"""
Document Ingestion Pipeline
============================
Uses Docling for structural-aware PDF parsing and HybridChunker for
section-aware hierarchical chunking. Stores chunks with full metadata
and both dense (BGE) + sparse (BM25) vectors in Qdrant.

Compatible with docling 2.x (latest) and older 2.5.x releases.
"""
import os
import json
import logging
import re
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────
# Docling imports — explicit with clear error messages
# ──────────────────────────────────────────────

# 1. DocumentConverter (stable across all docling versions)
try:
    from docling.document_converter import DocumentConverter
except ImportError as e:
    raise ImportError(
        "\n\n[MediBot] Could not import docling.document_converter.\n"
        "Fix: pip install docling docling-core\n"
        f"Error: {e}"
    )

# 2. HybridChunker — location changed in docling >= 2.6
_HybridChunker = None
try:
    # docling >= 2.6 (current): lives in docling_core
    from docling_core.transforms.chunker import HybridChunker
    _HybridChunker = HybridChunker
except ImportError:
    pass

if _HybridChunker is None:
    try:
        # docling <= 2.5: lived in docling.chunking
        from docling.chunking import HybridChunker  # type: ignore
        _HybridChunker = HybridChunker
    except ImportError:
        pass

# 3. HuggingFaceTokenizer for HybridChunker config
_HuggingFaceTokenizer = None
try:
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
    _HuggingFaceTokenizer = HuggingFaceTokenizer
except ImportError:
    try:
        from docling.chunking import HuggingFaceTokenizer  # type: ignore
        _HuggingFaceTokenizer = HuggingFaceTokenizer
    except ImportError:
        pass

# ──────────────────────────────────────────────
# Other imports
# ──────────────────────────────────────────────
from transformers import AutoTokenizer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    SparseVector,
)
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

from app.core.config import (
    settings,
    COLLECTION_ACCESS,
    QDRANT_COLLECTION,
    EMBEDDING_MODEL,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("DocumentConverter: OK")
logger.info(f"HybridChunker: {'OK from ' + _HybridChunker.__module__ if _HybridChunker else 'NOT FOUND — fallback chunker will be used'}")
logger.info(f"HuggingFaceTokenizer: {'OK' if _HuggingFaceTokenizer else 'NOT FOUND — will use defaults'}")

# ──────────────────────────────────────────────
# Singleton model holders
# ──────────────────────────────────────────────
_embed_model: Optional[SentenceTransformer] = None
_qdrant_client: Optional[QdrantClient] = None


def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embed_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embed_model


def get_qdrant() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        if settings.qdrant_url:
            try:
                _qdrant_client = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key,
                    timeout=60,
                )
                _qdrant_client.get_collections()
                logger.info(f"Connected to remote Qdrant at {settings.qdrant_url}")
            except Exception as e:
                logger.warning(f"Remote Qdrant failed ({e}), using local path")
                _qdrant_client = QdrantClient(path=settings.qdrant_path)
        else:
            os.makedirs(settings.qdrant_path, exist_ok=True)
            _qdrant_client = QdrantClient(path=settings.qdrant_path)
            logger.info(f"Using local Qdrant storage at: {settings.qdrant_path}")
    return _qdrant_client


# ──────────────────────────────────────────────
# Collection → file mappings
# ──────────────────────────────────────────────
COLLECTION_FILES = {
    "general": [
        "staff_handbook.pdf",
        "code_of_conduct.pdf",
        "leave_policy.pdf",
        "general_faqs.pdf",
    ],
    "clinical": [
        "treatment_protocols.pdf",
        "drug_formulary.pdf",
        "diagnostic_reference.pdf",
    ],
    "nursing": ["icu_nursing_procedures.pdf", "infection_control.pdf"],
    "billing": ["billing_codes.pdf", "claim_submission_guide.md"],
    "equipment": ["equipment_manual.pdf"],
}


def _build_bm25_sparse_vector(text: str, vocab: dict) -> SparseVector:
    """Build a BM25-style sparse vector for a single text using vocab index."""
    tokens = re.findall(r'\w+', text.lower())
    freq: dict = {}
    for token in tokens:
        idx = vocab.get(token)
        if idx is not None:
            freq[idx] = freq.get(idx, 0) + 1.0
    if not freq:
        return SparseVector(indices=[0], values=[0.0])
    return SparseVector(indices=list(freq.keys()), values=list(freq.values()))


def _build_chunker():
    """
    Build HybridChunker with token-aware sizing.
    Handles API differences across docling versions gracefully.
    Returns chunker instance or None (fallback will be used).
    """
    if _HybridChunker is None:
        logger.warning("HybridChunker unavailable — using paragraph fallback")
        return None

    try:
        hf_tok = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)

        if _HuggingFaceTokenizer is not None:
            try:
                tok_wrapper = _HuggingFaceTokenizer(tokenizer=hf_tok, max_tokens=256)
            except TypeError:
                tok_wrapper = _HuggingFaceTokenizer(tokenizer=hf_tok)
            try:
                return _HybridChunker(tokenizer=tok_wrapper)
            except TypeError:
                return _HybridChunker()
        else:
            try:
                return _HybridChunker(tokenizer=hf_tok, max_tokens=256)
            except TypeError:
                try:
                    return _HybridChunker(tokenizer=hf_tok)
                except TypeError:
                    return _HybridChunker()

    except Exception as e:
        logger.warning(f"Could not build HybridChunker ({e}) — using fallback")
        return None


def _chunk_docling_doc(doc, filename: str, collection_name: str,
                       access_roles: list, chunker) -> list:
    """
    Chunk a parsed Docling document.
    Uses HybridChunker if available, else paragraph fallback.
    """
    chunks = []

    if chunker is not None:
        try:
            try:
                chunk_iter = chunker.chunk(dl_doc=doc)
            except TypeError:
                chunk_iter = chunker.chunk(doc)

            for chunk in chunk_iter:
                if hasattr(chunk, "text"):
                    text = chunk.text.strip()
                elif hasattr(chunk, "content"):
                    text = str(chunk.content).strip()
                else:
                    continue

                if not text:
                    continue

                section_title = _extract_section_title(chunk)
                chunk_type = _detect_chunk_type(chunk)
                enriched = f"{section_title}: {text}" if section_title else text

                chunks.append({
                    "text": enriched,
                    "source_document": filename,
                    "collection": collection_name,
                    "access_roles": access_roles,
                    "section_title": section_title or "General",
                    "chunk_type": chunk_type,
                })

            if chunks:
                return chunks

        except Exception as e:
            logger.warning(f"HybridChunker failed on {filename} ({e}) — using fallback")

    # ── Fallback: export to markdown then paragraph-split ──
    logger.info(f"Using paragraph fallback for: {filename}")
    try:
        full_text = doc.export_to_markdown()
    except Exception:
        try:
            full_text = str(doc)
        except Exception:
            return []

    return _split_into_chunks(full_text, filename, collection_name, access_roles)


def _split_into_chunks(text: str, filename: str, collection: str,
                       access_roles: list, max_chars: int = 1200) -> list:
    """Paragraph-aware chunker used as fallback when HybridChunker is unavailable."""
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
    chunks = []
    current_heading = "General"
    buffer = []
    buffer_len = 0

    def flush():
        if buffer:
            body = "\n\n".join(buffer)
            chunks.append({
                "text": f"{current_heading}: {body}" if current_heading != "General" else body,
                "source_document": filename,
                "collection": collection,
                "access_roles": access_roles,
                "section_title": current_heading,
                "chunk_type": "text",
            })

    for para in paragraphs:
        if para.startswith("#"):
            flush()
            buffer = []
            buffer_len = 0
            current_heading = para.lstrip("#").strip()
            continue

        if buffer_len + len(para) > max_chars and buffer:
            flush()
            buffer = []
            buffer_len = 0

        buffer.append(para)
        buffer_len += len(para)

    flush()
    return chunks


def ingest_all_documents(data_dir: str = None, force_reingest: bool = False) -> dict:
    """
    Main ingestion function. Parses all documents with Docling,
    chunks with HybridChunker (or paragraph fallback), and upserts to Qdrant.
    """
    data_dir = data_dir or settings.data_dir
    data_path = Path(data_dir)
    embed_model = get_embed_model()
    client = get_qdrant()

    # ── Check if already ingested ──
    existing = client.get_collections()
    existing_names = [c.name for c in existing.collections]
    if QDRANT_COLLECTION in existing_names and not force_reingest:
        logger.info("Collection already exists. Skipping ingestion.")
        count = client.count(QDRANT_COLLECTION).count
        return {"status": "skipped", "existing_chunks": count}

    # ── Create / recreate collection ──
    embed_dim = embed_model.get_sentence_embedding_dimension()
    if QDRANT_COLLECTION in existing_names:
        client.delete_collection(QDRANT_COLLECTION)

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config={"dense": VectorParams(size=embed_dim, distance=Distance.COSINE)},
        sparse_vectors_config={
            "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))
        },
    )
    logger.info(f"Created Qdrant collection '{QDRANT_COLLECTION}' dim={embed_dim}")

    # ── Build chunker + converter ──
    chunker = _build_chunker()
    converter = DocumentConverter()

    all_chunks = []
    all_texts = []

    for collection_name, filenames in COLLECTION_FILES.items():
        coll_dir = data_path / collection_name
        access_roles = COLLECTION_ACCESS[collection_name]

        for filename in filenames:
            file_path = coll_dir / filename
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue

            logger.info(f"Parsing: {file_path}")
            try:
                if filename.endswith(".md"):
                    text = file_path.read_text(encoding="utf-8")
                    sections = _parse_markdown_sections(
                        text, filename, collection_name, access_roles
                    )
                    all_chunks.extend(sections)
                    all_texts.extend([s["text"] for s in sections])
                else:
                    result = converter.convert(str(file_path))
                    doc = result.document
                    doc_chunks = _chunk_docling_doc(
                        doc, filename, collection_name, access_roles, chunker
                    )
                    all_chunks.extend(doc_chunks)
                    all_texts.extend([c["text"] for c in doc_chunks])

            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}", exc_info=True)
                continue

    logger.info(f"Total chunks to ingest: {len(all_chunks)}")

    if not all_chunks:
        return {
            "status": "error",
            "message": "No chunks generated. Check DATA_DIR path in .env",
        }

    # ── Build BM25 vocabulary ──
    tokenized_corpus = [re.findall(r'\w+', t.lower()) for t in all_texts]
    BM25Okapi(tokenized_corpus)
    vocab: dict = {}
    for tokens in tokenized_corpus:
        for token in tokens:
            if token not in vocab:
                vocab[token] = len(vocab)

    # ── Dense embeddings ──
    logger.info("Generating dense embeddings...")
    dense_embeddings = embed_model.encode(
        all_texts, batch_size=32, show_progress_bar=True, normalize_embeddings=True
    )

    # ── Upsert to Qdrant ──
    points = []
    for i, (chunk, dense_vec) in enumerate(zip(all_chunks, dense_embeddings)):
        sparse_vec = _build_bm25_sparse_vector(chunk["text"], vocab)
        points.append(
            PointStruct(
                id=i,
                vector={"dense": dense_vec.tolist(), "sparse": sparse_vec},
                payload={
                    "text": chunk["text"],
                    "source_document": chunk["source_document"],
                    "collection": chunk["collection"],
                    "access_roles": chunk["access_roles"],
                    "section_title": chunk["section_title"],
                    "chunk_type": chunk["chunk_type"],
                },
            )
        )

    batch_size = 100
    for start in range(0, len(points), batch_size):
        batch = points[start: start + batch_size]
        client.upsert(collection_name=QDRANT_COLLECTION, points=batch)
        logger.info(f"Upserted {min(start + batch_size, len(points))}/{len(points)}")

    # ── Save BM25 vocab ──
    vocab_path = Path(data_dir) / "bm25_vocab.json"
    with open(vocab_path, "w") as f:
        json.dump(vocab, f)
    logger.info(f"Saved BM25 vocab → {vocab_path}")

    return {
        "status": "success",
        "total_chunks": len(all_chunks),
        "collection": QDRANT_COLLECTION,
        "chunker_used": "HybridChunker" if chunker else "FallbackParagraphChunker",
    }


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _extract_section_title(chunk) -> str:
    try:
        meta = chunk.meta
        if hasattr(meta, "headings") and meta.headings:
            return meta.headings[-1]
        if hasattr(meta, "doc_items"):
            for item in reversed(meta.doc_items):
                if hasattr(item, "label") and "heading" in str(item.label).lower():
                    if hasattr(item, "text"):
                        return item.text[:100]
    except Exception:
        pass
    return ""


def _detect_chunk_type(chunk) -> str:
    try:
        meta = chunk.meta
        if hasattr(meta, "doc_items"):
            for item in meta.doc_items:
                label = str(getattr(item, "label", "")).lower()
                if "table" in label:
                    return "table"
                if "heading" in label:
                    return "heading"
                if "code" in label:
                    return "code"
    except Exception:
        pass
    return "text"


def _parse_markdown_sections(text: str, filename: str,
                              collection: str, access_roles: list) -> list:
    """Parse a Markdown file into section-aware chunks."""
    lines = text.split("\n")
    chunks = []
    current_heading = "General"
    current_lines: list = []

    def flush():
        body = "\n".join(current_lines).strip()
        if body:
            chunks.append({
                "text": f"{current_heading}: {body}",
                "source_document": filename,
                "collection": collection,
                "access_roles": access_roles,
                "section_title": current_heading,
                "chunk_type": "text",
            })

    for line in lines:
        if line.startswith("#"):
            flush()
            current_heading = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)
    flush()
    return chunks


def load_bm25_vocab(data_dir: str = None) -> dict:
    """Load persisted BM25 vocabulary."""
    data_dir = data_dir or settings.data_dir
    vocab_path = Path(data_dir) / "bm25_vocab.json"
    if not vocab_path.exists():
        return {}
    with open(vocab_path) as f:
        return json.load(f)