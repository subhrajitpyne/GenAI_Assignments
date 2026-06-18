from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .nodes import (
    aggregator_node,
    intake_node,
    output_node,
    researcher_node,
    reviewer_node,
    tool_node,
    trend_finder_node,
    writer_node,
)
from .state import BlogState


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def writer_router(state: BlogState) -> Literal["tools", "reviewer"]:
    """
    After the writer runs:
    - if the LLM emitted tool_calls  → execute the tools
    - otherwise                      → send the draft to the reviewer
    """
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "reviewer"


def review_router(state: BlogState) -> Literal["writer", "output"]:
    """
    After the reviewer runs:
    - if approved or max iterations hit → finish
    - otherwise                         → send back to writer for revision
    """
    approved: bool      = state.get("review_feedback") == "APPROVED"
    max_reached: bool   = state.get("iteration", 0) >= 3
    if approved or max_reached:
        return "output"
    return "writer"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph() -> CompiledStateGraph:
    builder: StateGraph = StateGraph(BlogState)

    # register all nodes
    builder.add_node("intake",       intake_node)
    builder.add_node("researcher",   researcher_node)
    builder.add_node("trend_finder", trend_finder_node)
    builder.add_node("aggregator",   aggregator_node)
    builder.add_node("writer",       writer_node)
    builder.add_node("reviewer",     reviewer_node)
    builder.add_node("tools",        tool_node)
    builder.add_node("output",       output_node)

    # entry point
    builder.add_edge(START, "intake")

    # parallel fan-out — researcher and trend_finder run simultaneously
    builder.add_edge("intake", "researcher")
    builder.add_edge("intake", "trend_finder")

    # fan-in — aggregator waits for both parallel nodes to finish
    builder.add_edge("researcher",   "aggregator")
    builder.add_edge("trend_finder", "aggregator")

    # linear: aggregator feeds the writer
    builder.add_edge("aggregator", "writer")

    # conditional: writer → tools (ReAct) or reviewer
    builder.add_conditional_edges(
        "writer",
        writer_router,
        {"tools": "tools", "reviewer": "reviewer"},
    )

    # ReAct loopback — tool results go back to writer
    builder.add_edge("tools", "writer")

    # conditional: reviewer → writer (Reflection) or output
    builder.add_conditional_edges(
        "reviewer",
        review_router,
        {"writer": "writer", "output": "output"},
    )

    builder.add_edge("output", END)

    return builder.compile()


# compiled graph — imported by routes.py
graph: CompiledStateGraph = build_graph()
