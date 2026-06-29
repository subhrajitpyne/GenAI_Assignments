from typing import Any, Literal
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.chat_models import init_chat_model

from ..state import ProjectState
from ..cost_tracker import SessionCostTracker, calculate_cost

from dotenv import load_dotenv

import os,certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

#Uses windows trusted certs from truststore
import truststore
truststore.inject_into_ssl()

load_dotenv()

# ── Structured output schema ───────────────────────────────────────────────────
class OrchestratorDecision(BaseModel):
    next:   Literal["coder", "tester", "validate_tests", "runner", "output"]
    reason: str


# ── LLM — temperature=0 for deterministic routing ─────────────────────────────
_tracker   = SessionCostTracker(model_name="gpt-4o-mini")
_llm       = init_chat_model(
    "openai:gpt-4o-mini",
    temperature=0,
    callbacks=[_tracker],
)
_router_llm = _llm.with_structured_output(OrchestratorDecision)


_SYSTEM_PROMPT: str = """You are an orchestrator managing a coding assistant pipeline.

Your job is to decide which agent runs next based on the current state.

Routing rules:
- coder         : no code yet, OR code failed tests (code_attempts < 3)
- tester        : no test cases yet, OR test cases were invalid (test_attempts < 2)
- validate_tests: both code and test_code exist but tests not yet validated
- runner        : tests are validated as valid — run them against the code
- output        : tests passed OR max attempts reached

Always check attempts before routing back to coder or tester.
If code_attempts >= 3 and tests still fail → route to output.
If test_attempts >= 2 and tests still invalid → route to output.
"""


def orchestrator_node(state: ProjectState) -> dict[str, Any]:
    """
    Supervisor node — reads full state and decides which agent runs next.
    Uses LLM with structured output for deterministic routing decisions.
    """
    print("[orchestrator] deciding next step...")

    # build context for the LLM to reason about
    context: str = f"""
Current state:
- code exists          : {bool(state.get('code'))}
- test_code exists     : {bool(state.get('test_code'))}
- code_attempts        : {state.get('code_attempts', 0)}
- test_attempts        : {state.get('test_attempts', 0)}
- test_validation      : {state.get('test_validation_status', 'not done')}
- test_status          : {state.get('test_status', 'not run')}

DECISION RULES — follow exactly:
- code empty                                    → coder
- test_code empty                               → tester
- validation not done AND test_attempts < 2    → validate_tests
- validation = valid AND test_status = not run → runner
- test_status = fail AND code_attempts < 3     → runner   ← ALWAYS runner after coder retry
- test_status = pass                           → output
- code_attempts >= 3                           → output
- test_attempts >= 2 AND validation invalid    → output

IMPORTANT: After coder retries — ALWAYS route to runner next. Never skip runner.
Current code_attempts={state.get('code_attempts', 0)} — max is 3.
test_status='{state.get('test_status', 'not run')}' — if fail and attempts < 3 → runner.
"""

    decision: OrchestratorDecision = _router_llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ])

    print(f"[orchestrator] → {decision.next} | {decision.reason}")

    # extract token usage from tracker
    usage      = _tracker.call_breakdown[-1] if _tracker.call_breakdown else {}
    p: int     = usage.get("prompt_tokens", 0)
    c: int     = usage.get("output_tokens", 0)
    cost: float = calculate_cost("gpt-4o-mini", p, c)

    return {
        "next":              decision.next,
        "agent_notes":       [f"[orchestrator] → {decision.next}: {decision.reason}"],
        "prompt_tokens":     p,
        "completion_tokens": c,
        "total_cost_usd":    cost,
    }
