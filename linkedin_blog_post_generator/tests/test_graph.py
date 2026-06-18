import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from langgraph.graph.state import CompiledStateGraph

from src.blog_generator.graph import build_graph


def test_graph_compiles_without_error() -> None:
    graph: CompiledStateGraph = build_graph()
    assert graph is not None


def test_graph_contains_all_expected_nodes() -> None:
    graph: CompiledStateGraph = build_graph()
    nodes: list[str] = list(graph.nodes.keys())
    expected: list[str] = [
        "intake", "researcher", "trend_finder",
        "aggregator", "writer", "reviewer", "tools", "output",
    ]
    for node in expected:
        assert node in nodes, f"Missing node: {node}"


def test_mermaid_diagram_generates() -> None:
    graph: CompiledStateGraph = build_graph()
    mermaid: str = graph.get_graph().draw_mermaid()
    # key nodes should appear in the diagram
    for node in ("intake", "writer", "reviewer", "output"):
        assert node in mermaid, f"Node '{node}' missing from Mermaid output"
