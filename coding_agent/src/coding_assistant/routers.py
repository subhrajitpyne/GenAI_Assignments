from typing import Literal
from .state import ProjectState


def orchestrator_router(
    state: ProjectState,
) -> Literal["coder", "tester", "validate_tests", "runner", "output"]:
    """
    Routes from orchestrator to the correct next node.
    Reads state['next'] which the orchestrator set.
    """
    return state["next"]


def test_validation_router(
    state: ProjectState,
) -> Literal["runner", "tester"]:
    """
    After validator runs — route based on validation result.
    valid   → run tests against code
    invalid → regenerate test cases (if attempts remain)
    """
    status: str      = state.get("test_validation_status", "invalid")
    test_attempts: int = state.get("test_attempts", 0)

    if status == "valid":
        return "runner"

    # invalid tests — regenerate if attempts remain
    if test_attempts < 2:
        return "tester"

    # max test attempts reached — run anyway, let runner report failure
    print("[router] max test attempts reached — running tests anyway")
    return "runner"


def test_result_router(
    state: ProjectState,
) -> Literal["output", "coder"]:
    test_status:   str = state.get("test_status",   "fail")
    code_attempts: int = state.get("code_attempts", 0)

    if test_status == "pass":
        print("[router] tests passed → output")
        return "output"

    if code_attempts < 5:    # ← change 3 to 5
        print(f"[router] tests failed → coder (attempt {code_attempts + 1})")
        return "coder"

    print("[router] max code attempts reached → output")
    return "output"
