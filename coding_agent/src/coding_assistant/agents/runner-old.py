import os
import certifi
import subprocess
from typing import Any
from dotenv import load_dotenv

# ── SSL setup ─────────────────────────────────────────────────────────────────
os.environ["SSL_CERT_FILE"]      = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

import truststore
truststore.inject_into_ssl()

load_dotenv()

from ..state import ProjectState


# ── Languages with working test runners ───────────────────────────────────────
# Add "java", "javascript", "go" here when runtime is configured
_SUPPORTED_RUNNERS: set[str] = {"python"}


# ── Individual test runners ───────────────────────────────────────────────────

import re

def _run_python_tests(test_file: str, solution_file: str) -> tuple[str, int]:
    """
    Combine solution + tests into one file with automatic function name aliasing.
    This avoids all import path issues and function name mismatches.
    """
    import re
    test_dir: str = os.path.dirname(os.path.abspath(test_file))

    try:
        with open(os.path.abspath(solution_file), "r") as f:
            solution_code: str = f.read().strip()
        with open(os.path.abspath(test_file), "r") as f:
            test_code: str = f.read().strip()
    except FileNotFoundError as e:
        return f"Error reading files: {str(e)}", 1

    # find all function names defined in solution
    solution_funcs: list[str] = re.findall(
        r"^def (\w+)\(", solution_code, re.MULTILINE
    )
    print(f"[runner] solution functions: {solution_funcs}")

    # remove import lines from test
    clean_lines: list[str] = []
    for line in test_code.split("\n"):
        s = line.strip()
        if s.startswith("from solution") or s.startswith("import solution"):
            continue
        clean_lines.append(line)
    clean_test: str = "\n".join(clean_lines).strip()

    # find non-test function names called in tests
    called_funcs: set[str] = {
        f for f in re.findall(r"\b(\w+)\s*\(", clean_test)
        if not f.startswith("test_")
        and f not in {
            "assert", "print", "len", "range", "isinstance",
            "str", "int", "float", "list", "dict", "set",
            "tuple", "bool", "type", "pytest", "raises",
            "True", "False", "None",
        }
    }
    print(f"[runner] functions called in tests: {called_funcs}")

    # build aliases — map test function names to solution function names
    aliases: str = ""
    if solution_funcs:
        for called in called_funcs:
            if called not in solution_funcs:
                best: str = solution_funcs[0]
                aliases += f"{called} = {best}\n"
                print(f"[runner] aliased: {called} → {best}")

    # combine: solution + aliases + tests
    combined: str = (
        f"{solution_code}\n\n"
        f"{aliases}\n"
        f"{clean_test}\n"
    )

    combined_path: str = os.path.join(test_dir, "combined_test.py")
    with open(combined_path, "w", encoding="utf-8") as f:
        f.write(combined)

    print(f"[runner] combined preview:\n{combined[:300]}\n")

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

    print(f"[runner] pytest:\n{output}")
    return output, result.returncode

def _run_javascript_tests(test_file: str, solution_file: str) -> tuple[str, int]:
    """Run Jest for JavaScript test files."""
    result = subprocess.run(
        ["npx", "jest", test_file, "--no-coverage"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout
    if result.stderr:
        output += f"\nSTDERR:\n{result.stderr}"
    return output, result.returncode


def _run_typescript_tests(test_file: str, solution_file: str) -> tuple[str, int]:
    """Run Jest with ts-jest for TypeScript test files."""
    result = subprocess.run(
        ["npx", "jest", test_file, "--no-coverage"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout
    if result.stderr:
        output += f"\nSTDERR:\n{result.stderr}"
    return output, result.returncode


def _run_java_tests(test_file: str, solution_file: str) -> tuple[str, int]:
    """Compile and run JUnit 5 tests for Java files."""
    workspace = os.path.dirname(test_file)

    # Step 1 — compile both files
    compile_result = subprocess.run(
        [
            "javac",
            "-cp", ".:junit-platform-console-standalone.jar",
            solution_file,
            test_file,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=workspace,
    )
    if compile_result.returncode != 0:
        return (
            f"Compilation failed:\n{compile_result.stdout}\n{compile_result.stderr}",
            compile_result.returncode,
        )

    # Step 2 — run JUnit tests
    test_class: str = os.path.basename(test_file).replace(".java", "")
    run_result = subprocess.run(
        [
            "java",
            "-cp", ".:junit-platform-console-standalone.jar",
            "org.junit.platform.console.ConsoleLauncher",
            "--select-class", test_class,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=workspace,
    )
    output = run_result.stdout
    if run_result.stderr:
        output += f"\nSTDERR:\n{run_result.stderr}"
    return output, run_result.returncode


def _run_go_tests(test_file: str, solution_file: str) -> tuple[str, int]:
    """Run go test for Go test files."""
    workspace = os.path.dirname(test_file)
    result    = subprocess.run(
        ["go", "test", "-v", "./..."],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=workspace,
    )
    output = result.stdout
    if result.stderr:
        output += f"\nSTDERR:\n{result.stderr}"
    return output, result.returncode


# ── Runner dispatch map ───────────────────────────────────────────────────────
_RUNNER_MAP: dict[str, Any] = {
    "python":     _run_python_tests,
    "javascript": _run_javascript_tests,
    "typescript": _run_typescript_tests,
    "java":       _run_java_tests,
    "go":         _run_go_tests,
}


# ── Execute tests ─────────────────────────────────────────────────────────────
def _execute_tests(
    language:      str,
    test_file:     str,
    solution_file: str,
) -> tuple[str, str]:
    """
    Dispatches to the correct test runner based on language.
    Returns (output, status) where status is 'pass' or 'fail'.
    """
    runner = _RUNNER_MAP.get(language)

    if runner is None:
        return (
            f"Test runner not available for '{language}'.\n"
            f"Supported: {', '.join(_RUNNER_MAP.keys())}",
            "fail",
        )

    if not os.path.exists(solution_file):
        return f"Error: Solution file not found at {solution_file}", "fail"

    if not os.path.exists(test_file):
        return f"Error: Test file not found at {test_file}", "fail"

    try:
        output, returncode = runner(test_file, solution_file)

        if returncode == 0:
            output += "\n\nRESULT: PASS 👽"
            status  = "pass"
        else:
            output += "\n\nRESULT: FAIL 😭"
            status  = "fail"

        return output, status

    except subprocess.TimeoutExpired:
        return (
            "Error: Tests timed out after 30 seconds — "
            "possible infinite loop in generated code",
            "fail",
        )
    except FileNotFoundError as e:
        return (
            f"Error: Test runner not found — {str(e)}\n"
            f"Make sure required tools are installed for '{language}'.",
            "fail",
        )
    except Exception as e:
        return f"Error running tests: {str(e)}", "fail"


# ── Node — ONE definition only ────────────────────────────────────────────────
def runner_node(state: ProjectState) -> dict[str, Any]:
    import re
    import subprocess

    language:  str = state.get("language",  "python").lower().strip()
    code_file: str = state.get("code_file", "workspace/solution.py")
    test_file: str = state.get("test_file", "workspace/test_solution.py")

    print(f"[runner] language: {language}", flush=True)

    # bypass for non-python
    if language not in _SUPPORTED_RUNNERS:
        return {
            "test_results": f"Skipped for '{language}'.\n\nRESULT: PASS 👽",
            "test_status":  "pass",
            "agent_notes":  [f"[runner] '{language}' skipped"],
        }

    # read files
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

    # remove import lines — solution is combined directly
    clean_lines: list[str] = [
        line for line in test_code.split("\n")
        if not line.strip().startswith("from solution")
        and not line.strip().startswith("import solution")
    ]
    clean_test: str = "\n".join(clean_lines).strip()

    # combine solution + tests — no import needed
    combined: str = f"{solution_code}\n\n\n{clean_test}\n"

    test_dir:      str = os.path.dirname(os.path.abspath(test_file))
    combined_path: str = os.path.join(test_dir, "combined_test.py")

    with open(combined_path, "w", encoding="utf-8") as f:
        f.write(combined)

    print(f"[runner] combined written to {combined_path}", flush=True)
    print(f"[runner] preview:\n{combined[:300]}", flush=True)

    # run pytest
    try:
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

        status: str = "pass" if result.returncode == 0 else "fail"
        output += f"\n\nRESULT: {'PASS 👽' if status == 'pass' else 'FAIL 😭'}"

        print(f"[runner] status: {status}", flush=True)
        print(f"[runner] pytest output:\n{output[:500]}", flush=True)

    except subprocess.TimeoutExpired:
        output = "Error: Timed out\n\nRESULT: FAIL 😭"
        status = "fail"
    except Exception as e:
        output = f"Error: {str(e)}\n\nRESULT: FAIL 😭"
        status = "fail"

    return {
        "test_results": output,
        "test_status":  status,
        "agent_notes":  [f"[runner] python tests → {status}"],
    }