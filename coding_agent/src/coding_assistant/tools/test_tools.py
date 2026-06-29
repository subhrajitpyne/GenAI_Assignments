import ast
import os
import subprocess
from langchain_core.tools import tool


@tool
def check_syntax(code: str, language: str = "python") -> str:
    """
    Check code for syntax errors.
    Python uses built-in ast.parse().
    All other languages are skipped — the test runner will catch errors.
    Returns 'No syntax errors found' or a description of the error.
    """
    language = language.lower().strip()

    if language == "python":
        try:
            ast.parse(code)
            return "No syntax errors found"
        except SyntaxError as e:
            return (
                f"Syntax error on line {e.lineno}: {e.msg}\n"
                f"Text: {e.text}"
            )
        except Exception as e:
            return f"Error during syntax check: {str(e)}"

    # non-Python — skip and let the test runner catch it
    return f"Syntax check skipped for '{language}' — test runner will catch errors"


@tool
def run_tests(test_file: str, solution_file: str) -> str:
    """
    Run pytest on the test file against the solution file.
    Both files must exist in the workspace directory.
    Returns the full pytest output including pass/fail status and any errors.
    """
    if not os.path.exists(solution_file):
        return f"Error: Solution file not found at {solution_file}"

    if not os.path.exists(test_file):
        return f"Error: Test file not found at {test_file}"

    try:
        result = subprocess.run(
            [
                "pytest",
                test_file,
                "-v",
                "--tb=short",
                "--no-header",
                "-p", "no:warnings",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output: str = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"

        if result.returncode == 0:
            output += "\n\nRESULT: PASS"
        else:
            output += "\n\nRESULT: FAIL"

        return output

    except subprocess.TimeoutExpired:
        return "Error: Tests timed out after 30 seconds — possible infinite loop in generated code"

    except FileNotFoundError:
        return "Error: pytest not found — make sure pytest is installed in your environment"

    except Exception as e:
        return f"Error running tests: {str(e)}"


# export
test_tools: list = [check_syntax, run_tests]
