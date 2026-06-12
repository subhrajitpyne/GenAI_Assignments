"""
Query Router
=============
Decides whether a question should go to SQL RAG (analytical/numbers)
or Hybrid RAG (document-based). Uses a simple LLM classifier.
"""
import re
from openai import OpenAI
from app.rag.hybrid_rag import get_openai
from app.core.config import SQL_ALLOWED_ROLES

# Keywords that strongly suggest analytical/numerical queries
ANALYTICAL_KEYWORDS = [
    r"\bhow many\b",
    r"\bcount\b",
    r"\btotal\b",
    r"\bsum\b",
    r"\baverage\b",
    r"\bstatistic",
    r"\breport\b",
    r"\blast month\b",
    r"\bthis year\b",
    r"\bpending claim",
    r"\bescalated\b",
    r"\bmost open\b",
    r"\bwhich department\b",
    r"\bwhich equipment\b",
    r"\bbreakdown of\b",
    r"\bpercentage\b",
    r"\bwhat is the status of\b",
    r"\bhow much\b",
    r"\btop \d+\b",
]


def is_analytical_question(question: str) -> bool:
    """Heuristic check for analytical/numerical questions."""
    q_lower = question.lower()
    for pattern in ANALYTICAL_KEYWORDS:
        if re.search(pattern, q_lower):
            return True
    return False


def route_question(question: str, role: str) -> str:
    """
    Returns 'sql_rag' or 'hybrid_rag'.
    SQL RAG only available for billing_executive and admin roles.
    """
    if role not in SQL_ALLOWED_ROLES:
        return "hybrid_rag"

    return "sql_rag" if is_analytical_question(question) else "hybrid_rag"
