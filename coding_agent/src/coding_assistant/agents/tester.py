import os
import certifi
from typing import Any
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
_tracker = SessionCostTracker(model_name="gpt-4o-mini")
_llm     = init_chat_model(
    "openai:gpt-4o-mini",
    temperature=0.1,
    max_tokens=2000,
    callbacks=[_tracker],
)


# ── Language-aware system prompts ─────────────────────────────────────────────
_PYTHON_PROMPT: str = """You are an expert QA engineer writing comprehensive pytest test cases.

Rules:
- Write ONLY pytest test code — no markdown, no backticks, no explanation
- ALWAYS use this exact import: from solution import *
- This imports ALL functions from the solution — do NOT hardcode the function name in the import
- Write at minimum 5 test cases covering:
  * Happy path (normal inputs)
  * Edge cases (empty, None, zero, negative)
  * Boundary values
  * Error conditions
- Each test function must start with test_
- Test function names must clearly describe what they test
- Call the solution function by the name that makes sense for the problem
- Do NOT write the solution — test only the requirements
- Tests must be independent of each other
"""

_JAVASCRIPT_PROMPT: str = """You are an expert QA engineer writing comprehensive Jest test cases.

Rules:
- Write ONLY Jest test code — no markdown, no backticks, no explanation
- Do NOT use require or import — the function will be available directly
- Use describe() and it() blocks like this:

describe('functionName', () => {
  it('should return correct result for happy path', () => {
    expect(functionName(5)).toBe(120);
  });
  it('should handle null input', () => {
    expect(functionName(null)).toBeNull();
  });
  it('should handle negative numbers', () => {
    expect(functionName(-1)).toBeNull();
  });
  it('should handle zero', () => {
    expect(functionName(0)).toBe(1);
  });
  it('should handle large numbers', () => {
    expect(functionName(10)).toBe(3628800);
  });
});

- Write minimum 5 test cases covering happy path, edge cases, boundaries
- Do NOT write the solution — test only the requirements
- Do NOT use require() or import statements
"""

_JAVA_PROMPT: str = """You are an expert QA engineer who writes comprehensive JUnit 5 test cases.

Rules:
- Write ONLY JUnit 5 test code — no markdown, no backticks, no explanation
- Use @Test annotation on each test method
- Import org.junit.jupiter.api.Test and org.junit.jupiter.api.Assertions.*
- Write at minimum 5 test cases covering happy path, edge cases, boundaries
- Test method names must clearly describe what they test
- Do NOT look at any implementation — test only the requirements
- Tests must be in a class ending with Test
"""

_TYPESCRIPT_PROMPT: str = """You are an expert QA engineer who writes comprehensive Jest test cases for TypeScript.

Rules:
- Write ONLY Jest + TypeScript test code — no markdown, no backticks, no explanation
- Import the solution using: import { functionName } from './solution';
- Write at minimum 5 test cases covering happy path, edge cases, boundaries
- Use describe() and test() or it() blocks
- Test names must clearly describe what they test
- Do NOT look at any implementation — test only the requirements
"""

_GO_PROMPT: str = """You are an expert QA engineer who writes comprehensive Go test cases.

Rules:
- Write ONLY Go test code — no markdown, no backticks, no explanation
- Use the testing package: import "testing"
- Each test function must start with Test and accept *testing.T
- Write at minimum 5 test cases covering happy path, edge cases, boundaries
- Use t.Errorf() for assertions
- Do NOT look at any implementation — test only the requirements
"""

_DEFAULT_PROMPT: str = """You are an expert QA engineer who writes comprehensive test cases.

Rules:
- Write ONLY test code for {language} — no markdown, no backticks, no explanation
- Follow {language} testing conventions and best practices
- Write at minimum 5 test cases covering:
  * Happy path (normal inputs)
  * Edge cases (empty, None, zero, negative)
  * Boundary values
  * Error conditions
- Test names must clearly describe what they test
- Do NOT look at any implementation — test only the requirements
"""

_PROMPT_MAP: dict[str, str] = {
    "python":     _PYTHON_PROMPT,
    "javascript": _JAVASCRIPT_PROMPT,
    "java":       _JAVA_PROMPT,
    "typescript": _TYPESCRIPT_PROMPT,
    "go":         _GO_PROMPT,
}


def _get_system_prompt(language: str) -> str:
    """Returns the correct system prompt for the given language."""
    lang = language.lower().strip()
    prompt = _PROMPT_MAP.get(lang, _DEFAULT_PROMPT)
    return prompt.replace("{language}", language)


def _build_user_message(state: ProjectState, is_retry: bool) -> str:
    # get actual function name coder used
    function_name: str = state.get("function_name", "")

    import_line: str = (
        f"from solution import {function_name}"
        if function_name
        else "from solution import *"
    )

    if is_retry:
        return (
            f"The previous test cases were rejected.\n"
            f"Reason: {state.get('test_validation_reason', 'unknown')}\n\n"
            f"Rewrite better test cases for this problem:\n\n"
            f"Problem    : {state['question']}\n"
            f"Language   : {state['language']}\n"
            f"Import line: {import_line}\n"
            f"Function   : {function_name}\n\n"
            f"Write comprehensive test cases only — fix all issues mentioned above."
        )
    return (
        f"Write test cases for the following problem:\n\n"
        f"Problem    : {state['question']}\n"
        f"Language   : {state['language']}\n"
        f"Import line: {import_line}\n"
        f"Function   : {function_name}\n\n"
        f"Write comprehensive test cases only — do NOT write the solution.\n"
        f"Use exactly this import: {import_line}\n"
        f"Call the function as: {function_name}(...)"
    )


def _strip_code_fences(content: str) -> str:
    """Removes markdown code fences if the LLM added them."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(
            line for line in lines
            if not line.startswith("```")
        ).strip()
    return content


def tester_node(state: ProjectState) -> dict[str, Any]:
    """
    Generates test cases from the problem statement only.

    Key rules:
    - NEVER reads state['code'] — tests are independent of implementation
    - Uses language-aware prompts — Python gets pytest, Java gets JUnit etc.
    - On retry — injects validation failure reason so LLM knows what to fix
    """
    attempt: int   = state.get("test_attempts", 0) + 1
    is_retry: bool = attempt > 1
    language: str  = state.get("language", "python")

    print(f"[tester] attempt {attempt} — language: {language}")

    system_prompt: str = _get_system_prompt(language)
    user_message:  str = _build_user_message(state, is_retry)

    response: AIMessage = _llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ])

    generated_tests: str = _strip_code_fences(response.content)

    # save to workspace
    ext:       str = get_file_extension(language)
    test_file: str = f"workspace/test_solution{ext}"
    write_file.invoke({"file_path": test_file, "content": generated_tests})

    print(f"[tester] wrote {len(generated_tests)} chars to {test_file}")

    # extract token usage
    usage:      dict  = _tracker.call_breakdown[-1] if _tracker.call_breakdown else {}
    p:          int   = usage.get("prompt_tokens", 0)
    c:          int   = usage.get("output_tokens", 0)
    cost:       float = calculate_cost("gpt-4o-mini", p, c)

    return {
        "test_code":         generated_tests,
        "test_file":         test_file,
        "test_attempts":     attempt,
        "messages":          [response],
        "agent_notes":       [f"[tester] attempt {attempt} ({language}) — {len(generated_tests)} chars"],
        "prompt_tokens":     p,
        "completion_tokens": c,
        "total_cost_usd":    cost,
    }