import operator
from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ProjectState(TypedDict):
    """
    Shared state that flows through every node in the coding assistant graph.

    All agents read from this state.
    Each agent only writes to the fields it owns.
    """

    # ── Input ──────────────────────────────────────────────────────────────────
    question:   str    # user's coding problem
    language:   str    # programming language — defaults to "python"
    
    function_name: str

    # ── Supervisor routing ─────────────────────────────────────────────────────
    next:       str    # supervisor sets this — which node runs next

    # ── Conversation history ───────────────────────────────────────────────────
    messages:   Annotated[list[BaseMessage], add_messages]

    # ── Generated outputs ──────────────────────────────────────────────────────
    code:       str    # coder agent writes here
    test_code:  str    # tester agent writes here — never reads code

    # ── File paths ─────────────────────────────────────────────────────────────
    code_file:  str    # e.g. workspace/solution.py
    test_file:  str    # e.g. workspace/test_solution.py

    # ── Test validation ────────────────────────────────────────────────────────
    # supervisor validates test cases against the problem statement
    test_validation_status: str   # "valid" | "invalid"
    test_validation_reason: str   # why valid or invalid

    # ── Test execution ─────────────────────────────────────────────────────────
    test_results:   str    # stdout/stderr from pytest
    test_status:    str    # "pass" | "fail"

    # ── Retry counters ─────────────────────────────────────────────────────────
    code_attempts:  int    # how many times coder ran — max 3
    test_attempts:  int    # how many times tester ran — max 2

    # ── Agent notes — all agents append here ───────────────────────────────────
    agent_notes:    Annotated[list[str], operator.add]

    # ── Cost tracking — accumulates across all nodes ───────────────────────────
    prompt_tokens:     Annotated[int,   operator.add]
    completion_tokens: Annotated[int,   operator.add]
    total_cost_usd:    Annotated[float, operator.add]

    # ── Final output ───────────────────────────────────────────────────────────
    final_code:      str
    final_test_code: str
    is_solved:       bool
