from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.core.auth import get_current_user
from app.core.config import ROLE_COLLECTIONS, SQL_ALLOWED_ROLES
from app.rag.router import route_question
from app.rag.hybrid_rag import hybrid_rag_chain
from app.rag.sql_rag import sql_rag_chain

router = APIRouter(tags=["Chat"])


class ChatRequest(BaseModel):
    question: str


class SourceCitation(BaseModel):
    source_document: str
    section_title: str
    collection: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    retrieval_type: str  # "hybrid_rag" or "sql_rag"
    role: str
    collections: list[str]
    sql_rag_available: bool


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """
    Main RAG endpoint. Applies RBAC at retrieval layer.
    Routes to Hybrid RAG or SQL RAG based on question type.
    """
    role = current_user.get("role", "")
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    allowed_collections = ROLE_COLLECTIONS.get(role, [])

    # Route question
    retrieval_type = route_question(question, role)

    if retrieval_type == "sql_rag":
        # SQL RAG path
        answer = sql_rag_chain(question)
        return ChatResponse(
            answer=answer,
            sources=[],
            retrieval_type="sql_rag",
            role=role,
            collections=allowed_collections,
            sql_rag_available=role in SQL_ALLOWED_ROLES,
        )
    else:
        # Hybrid RAG path - RBAC enforced inside hybrid_rag_chain
        result = hybrid_rag_chain(question, role)
        return ChatResponse(
            answer=result["answer"],
            sources=[SourceCitation(**s) for s in result["sources"]],
            retrieval_type=result["retrieval_type"],
            role=role,
            collections=allowed_collections,
            sql_rag_available=role in SQL_ALLOWED_ROLES,
        )


@router.get("/collections/{role}")
def get_collections(role: str, current_user: dict = Depends(get_current_user)):
    """Return document collections accessible to the given role."""
    # Non-admin users can only query their own role's collections
    requester_role = current_user.get("role", "")
    if requester_role != "admin" and requester_role != role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view collections for your own role",
        )

    collections = ROLE_COLLECTIONS.get(role)
    if collections is None:
        raise HTTPException(status_code=404, detail=f"Unknown role: {role}")

    return {
        "role": role,
        "collections": collections,
        "sql_rag_available": role in SQL_ALLOWED_ROLES,
    }
