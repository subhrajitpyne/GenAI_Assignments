from typing import Any, Literal
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.chat_models import init_chat_model

from ..state import ProjectState
from ..cost_tracker import SessionCostTracker, calculate_cost


# ── Structured output schema ───────────────────────────────────────────────────
class TestValidationResult(BaseModel):
    status: Literal["valid", "invalid"]
    reason: str

from dotenv import load_dotenv

import os,certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

#Uses windows trusted certs from truststore
import truststore
truststore.inject_into_ssl()

load_dotenv()

# ── LLM ───────────────────────────────────────────────────────────────────────
_tracker    = SessionCostTracker(model_name="gpt-4o-mini")
_llm        = init_chat_model(
    "openai:gpt-4o-mini",
    temperature=0,
    callbacks=[_tracker],
)
_validator_llm = _llm.with_structured_output(TestValidationResult)

_SYSTEM_PROMPT: str = """You are a senior QA engineer reviewing test cases.

A test suite is VALID if it correctly tests the requirements. Rules vary by language:

Python:
- Test functions must start with test_
- Import statement must be present

JavaScript/TypeScript:
- Uses describe() and it() or test() blocks — NOT test_ prefix
- Import or require statement present
- Any standard Jest/Mocha format is acceptable

Java:
- Uses @Test annotation on each test method
- Import statements for JUnit present
- Method names do NOT need to start with test_

Go:
- Test functions start with Test (capital T)
- Uses testing.T parameter

A test suite is INVALID ONLY if:
- Tests a completely different function than required
- No test cases exist at all
- Wrong language syntax used entirely

NEVER reject tests for:
- Not using test_ prefix in JavaScript/Java/Go (only required for Python)
- Testing edge cases not mentioned in problem
- Being too thorough
"""


def validator_node(state: ProjectState) -> dict[str, Any]:
    """
    Supervisor validates test cases against the problem statement.
    Does NOT run the tests — just checks if they make sense semantically.
    Returns validation status and reason.
    """
    print("[validator] checking test cases against problem statement...")

    result: TestValidationResult = _validator_llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Problem statement:\n{state['question']}\n\n"
            f"Generated test cases:\n{state.get('test_code', '')}\n\n"
            f"Are these test cases valid for this problem?"
        )),
    ])

    status_emoji: str = "✅" if result.status == "valid" else "❌"
    print(f"[validator] {status_emoji} {result.status} — {result.reason}")

    # extract token usage
    usage       = _tracker.call_breakdown[-1] if _tracker.call_breakdown else {}
    p: int      = usage.get("prompt_tokens", 0)
    c: int      = usage.get("output_tokens", 0)
    cost: float = calculate_cost("gpt-4o-mini", p, c)

    return {
        "test_validation_status": result.status,
        "test_validation_reason": result.reason,
        "agent_notes":            [f"[validator] {result.status}: {result.reason}"],
        "prompt_tokens":          p,
        "completion_tokens":      c,
        "total_cost_usd":         cost,
    }
