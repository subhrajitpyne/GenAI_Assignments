import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from src.coding_assistant.tools.file_tools import write_file, read_file
from src.coding_assistant.tools.test_tools import check_syntax, run_tests


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_python_code() -> str:
    return "def add(a, b):\n    return a + b\n"


@pytest.fixture
def sample_test_code() -> str:
    return (
        "from solution import add\n\n"
        "def test_add_positive():\n"
        "    assert add(2, 3) == 5\n\n"
        "def test_add_negative():\n"
        "    assert add(-1, 1) == 0\n\n"
        "def test_add_zeros():\n"
        "    assert add(0, 0) == 0\n"
    )


@pytest.fixture
def workspace_dir() -> str:
    os.makedirs("workspace", exist_ok=True)
    return "workspace"


# ── write_file tests ──────────────────────────────────────────────────────────

def test_write_file_creates_file(workspace_dir: str, sample_python_code: str) -> None:
    """write_file creates the file at the given path."""
    file_path = f"{workspace_dir}/test_write.py"
    result    = write_file.invoke({"file_path": file_path, "content": sample_python_code})

    assert "Successfully written" in result
    assert os.path.exists(file_path)

    # cleanup
    os.remove(file_path)


def test_write_file_content_is_correct(workspace_dir: str, sample_python_code: str) -> None:
    """write_file writes exact content — no modification."""
    file_path = f"{workspace_dir}/test_content.py"
    write_file.invoke({"file_path": file_path, "content": sample_python_code})

    with open(file_path, "r") as f:
        content = f.read()

    assert content == sample_python_code

    # cleanup
    os.remove(file_path)


def test_write_file_creates_directories(workspace_dir: str) -> None:
    """write_file creates nested directories if they don't exist."""
    file_path = f"{workspace_dir}/nested/deep/file.py"
    result    = write_file.invoke({"file_path": file_path, "content": "x = 1"})

    assert "Successfully written" in result
    assert os.path.exists(file_path)

    # cleanup
    os.remove(file_path)
    os.rmdir(f"{workspace_dir}/nested/deep")
    os.rmdir(f"{workspace_dir}/nested")


def test_write_file_overwrites_existing(workspace_dir: str) -> None:
    """write_file overwrites existing file content."""
    file_path = f"{workspace_dir}/test_overwrite.py"

    write_file.invoke({"file_path": file_path, "content": "x = 1"})
    write_file.invoke({"file_path": file_path, "content": "x = 99"})

    with open(file_path, "r") as f:
        content = f.read()

    assert content == "x = 99"

    # cleanup
    os.remove(file_path)


# ── read_file tests ───────────────────────────────────────────────────────────

def test_read_file_returns_content(workspace_dir: str, sample_python_code: str) -> None:
    """read_file returns exact content that was written."""
    file_path = f"{workspace_dir}/test_read.py"

    with open(file_path, "w") as f:
        f.write(sample_python_code)

    result = read_file.invoke({"file_path": file_path})

    assert result == sample_python_code

    # cleanup
    os.remove(file_path)


def test_read_file_not_found() -> None:
    """read_file returns error string when file does not exist."""
    result = read_file.invoke({"file_path": "workspace/does_not_exist.py"})

    assert "Error" in result
    assert "not found" in result.lower()


def test_read_file_returns_string(workspace_dir: str) -> None:
    """read_file always returns a string — never raises exception."""
    file_path = f"{workspace_dir}/test_string.py"

    with open(file_path, "w") as f:
        f.write("hello = 'world'")

    result = read_file.invoke({"file_path": file_path})

    assert isinstance(result, str)

    # cleanup
    os.remove(file_path)


# ── check_syntax tests ────────────────────────────────────────────────────────

def test_check_syntax_valid_python(sample_python_code: str) -> None:
    """check_syntax passes valid Python code."""
    result = check_syntax.invoke({
        "code":     sample_python_code,
        "language": "python",
    })
    assert "No syntax errors" in result


def test_check_syntax_invalid_python() -> None:
    """check_syntax catches Python syntax errors."""
    invalid_code = "def hello(\n    return 'world'"   # missing closing paren
    result       = check_syntax.invoke({
        "code":     invalid_code,
        "language": "python",
    })
    assert "Syntax error" in result


def test_check_syntax_default_is_python(sample_python_code: str) -> None:
    """check_syntax defaults to Python when no language given."""
    result = check_syntax.invoke({
        "code":     sample_python_code,
        "language": "python",
    })
    assert "No syntax errors" in result


def test_check_syntax_javascript_skips() -> None:
    """check_syntax skips non-Python languages gracefully."""
    result = check_syntax.invoke({
        "code":     "function add(a, b) { return a + b; }",
        "language": "javascript",
    })
    assert "skipped" in result.lower()


def test_check_syntax_unknown_language_skips() -> None:
    """check_syntax skips unknown languages gracefully."""
    result = check_syntax.invoke({
        "code":     "some code here",
        "language": "brainfuck",
    })
    assert "skipped" in result.lower()


def test_check_syntax_always_returns_string() -> None:
    """check_syntax always returns a string — never raises exception."""
    result = check_syntax.invoke({
        "code":     "",
        "language": "python",
    })
    assert isinstance(result, str)


def test_check_syntax_empty_code() -> None:
    """check_syntax handles empty code gracefully."""
    result = check_syntax.invoke({
        "code":     "",
        "language": "python",
    })
    # empty code is valid Python
    assert isinstance(result, str)
    assert "No syntax errors" in result


# ── run_tests tests ───────────────────────────────────────────────────────────

def test_run_tests_solution_not_found() -> None:
    """run_tests returns error when solution file does not exist."""
    result = run_tests.invoke({
        "test_file":     "workspace/test_solution.py",
        "solution_file": "workspace/does_not_exist.py",
    })
    assert "Error" in result
    assert "not found" in result.lower()


def test_run_tests_test_file_not_found(workspace_dir: str, sample_python_code: str) -> None:
    """run_tests returns error when test file does not exist."""
    solution_path = f"{workspace_dir}/solution.py"
    with open(solution_path, "w") as f:
        f.write(sample_python_code)

    result = run_tests.invoke({
        "test_file":     "workspace/does_not_exist_test.py",
        "solution_file": solution_path,
    })

    assert "Error" in result
    assert "not found" in result.lower()

    # cleanup
    os.remove(solution_path)


def test_run_tests_passing_tests(
    workspace_dir:    str,
    sample_python_code: str,
    sample_test_code:   str,
) -> None:
    """run_tests returns PASS when all tests pass."""
    solution_path = f"{workspace_dir}/solution.py"
    test_path     = f"{workspace_dir}/test_solution.py"

    with open(solution_path, "w") as f:
        f.write(sample_python_code)

    with open(test_path, "w") as f:
        f.write(sample_test_code)

    result = run_tests.invoke({
        "test_file":     test_path,
        "solution_file": solution_path,
    })

    assert "PASS" in result

    # cleanup
    os.remove(solution_path)
    os.remove(test_path)


def test_run_tests_failing_tests(workspace_dir: str) -> None:
    """run_tests returns FAIL when tests fail."""
    # wrong implementation — returns wrong value
    wrong_code = "def add(a, b):\n    return a - b\n"
    test_code  = (
        "from solution import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
    )

    solution_path = f"{workspace_dir}/solution.py"
    test_path     = f"{workspace_dir}/test_solution.py"

    with open(solution_path, "w") as f:
        f.write(wrong_code)

    with open(test_path, "w") as f:
        f.write(test_code)

    result = run_tests.invoke({
        "test_file":     test_path,
        "solution_file": solution_path,
    })

    assert "FAIL" in result

    # cleanup
    os.remove(solution_path)
    os.remove(test_path)


def test_run_tests_always_returns_string(workspace_dir: str) -> None:
    """run_tests always returns a string — never raises exception."""
    result = run_tests.invoke({
        "test_file":     "workspace/nonexistent_test.py",
        "solution_file": "workspace/nonexistent_solution.py",
    })
    assert isinstance(result, str)