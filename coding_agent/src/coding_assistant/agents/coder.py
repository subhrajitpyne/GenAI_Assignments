import os
import certifi
from typing import Any, Callable
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv

# ── SSL setup ─────────────────────────────────────────────────────────────────
os.environ["SSL_CERT_FILE"]      = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

import truststore
truststore.inject_into_ssl()

load_dotenv()

from ..state import ProjectState
from ..cost_tracker import SessionCostTracker, calculate_cost
from ..tools.file_tools import get_file_extension, write_file


# ── LLM ───────────────────────────────────────────────────────────────────────
_tracker: Callable = SessionCostTracker(model_name="gpt-4o-mini")
_llm: Callable     = init_chat_model(
    "openai:gpt-4o-mini",
    temperature=0.2,
    max_tokens=2000,
    callbacks=[_tracker],
)

_SYSTEM_PROMPT: str = """You are an expert software engineer.
Your job is to write clean, correct, well-structured code.

CRITICAL RULES — NEVER VIOLATE:
- Write code ONLY in the language specified by the user — never switch languages
- If language is Java — write Java. If Python — write Python. Never mix.
- Write ONLY the solution function(s) — absolutely NO test code
- NO def test_* functions anywhere in your output
- NO assert statements anywhere in your output
- NO if __name__ == '__main__' blocks
- NO example usage or demo code
- NO markdown, NO backticks, NO explanation
- ONLY the function(s) that solve the problem
- Handle edge cases in this EXACT order:
  1. Check for None/null FIRST
  2. Check for wrong type
  3. Check for invalid values (negative, empty, etc.)
- Function names must be clear and descriptive
"""


# ── Helper functions — defined BEFORE coder_node ──────────────────────────────

def _strip_code_fences(code: str) -> str:
    """Remove markdown code fences if LLM added them."""
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code  = "\n".join(
            line for line in lines
            if not line.startswith("```")
        ).strip()
    return code


def _strip_test_functions(code: str) -> str:
    """
    Remove any test functions or assert statements the LLM accidentally included.
    Runs after code fence stripping as a safety net.
    """
    lines:      list[str] = code.split("\n")
    clean:      list[str] = []
    skip_block: bool      = False

    for line in lines:
        stripped = line.strip()

        # start skipping when we hit a test function
        if stripped.startswith("def test_"):
            skip_block = True

        # stop skipping when we hit a real non-test function at root level
        if (
            skip_block
            and stripped.startswith("def ")
            and not stripped.startswith("def test_")
            and not line.startswith(" ")
            and not line.startswith("\t")
        ):
            skip_block = False

        if not skip_block:
            # also remove standalone assert lines outside functions
            if not stripped.startswith("assert "):
                clean.append(line)

    return "\n".join(clean).strip()




def _build_user_message(state: ProjectState, is_retry: bool, test_results: str) -> str:
    language: str = state.get("language", "python")

    if is_retry:
        return (
            f"Fix the following {language} code so all tests pass.\n\n"
            f"IMPORTANT: Write ONLY {language} code — not any other language.\n\n"
            f"Problem: {state['question']}\n\n"
            f"Your previous {language} code:\n{state.get('code', '')}\n\n"
            f"Test failure output:\n{test_results}\n\n"
            f"Write ONLY the corrected {language} solution function — no tests, no asserts."
        )
    return (
        f"Write a {language} solution for the following problem:\n\n"
        f"IMPORTANT: Write ONLY {language} code — not Python, not any other language.\n\n"
        f"Problem: {state['question']}\n\n"
        f"Write ONLY the {language} solution function — no tests, no asserts, no explanation."
    )

# ── Node ──────────────────────────────────────────────────────────────────────

def coder_node(state: ProjectState) -> dict[str, Any]:
    """
    Writes or fixes code based on the problem statement.
    On first run — writes from scratch.
    On retry    — fixes based on test failure output.
    Never reads test_code — only sees problem and test results.
    """
    attempt:      int  = state.get("code_attempts", 0) + 1
    test_results: str  = state.get("test_results", "")
    is_retry:     bool = bool(test_results and "FAIL" in test_results)

    print(f"[coder] attempt {attempt} — {'retry' if is_retry else 'first run'}")

    user_message: str = _build_user_message(state, is_retry, test_results)

    response: AIMessage = _llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ])

    generated_code: str = response.content

    # Step 1 — strip markdown code fences
    generated_code = _strip_code_fences(generated_code)

    # Step 2 — strip any test functions LLM accidentally included
    generated_code = _strip_test_functions(generated_code)

    # Step 3 — extract function name ← ADD THIS
    import re
    func_names: list[str] = re.findall(
        r"^def (\w+)\(", generated_code, re.MULTILINE
    )
    function_name: str = func_names[0] if func_names else "solution"
    print(f"[coder] function name extracted: {function_name}", flush=True)

    # save to workspace
    ext:       str = get_file_extension(state["language"])
    code_file: str = f"workspace/solution{ext}"
    write_file.invoke({"file_path": code_file, "content": generated_code})

    print(f"[coder] wrote {len(generated_code)} chars to {code_file}")

    # extract token usage
    usage:      dict  = _tracker.call_breakdown[-1] if _tracker.call_breakdown else {}
    p:          int   = usage.get("prompt_tokens", 0)
    c:          int   = usage.get("output_tokens", 0)
    cost:       float = calculate_cost("gpt-4o-mini", p, c)

    return {
        "code":              generated_code,
        "code_file":         code_file,
        "code_attempts":     attempt,
        "function_name":     function_name,    # ← ADD THIS
        "messages":          [response],
        "agent_notes":       [f"[coder] attempt {attempt} — {len(generated_code)} chars"],
        "prompt_tokens":     p,
        "completion_tokens": c,
        "total_cost_usd":    cost,
    }