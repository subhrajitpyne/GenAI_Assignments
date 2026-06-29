from langgraph.graph import StateGraph, END, START
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import InMemorySaver

from .state import ProjectState
from .agents import (
    orchestrator_node,
    coder_node,
    tester_node,
    validator_node,
    runner_node,
    output_node,
)
from .routers import (
    orchestrator_router,
    test_validation_router,
    test_result_router,
    post_coder_router,          # ← import new router
)


def build_graph() -> CompiledStateGraph:
    """
    Assembles the full coding assistant graph.

    Flow:
    START → orchestrator → (coder + tester in parallel) →
    orchestrator → validator → (runner or tester) →
    runner → (coder or output)
    """
    builder = StateGraph(ProjectState)

    # ── Register all nodes ────────────────────────────────────────────────────
    builder.add_node("orchestrator",    orchestrator_node)
    builder.add_node("coder",           coder_node)
    builder.add_node("tester",          tester_node)
    builder.add_node("validate_tests",  validator_node)
    builder.add_node("runner",          runner_node)
    builder.add_node("output",          output_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    builder.add_edge(START, "orchestrator")

    # ── Orchestrator routes to any node ───────────────────────────────────────
    builder.add_conditional_edges(
        "orchestrator",
        orchestrator_router,
        {
            "coder":          "coder",
            "tester":         "tester",
            "validate_tests": "validate_tests",
            "runner":         "runner",
            "output":         "output",
        },
    )

    # ── Coder and tester both report back to orchestrator ─────────────────────
    builder.add_edge("coder",  "orchestrator")
    builder.add_edge("tester", "orchestrator")

    # ── After validation — run tests or regenerate test cases ─────────────────
    builder.add_conditional_edges(
        "validate_tests",
        test_validation_router,
        {
            "runner": "runner",
            "tester": "tester",
        },
    )

    # ── After tests run — fix code or finish ──────────────────────────────────
    builder.add_conditional_edges(
        "runner",
        test_result_router,
        {
            "coder":  "coder",
            "output": "output",
        },
    )

    # ── Output ends the graph ─────────────────────────────────────────────────
    builder.add_edge("output", END)

    return builder.compile(checkpointer=InMemorySaver())


# compiled graph — import this anywhere
graph: CompiledStateGraph = build_graph()
