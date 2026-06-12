"""
Hybrid RAG Pipeline
====================
Combines dense vector search (BGE embeddings) with sparse BM25 search
in a single Qdrant prefetch query, then applies cross-encoder reranking.
RBAC is enforced at the Qdrant retrieval layer via metadata filters.
"""

import os,certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

#Uses windows trusted certs from truststore
import truststore
truststore.inject_into_ssl()

import logging
import re
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchAny,
    Prefetch,
    FusionQuery,
    Fusion,
    SparseVector,
    SearchRequest,
)
from sentence_transformers import SentenceTransformer, CrossEncoder
from openai import OpenAI

from app.core.config import (
    settings,
    ROLE_COLLECTIONS,
    QDRANT_COLLECTION,
    EMBEDDING_MODEL,
    RERANKER_MODEL,
    INITIAL_RETRIEVE_K,
    RERANK_TOP_K,
)
from app.ingestion.ingest import get_embed_model, get_qdrant, load_bm25_vocab, _build_bm25_sparse_vector

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Singleton model holders
# ──────────────────────────────────────────────
_reranker: Optional[CrossEncoder] = None
_openai_client: Optional[OpenAI] = None


def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        logger.info(f"Loading reranker: {RERANKER_MODEL}")
        _reranker = CrossEncoder(RERANKER_MODEL)
    return _reranker


def get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


# ──────────────────────────────────────────────
# RBAC filter builder
# ──────────────────────────────────────────────
def build_rbac_filter(role: str) -> Filter:
    """Build a Qdrant filter restricting chunks to the role's allowed collections."""
    allowed = ROLE_COLLECTIONS.get(role, [])
    return Filter(
        must=[
            FieldCondition(
                key="collection",
                match=MatchAny(any=allowed),
            )
        ]
    )


# ──────────────────────────────────────────────
# Hybrid retrieval
# ──────────────────────────────────────────────
def hybrid_retrieve(query: str, role: str, top_k: int = INITIAL_RETRIEVE_K) -> list[dict]:
    """
    Retrieve top-k chunks using RRF fusion of dense + sparse search,
    with RBAC filter applied at the vector store layer.
    """
    embed_model = get_embed_model()
    client = get_qdrant()
    vocab = load_bm25_vocab()
    rbac_filter = build_rbac_filter(role)

    # Dense query vector
    dense_vec = embed_model.encode(query, normalize_embeddings=True).tolist()

    # Sparse query vector
    sparse_vec = _build_bm25_sparse_vector(query, vocab)

    try:
        # Hybrid search using Qdrant's native prefetch + RRF fusion
        results = client.query_points(
            collection_name=QDRANT_COLLECTION,
            prefetch=[
                Prefetch(
                    query=dense_vec,
                    using="dense",
                    filter=rbac_filter,
                    limit=top_k,
                ),
                Prefetch(
                    query=sparse_vec,
                    using="sparse",
                    filter=rbac_filter,
                    limit=top_k,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )
        points = results.points
    except Exception as e:
        logger.warning(f"Hybrid search failed ({e}), falling back to dense-only")
        results = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=("dense", dense_vec),
            query_filter=rbac_filter,
            limit=top_k,
            with_payload=True,
        )
        points = results

    chunks = []
    for point in points:
        payload = point.payload or {}
        chunks.append({
            "text": payload.get("text", ""),
            "source_document": payload.get("source_document", ""),
            "collection": payload.get("collection", ""),
            "access_roles": payload.get("access_roles", []),
            "section_title": payload.get("section_title", ""),
            "chunk_type": payload.get("chunk_type", "text"),
            "score": getattr(point, "score", 0.0),
        })

    return chunks


# ──────────────────────────────────────────────
# Reranking
# ──────────────────────────────────────────────
def rerank_chunks(query: str, chunks: list[dict], top_k: int = RERANK_TOP_K) -> list[dict]:
    """
    Apply cross-encoder reranking. Scores each (query, chunk) pair jointly
    and returns the top_k chunks sorted by reranker score.
    """
    if not chunks:
        return []

    reranker = get_reranker()
    pairs = [(query, chunk["text"]) for chunk in chunks]
    scores = reranker.predict(pairs)

    # Attach reranker scores and sort
    for chunk, score in zip(chunks, scores):
        chunk["reranker_score"] = float(score)

    ranked = sorted(chunks, key=lambda x: x["reranker_score"], reverse=True)
    top = ranked[:top_k]

    logger.info(
        f"Reranked {len(chunks)} → {len(top)} chunks. "
        f"Top score: {top[0]['reranker_score']:.3f} | "
        f"Bottom of initial: {ranked[-1]['reranker_score']:.3f}"
    )
    return top


# ──────────────────────────────────────────────
# LLM answer generation
# ──────────────────────────────────────────────
SYSTEM_PROMPT = """You are MediBot, an intelligent medical assistant for MediAssist Health Network.
You answer questions based ONLY on the provided document context.
Always cite the source document and section in your answer.
If the context does not contain enough information, say so clearly.
Do NOT make up medical information. Be precise and professional."""


def generate_answer(query: str, chunks: list[dict], role: str) -> str:
    """Generate a natural language answer from reranked chunks using the LLM."""
    client = get_openai()

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"[Source {i}: {chunk['source_document']}, Section: {chunk['section_title']}]\n"
            f"{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    user_prompt = f"""Context from authorised documents:

{context}

Question: {query}

Please answer based on the provided context. Mention the source document(s) in your response."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=800,
    )
    return response.choices[0].message.content


# ──────────────────────────────────────────────
# Main RAG chain
# ──────────────────────────────────────────────
def hybrid_rag_chain(query: str, role: str) -> dict:
    """
    Full pipeline: RBAC-filtered hybrid retrieval → reranking → LLM answer.
    Returns answer, sources, and retrieval type.
    """
    # 1. Hybrid retrieval with RBAC enforced at Qdrant layer
    candidates = hybrid_retrieve(query, role, top_k=INITIAL_RETRIEVE_K)

    if not candidates:
        allowed = ROLE_COLLECTIONS.get(role, [])
        return {
            "answer": (
                f"I couldn't find any relevant documents for your query. "
                f"As a {role.replace('_', ' ')}, you have access to the following collections: "
                f"{', '.join(allowed)}. Please ensure your question is related to these areas."
            ),
            "sources": [],
            "retrieval_type": "hybrid_rag",
        }

    # 2. Rerank to top-k
    top_chunks = rerank_chunks(query, candidates, top_k=RERANK_TOP_K)

    # 3. LLM answer generation
    answer = generate_answer(query, top_chunks, role)

    sources = [
        {
            "source_document": c["source_document"],
            "section_title": c["section_title"],
            "collection": c["collection"],
        }
        for c in top_chunks
    ]

    return {
        "answer": answer,
        "sources": sources,
        "retrieval_type": "hybrid_rag",
    }
