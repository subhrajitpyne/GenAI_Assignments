from typing import Literal
from .state import ProjectState


def orchestrator_router(
    state: ProjectState,
) -> Literal["coder", "tester", "validate_tests", "runner", "output"]:
    """
    Routes from orchestrator to the correct next node.
    Reads state['next'] which the orchestrator set.
    """
    next_node: str = state.get("next", "output")
    print(f"[router] orchestrator → {next_node}", flush=True)
    return next_node


def test_validation_router(
    state: ProjectState,
) -> Literal["runner", "tester"]:
    """
    After validator runs:
    valid        → run tests against code
    invalid      → regenerate test cases if attempts remain
    max attempts → run anyway, let runner report failure
    """
    status:        str = state.get("test_validation_status", "invalid")
    test_attempts: int = state.get("test_attempts", 0)

    if status == "valid":
        print("[router] tests valid → runner", flush=True)
        return "runner"

    if test_attempts < 2:
        print(f"[router] tests invalid → tester (attempt {test_attempts + 1})", flush=True)
        return "tester"

    # max test attempts reached — run anyway
    print("[router] max test attempts reached — running tests anyway", flush=True)
    return "runner"


def test_result_router(
    state: ProjectState,
) -> Literal["output", "coder", "runner"]:
    """
    After runner executes tests:
    pass             → output (done)
    fail + attempts  → coder (fix the code)
    fail + max       → output (give up, report failure)

    CRITICAL: After coder fixes code — ALWAYS go back to runner.
    The orchestrator handles coder → runner routing via state['next'].
    This router handles runner → coder → runner cycle.
    """
    test_status:   str = state.get("test_status",   "fail")
    code_attempts: int = state.get("code_attempts", 0)

    if test_status == "pass":
        print("[router] ✅ tests passed → output", flush=True)
        return "output"

    if code_attempts < 5:
        print(f"[router] ❌ tests failed → coder (attempt {code_attempts + 1})", flush=True)
        return "coder"

    print("[router] max code attempts reached → output", flush=True)
    return "output"


def post_coder_router(
    state: ProjectState,
) -> Literal["runner", "output"]:
    """
    After coder runs following a test failure —
    ALWAYS go back to runner to re-execute tests.
    Never skip runner after a retry.
    """
    code_attempts: int = state.get("code_attempts", 0)

    if code_attempts >= 5:
        print("[router] max code attempts → output", flush=True)
        return "output"

    print(f"[router] coder done → runner (re-testing attempt {code_attempts})", flush=True)
    return "runner"