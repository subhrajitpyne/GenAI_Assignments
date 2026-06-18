import os
import sys
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# make sure src/ is on the path when running from backend/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.blog_generator.graph import graph  # noqa: E402

router: APIRouter = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    topic: str


class GenerateResponse(BaseModel):
    topic:      str
    final_post: str
    sources:    list[str]
    iterations: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/health")
def health_check() -> dict[str, str]:
    """Simple liveness check — useful for deployment monitoring."""
    return {"status": "ok", "service": "Blog Post Generator API"}


@router.post("/generate", response_model=GenerateResponse)
async def generate_post(request: GenerateRequest) -> GenerateResponse:
    """
    Run the LangGraph multi-agent pipeline for the given topic
    and return the final LinkedIn post along with metadata.
    """
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty.")

    initial_state: dict[str, Any] = {
        "topic":           request.topic,
        "messages":        [],
        "research":        "",
        "trends":          "",
        "draft":           "",
        "review_feedback": "",
        "sources":         [],
        "iteration":       0,
        "final_post":      "",
    }

    try:
        result: dict[str, Any] = graph.invoke(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return GenerateResponse(
        topic      = result["topic"],
        final_post = result["final_post"],
        sources    = result["sources"],
        iterations = result["iteration"],
    )
