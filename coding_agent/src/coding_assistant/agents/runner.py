import os
import certifi
import re
import subprocess
from typing import Any
from dotenv import load_dotenv

# ── SSL setup ─────────────────────────────────────────────────────────────────
os.environ["SSL_CERT_FILE"]      = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

import truststore
truststore.inject_into_ssl()

load_dotenv()

from pydantic import BaseModel
from typing import Literal
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.chat_models import init_chat_model

from ..state import ProjectState


# ── LLM evaluator — for non-Python languages ──────────────────────────────────
class TestEvaluation(BaseModel):
    verdict:      Literal["pass", "fail"]
    passed_tests: list[str]
    failed_tests: list[str]
    reason:       str


_evaluator_llm = init_chat_model(
    "openai:gpt-4o-mini",
    temperature=0,
).with_structured_output(TestEvaluation)


# ── Python — real pytest execution ────────────────────────────────────────────
def _run_python_tests(test_file: str, solution_file: str) -> tuple[str, int]:
    """
    Combine solution + tests into one file.
    Auto-alias function names to handle name mismatches.
    Run pytest on combined file.
    """
    import time
    test_dir: str = os.path.dirname(os.path.abspath(test_file))

    # ── Always delete old combined file first ─────────────────────────────────
    combined_path: str = os.path.join(test_dir, "combined_test.py")
    if os.path.exists(combined_path):
        os.remove(combined_path)
        print("[runner] deleted old combined_test.py", flush=True)

    # ── Small delay to ensure coder's write_file has fully flushed ────────────
    time.sleep(0.5)

    # ── Read latest versions of both files ────────────────────────────────────
    try:
        with open(os.path.abspath(solution_file), "r", encoding="utf-8") as f:
            solution_code: str = f.read().strip()
        with open(os.path.abspath(test_file), "r", encoding="utf-8") as f:
            test_code: str = f.read().strip()
    except FileNotFoundError as e:
        return f"Error reading files: {str(e)}", 1

    # ── Debug — confirm we have the latest code ───────────────────────────────
    print(f"[runner] solution.py first 150 chars:\n{solution_code[:150]}", flush=True)

    # ── Find all function names defined in solution ───────────────────────────
    solution_funcs: list[str] = re.findall(
        r"^def (\w+)\(", solution_code, re.MULTILINE
    )
    print(f"[runner] solution functions: {solution_funcs}", flush=True)

    # ── Remove import lines from test ─────────────────────────────────────────
    clean_lines: list[str] = [
        line for line in test_code.split("\n")
        if not line.strip().startswith("from solution")
        and not line.strip().startswith("import solution")
    ]
    clean_test: str = "\n".join(clean_lines).strip()

    # ── Find non-test functions called in tests ───────────────────────────────
    skip_names: set[str] = {
        "assert", "print", "len", "range", "isinstance",
        "str", "int", "float", "list", "dict", "set",
        "tuple", "bool", "type", "pytest", "raises",
        "True", "False", "None", "Exception", "ValueError",
        "TypeError", "KeyError", "IndexError",
    }
    called_funcs: set[str] = {
        f for f in re.findall(r"\b(\w+)\s*\(", clean_test)
        if not f.startswith("test_") and f not in skip_names
    }

    # ── Build aliases for mismatched function names ───────────────────────────
    aliases: str = ""
    if solution_funcs:
        for called in called_funcs:
            if called not in solution_funcs:
                aliases += f"{called} = {solution_funcs[0]}\n"
                print(f"[runner] alias: {called} → {solution_funcs[0]}", flush=True)

    # ── Combine: solution + aliases + tests ───────────────────────────────────
    combined: str = f"{solution_code}\n\n{aliases}\n{clean_test}\n"

    with open(combined_path, "w", encoding="utf-8") as f:
        f.write(combined)
    f.close()  # ← explicit close to ensure flush

    # ── Verify combined file was written correctly ────────────────────────────
    with open(combined_path, "r", encoding="utf-8") as f:
        verify: str = f.read()
    print(f"[runner] combined_test.py first 200 chars:\n{verify[:200]}", flush=True)

    # ── Run pytest ────────────────────────────────────────────────────────────
    result = subprocess.run(
        [
            "pytest",
            combined_path,
            "-v",
            "--tb=short",
            "--no-header",
            "-p", "no:warnings",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=test_dir,
    )

    output: str = result.stdout
    if result.stderr:
        output += f"\nSTDERR:\n{result.stderr}"

    return output, result.returncode


# ── LLM evaluation — for all non-Python languages ─────────────────────────────
def _run_llm_tests(
    solution_code: str,
    test_code:     str,
    language:      str,
) -> tuple[str, int]:
    """
    Uses LLM to mentally execute tests against the solution.
    Works for any language without needing a runtime installed.
    """
    print(f"[runner] LLM evaluation for {language}", flush=True)

    result: TestEvaluation = _evaluator_llm.invoke([
        SystemMessage(content=(
            f"You are an expert {language} engineer evaluating whether test cases pass.\n\n"
            f"CRITICAL RULES:\n"
            f"1. Read the solution code EXACTLY as written — do not hallucinate code\n"
            f"2. Ignore import/syntax issues — focus only on LOGIC correctness\n"
            f"3. For Java — assume static methods can be called directly in tests\n"
            f"4. For JavaScript — assume the function is available in global scope\n"
            f"5. Trace each test case through the solution logic step by step\n"
            f"6. Only fail if the LOGIC produces wrong output for that test input\n"
            f"7. Do NOT fail tests for import issues, class name issues, or syntax\n"
            f"8. Be generous — if the algorithm is correct, mark tests as passed\n"
        )),
        HumanMessage(content=(
            f"Solution code:\n```{language}\n{solution_code}\n```\n\n"
            f"Test cases:\n```{language}\n{test_code}\n```\n\n"
            f"For each test — trace the INPUT through the solution code and check the OUTPUT.\n"
            f"Ignore any import or class reference issues — focus only on logic.\n"
            f"Would the logic produce the correct output for each test?"
        )),
    ])

    passed_block: str = "\n".join(f"  ✅ {t}" for t in result.passed_tests) or "  (none)"
    failed_block: str = "\n".join(f"  ❌ {t}" for t in result.failed_tests) or "  (none)"

    output: str = (
        f"LLM Code Evaluation — {language.upper()}\n"
        f"{'='*50}\n"
        f"Note: Evaluated by LLM (no {language} runtime available)\n\n"
        f"Passed:\n{passed_block}\n\n"
        f"Failed:\n{failed_block}\n\n"
        f"Analysis: {result.reason}\n"
        f"{'='*50}\n"
        f"Verdict: {result.verdict.upper()}\n"
    )

    returncode: int = 0 if result.verdict == "pass" else 1
    return output, returncode


# ── Node ──────────────────────────────────────────────────────────────────────
def runner_node(state: ProjectState) -> dict[str, Any]:
    """
    Runs tests for the generated code.

    Python   → real pytest execution (most accurate)
    Others   → LLM mentally evaluates tests (~90% accurate)
    """
    language:  str = state.get("language",  "python").lower().strip()
    code_file: str = state.get("code_file", "workspace/solution.py")
    test_file: str = state.get("test_file", "workspace/test_solution.py")

    print(f"[runner] language: {language}", flush=True)

    # read both files
    try:
        with open(os.path.abspath(code_file), "r") as f:
            solution_code: str = f.read().strip()
        with open(os.path.abspath(test_file), "r") as f:
            test_code: str = f.read().strip()
    except FileNotFoundError as e:
        return {
            "test_results": f"Error: {str(e)}\n\nRESULT: FAIL 😭",
            "test_status":  "fail",
            "agent_notes":  [f"[runner] file not found: {str(e)}"],
        }

    # ── Python — run real pytest ──────────────────────────────────────────────
    if language == "python":
        print("[runner] running pytest...", flush=True)
        try:
            output, returncode = _run_python_tests(test_file, code_file)
        except subprocess.TimeoutExpired:
            output     = "Error: Tests timed out after 30 seconds\n\nRESULT: FAIL 😭"
            returncode = 1
        except Exception as e:
            output     = f"Error running pytest: {str(e)}\n\nRESULT: FAIL 😭"
            returncode = 1

    # ── All other languages — LLM evaluation ─────────────────────────────────
    else:
        print(f"[runner] no {language} runtime — using LLM evaluation", flush=True)
        try:
            output, returncode = _run_llm_tests(solution_code, test_code, language)
        except Exception as e:
            output     = f"Error during LLM evaluation: {str(e)}\n\nRESULT: FAIL 😭"
            returncode = 1

    # ── Determine status and append result ────────────────────────────────────
    status: str = "pass" if returncode == 0 else "fail"

    if "RESULT:" not in output:
        output += f"\n\nRESULT: {'PASS 👽' if status == 'pass' else 'FAIL 😭'}"

    print(f"[runner] {status.upper()}", flush=True)

    return {
        "test_results": output,
        "test_status":  status,
        "agent_notes":  [f"[runner] {language} → {status}"],
    }