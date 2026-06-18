import os
import sys
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from src.blog_generator.nodes import (
    aggregator_node,
    intake_node,
    output_node,
    researcher_node,
    reviewer_node,
    trend_finder_node,
)


def _base_state() -> dict[str, Any]:
    """Returns a clean initial state for tests."""
    return {
        "topic":           "LangGraph",
        "messages":        [],
        "research":        "",
        "trends":          "",
        "draft":           "",
        "review_feedback": "",
        "sources":         [],
        "iteration":       0,
        "final_post":      "",
    }


def test_intake_adds_system_and_human_message() -> None:
    state: dict[str, Any] = _base_state()
    result: dict[str, Any] = intake_node(state)
    assert "messages" in result
    assert len(result["messages"]) == 2


def test_researcher_returns_research_and_source() -> None:
    state: dict[str, Any] = _base_state()
    result: dict[str, Any] = researcher_node(state)
    assert "research" in result
    assert "sources" in result
    assert "researcher" in result["sources"]
    assert len(result["research"]) > 0


def test_trend_finder_returns_trends_and_source() -> None:
    state: dict[str, Any] = _base_state()
    result: dict[str, Any] = trend_finder_node(state)
    assert "trends" in result
    assert "sources" in result
    assert "trend_finder" in result["sources"]
    assert len(result["trends"]) > 0


def test_aggregator_produces_one_message() -> None:
    state: dict[str, Any] = _base_state()
    state["research"] = "Some research findings"
    state["trends"]   = "Some trend data"
    result: dict[str, Any] = aggregator_node(state)
    assert "messages" in result
    assert len(result["messages"]) == 1


def test_reviewer_approves_good_draft() -> None:
    state: dict[str, Any] = _base_state()
    # draft that passes all three checks: hashtags, length, emojis
    state["draft"] = "🚀 LangGraph is a game changer! " + "x" * 180 + " #AI #Python"
    result: dict[str, Any] = reviewer_node(state)
    assert result["review_feedback"] == "APPROVED"


def test_reviewer_rejects_short_draft() -> None:
    state: dict[str, Any] = _base_state()
    state["draft"] = "Too short"
    result: dict[str, Any] = reviewer_node(state)
    assert result["review_feedback"] != "APPROVED"


def test_output_stores_final_post() -> None:
    state: dict[str, Any] = _base_state()
    state["draft"]   = "Final approved LinkedIn post"
    state["sources"] = ["researcher"]
    result: dict[str, Any] = output_node(state)
    assert result["final_post"] == "Final approved LinkedIn post"
