import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from langgraph.graph.state import CompiledStateGraph
from src.coding_assistant.graph import build_graph


def test_graph_compiles() -> None:
    """Graph compiles without errors."""
    graph = build_graph()
    assert graph is not None
    assert isinstance(graph, CompiledStateGraph)


def test_graph_has_all_nodes() -> None:
    """Graph contains all expected nodes."""
    graph    = build_graph()
    nodes    = list(graph.nodes.keys())
    expected = [
        "orchestrator",
        "coder",
        "tester",
        "validate_tests",
        "runner",
        "output",
    ]
    for node in expected:
        assert node in nodes, f"Missing node: {node}"


def test_graph_mermaid_renders() -> None:
    """Graph can generate a Mermaid diagram."""
    graph   = build_graph()
    mermaid = graph.get_graph().draw_mermaid()
    assert "orchestrator" in mermaid
    assert "coder"        in mermaid
    assert "tester"       in mermaid
    assert "output"       in mermaid
