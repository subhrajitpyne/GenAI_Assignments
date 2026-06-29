import os
import sys
import json
import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.coding_assistant.graph import graph
from src.coding_assistant.tools.file_tools import get_file_extension

router: APIRouter = APIRouter()


# ── Language detection ────────────────────────────────────────────────────────
_LANGUAGE_KEYWORDS: dict[str, list[str]] = {
    "java":       ["java"],
    "javascript": ["javascript", " js ", "node", "nodejs"],
    "python":     ["python", " py "],
}

def _detect_language(question: str) -> str:
    """
    Detect programming language from user prompt.
    Checks Java first — 'java' appears in 'javascript' so order matters.
    Defaults to python if nothing detected.
    """
    question_lower: str = f" {question.lower()} "
    for language, keywords in _LANGUAGE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in question_lower:
                print(f"[routes] keyword '{keyword.strip()}' → {language}", flush=True)
                return language
    print("[routes] no language detected → python (default)", flush=True)
    return "python"


# ── Schemas ───────────────────────────────────────────────────────────────────
class RunRequest(BaseModel):
    question: str
    # no language field — always auto-detected from question


class RunResponse(BaseModel):
    question:      str
    language:      str
    final_code:    str
    test_results:  str
    is_solved:     bool
    code_attempts: int
    test_attempts: int
    total_cost:    str
    agent_notes:   list[str]


def _build_initial_state(question: str, language: str) -> dict[str, Any]:
    """Build clean initial state."""
    ext: str = get_file_extension(language)
    return {
        "question":               question,
        "language":               language,
        "next":                   "",
        "messages":               [],
        "code":                   "",
        "test_code":              "",
        "code_file":              f"workspace/solution{ext}",
        "test_file":              f"workspace/test_solution{ext}",
        "test_validation_status": "",
        "test_validation_reason": "",
        "test_results":           "",
        "test_status":            "",
        "code_attempts":          0,
        "test_attempts":          0,
        "agent_notes":            [],
        "prompt_tokens":          0,
        "completion_tokens":      0,
        "total_cost_usd":         0.0,
        "final_code":             "",
        "final_test_code":        "",
        "is_solved":              False,
        "function_name":          "",
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "Coding Assistant API"}


@router.post("/run", response_model=RunResponse)
async def run_agent(request: RunRequest) -> RunResponse:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    language: str = _detect_language(request.question)
    print(f"[routes] /run — language: {language}", flush=True)

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    try:
        result: dict[str, Any] = await graph.ainvoke(
            _build_initial_state(request.question, language),
            config=config,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return RunResponse(
        question      = result["question"],
        language      = result["language"],
        final_code    = result.get("final_code", ""),
        test_results  = result.get("test_results", ""),
        is_solved     = result.get("is_solved", False),
        code_attempts = result.get("code_attempts", 0),
        test_attempts = result.get("test_attempts", 0),
        total_cost    = f"${result.get('total_cost_usd', 0.0):.4f}",
        agent_notes   = result.get("agent_notes", []),
    )


@router.post("/stream")
async def stream_agent(request: RunRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    language: str = _detect_language(request.question)
    print(f"[routes] /stream — language: {language}", flush=True)

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    async def event_generator():
        try:
            async for event in graph.astream(
                _build_initial_state(request.question, language),
                config=config,
                stream_mode="updates",
            ):
                for node_name, update in event.items():
                    payload = {
                        "node":        node_name,
                        "notes":       update.get("agent_notes", []),
                        "cost":        update.get("total_cost_usd", 0.0),
                        "is_solved":   update.get("is_solved"),
                        "final_code":  update.get("final_code"),
                        "test_status": update.get("test_status"),
                        "language":    language,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    await asyncio.sleep(0)

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )