import os
import re
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
- ALWAYS write code in the EXACT language specified by the user
- If user says Java → write Java. If Python → write Python. NEVER switch languages.
- Write ONLY the solution function(s) — absolutely NO test code
- NO def test_* functions anywhere in your output
- NO assert statements anywhere in your output
- NO if __name__ == '__main__' blocks
- NO example usage or demo code
- NO markdown, NO backticks, NO explanation
- ONLY the function(s) that solve the problem in the CORRECT language
- Handle edge cases: None/null first, then type check, then value check
- Function names must be clear and descriptive
"""


# ── Helper functions ───────────────────────────────────────────────────────────

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


def _strip_test_functions(code: str, language: str = "python") -> str:
    """
    Remove test functions accidentally included by LLM.
    Only applied for Python — other languages have different test syntax
    and stripping could corrupt valid code.
    """
    if language.lower() != "python":
        return code   # ← do not touch Java/JS/Go/TS code

    lines:      list[str] = code.split("\n")
    clean:      list[str] = []
    skip_block: bool      = False

    for line in lines:
        stripped = line.strip()

        # start skipping at test function
        if stripped.startswith("def test_"):
            skip_block = True

        # stop skipping at next real non-test root-level function
        if (
            skip_block
            and stripped.startswith("def ")
            and not stripped.startswith("def test_")
            and not line.startswith(" ")
            and not line.startswith("\t")
        ):
            skip_block = False

        if not skip_block:
            # remove standalone assert lines outside functions
            if not stripped.startswith("assert "):
                clean.append(line)

    return "\n".join(clean).strip()


def _extract_function_name(code: str, language: str) -> str:
    """
    Extract the first function/method name from generated code.
    Handles Python, Java, JavaScript, TypeScript, Go.
    """
    language = language.lower().strip()

    if language == "python":
        matches = re.findall(r"^def (\w+)\(", code, re.MULTILINE)

    elif language == "java":
        # public static long factorial(int n) or public int add(int a, int b)
        matches = re.findall(
            r"public\s+(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(", code
        )

    elif language in ("javascript", "typescript"):
        # function factorial(n) or const factorial = (n) => or factorial(n) {
        matches = re.findall(
            r"(?:function\s+(\w+)|const\s+(\w+)\s*=|(\w+)\s*\()",
            code,
        )
        # flatten tuples from groups
        matches = [m for group in matches for m in group if m]

    elif language == "go":
        # func factorial(n int) int {
        matches = re.findall(r"^func\s+(\w+)\s*\(", code, re.MULTILINE)

    else:
        matches = re.findall(r"(\w+)\s*\(", code)

    # filter out common keywords that are not function names
    _skip: set[str] = {
        "if", "for", "while", "switch", "return", "class",
        "public", "private", "static", "void", "int", "long",
        "String", "float", "double", "bool", "main",
    }
    matches = [m for m in matches if m not in _skip]

    return matches[0] if matches else "solution"


def _build_user_message(
    state:        ProjectState,
    is_retry:     bool,
    test_results: str,
) -> str:
    """Build the user prompt for first attempt or retry."""
    language: str = state.get("language", "python")
    question: str = state["question"]

    lang_instruction: str = (
        f"MANDATORY: Write ONLY {language.upper()} code.\n"
        f"DO NOT write Python or any other language unless explicitly told to.\n"
        f"The output must be valid {language} syntax ONLY.\n"
    )

    if is_retry:
        return (
            f"{lang_instruction}\n"
            f"Fix the following {language} code so all tests pass.\n\n"
            f"Problem: {question}\n\n"
            f"Your previous {language} code:\n{state.get('code', '')}\n\n"
            f"Test failure output:\n{test_results}\n\n"
            f"Write ONLY the corrected {language} solution — no tests, no asserts."
        )

    return (
        f"{lang_instruction}\n"
        f"Write a {language} solution for this problem:\n\n"
        f"{question}\n\n"
        f"Write ONLY the {language} solution — no tests, no asserts, no explanation."
    )


# ── Node ──────────────────────────────────────────────────────────────────────

def coder_node(state: ProjectState) -> dict[str, Any]:
    """
    Writes or fixes code based on the problem statement.
    On first run — writes from scratch in the detected language.
    On retry    — fixes based on test failure output.
    Never reads test_code — only sees problem and test results.
    """
    attempt:      int  = state.get("code_attempts", 0) + 1
    language:     str  = state.get("language", "python")
    test_results: str  = state.get("test_results", "")
    is_retry:     bool = bool(test_results and "FAIL" in test_results)

    print(f"[coder] attempt {attempt} — {'retry' if is_retry else 'first run'} — language: {language}", flush=True)

    user_message: str = _build_user_message(state, is_retry, test_results)

    response: AIMessage = _llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ])

    generated_code: str = response.content

    # Step 1 — strip markdown code fences
    generated_code = _strip_code_fences(generated_code)

    # Step 2 — strip test functions (Python only — other languages untouched)
    generated_code = _strip_test_functions(generated_code, language)

    # Step 3 — extract function name (language-aware)
    function_name: str = _extract_function_name(generated_code, language)
    print(f"[coder] function name: {function_name}", flush=True)
    print(f"[coder] first 100 chars:\n{generated_code[:100]}", flush=True)

    # save to workspace
    ext:       str = get_file_extension(language)
    code_file: str = f"workspace/solution{ext}"
    write_file.invoke({"file_path": code_file, "content": generated_code})

    print(f"[coder] wrote {len(generated_code)} chars to {code_file}", flush=True)

    # extract token usage
    usage:      dict  = _tracker.call_breakdown[-1] if _tracker.call_breakdown else {}
    p:          int   = usage.get("prompt_tokens", 0)
    c:          int   = usage.get("output_tokens", 0)
    cost:       float = calculate_cost("gpt-4o-mini", p, c)

    return {
        "code":              generated_code,
        "code_file":         code_file,
        "code_attempts":     attempt,
        "function_name":     function_name,
        "messages":          [response],
        "agent_notes":       [f"[coder] attempt {attempt} ({language}) — {len(generated_code)} chars"],
        "prompt_tokens":     p,
        "completion_tokens": c,
        "total_cost_usd":    cost,
    }