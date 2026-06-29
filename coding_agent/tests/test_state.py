import os
import sys
import operator
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from src.coding_assistant.state import ProjectState


def test_state_has_required_fields() -> None:
    """ProjectState TypedDict contains all required fields."""
    fields = ProjectState.__annotations__.keys()
    required = [
        "question", "language", "next", "messages",
        "code", "test_code", "code_file", "test_file",
        "test_validation_status", "test_validation_reason",
        "test_results", "test_status",
        "code_attempts", "test_attempts",
        "agent_notes", "prompt_tokens", "completion_tokens",
        "total_cost_usd", "final_code", "final_test_code", "is_solved",
    ]
    for field in required:
        assert field in fields, f"Missing field: {field}"


def test_operator_add_accumulates_integers() -> None:
    """operator.add reducer correctly accumulates integers."""
    result = operator.add(10, 5)
    assert result == 15


def test_operator_add_accumulates_floats() -> None:
    """operator.add reducer correctly accumulates floats."""
    result = operator.add(0.001, 0.002)
    assert round(result, 6) == 0.003


def test_operator_add_accumulates_lists() -> None:
    """operator.add reducer correctly appends lists."""
    existing = ["note 1"]
    new      = ["note 2"]
    result   = operator.add(existing, new)
    assert result == ["note 1", "note 2"]
