from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langgraph.prebuilt import ToolNode

from .state import BlogState
from .tools import tools

from dotenv import load_dotenv

import os,certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

#Uses windows trusted certs from truststore
import truststore
truststore.inject_into_ssl()

load_dotenv()
# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------

_model: BaseChatModel = init_chat_model(
    "openai:gpt-4o-mini",
    temperature=0.7,
    max_tokens=1000,
)

llm_with_tools: Runnable = _model.bind_tools(tools)

_SYSTEM_PROMPT: str = (
    "You are a professional LinkedIn content creator. "
    "Write engaging, insightful posts with emojis and relevant hashtags. "
    "Posts must be at least 200 characters. "
    "Use tools to get hashtags and emoji suggestions when needed. "
    "Structure posts with a strong hook, 2-3 key points, and a call to action."
)

# simulated research facts — keyed by topic keyword
_RESEARCH_DATA: dict[str, str] = {
    "langgraph": (
        "LangGraph is a framework by LangChain for building stateful multi-agent AI applications. "
        "It uses a graph-based execution model with nodes, edges, and shared state. "
        "Released as v1.0 in October 2025, used in production by Uber, LinkedIn, and Klarna."
    ),
    "langchain": (
        "LangChain is a high-level framework for building LLM-powered agents. "
        "v1.0 released October 2025 alongside LangGraph. "
        "Provides create_agent() abstraction and middleware support."
    ),
    "fastapi": (
        "FastAPI is a modern, fast Python web framework for building APIs. "
        "Known for automatic OpenAPI docs, Pydantic validation, and async support. "
        "One of the fastest Python frameworks available."
    ),
    "python": (
        "Python is the most popular language for AI/ML development. "
        "Known for readability, vast ecosystem, and strong community support."
    ),
}

_TRENDS_DATA: dict[str, str] = {
    "langgraph": (
        "Multi-agent systems growing 300% YoY. "
        "Companies moving from prototypes to production agents. "
        "Human-in-the-loop becoming standard. LangGraph v1.0 signals enterprise readiness."
    ),
    "langchain": (
        "LangChain 1.0 marks production-grade stability. "
        "create_agent() replacing manual chain building. "
        "Middleware pattern gaining adoption."
    ),
    "fastapi": (
        "FastAPI adoption surging in AI/ML backends. "
        "Async APIs becoming standard. "
        "FastAPI + LangGraph combination popular for agent APIs."
    ),
    "python": (
        "Python dominates AI/ML. "
        "Python 3.12+ performance improvements. "
        "Type hints becoming standard practice."
    ),
}

_DEFAULT_RESEARCH: str = (
    "A rapidly growing technology with widespread adoption across the industry, "
    "strong community support, and increasing enterprise interest."
)

_DEFAULT_TRENDS: str = (
    "Growing enterprise adoption, increasing community contributions, "
    "and strong industry momentum heading into 2026."
)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def intake_node(state: BlogState) -> dict[str, Any]:
    """
    First node — seeds the conversation with a system prompt
    and the user's topic as the initial HumanMessage.
    """
    print(f"[intake] topic='{state['topic']}'")
    return {
        "messages": [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"Write a LinkedIn post about: {state['topic']}"),
        ]
    }


def researcher_node(state: BlogState) -> dict[str, Any]:
    """
    Runs in parallel with trend_finder_node.
    Looks up pre-defined research facts for the topic.
    """
    print(f"[researcher] topic='{state['topic']}'")
    topic_lower: str = state["topic"].lower()
    research: str = next(
        (v for k, v in _RESEARCH_DATA.items() if k in topic_lower),
        f"Key facts about {state['topic']}: {_DEFAULT_RESEARCH}",
    )
    return {
        "research": research,
        "sources":  ["researcher"],
    }


def trend_finder_node(state: BlogState) -> dict[str, Any]:
    """
    Runs in parallel with researcher_node.
    Looks up current trend data for the topic.
    """
    print(f"[trend_finder] topic='{state['topic']}'")
    topic_lower: str = state["topic"].lower()
    trends: str = next(
        (v for k, v in _TRENDS_DATA.items() if k in topic_lower),
        f"Current trends in {state['topic']}: {_DEFAULT_TRENDS}",
    )
    return {
        "trends":  trends,
        "sources": ["trend_finder"],
    }


def aggregator_node(state: BlogState) -> dict[str, Any]:
    """
    Fan-in node — waits for both parallel agents to finish,
    then combines their output into a single context message for the writer.
    """
    print("[aggregator] combining research + trends")
    context: str = (
        f"Research findings:\n{state['research']}\n\n"
        f"Current trends:\n{state['trends']}\n\n"
        f"Now write an engaging LinkedIn post about: {state['topic']}. "
        f"Use tools to add hashtags and emojis."
    )
    return {
        "messages": [HumanMessage(content=context)]
    }


def writer_node(state: BlogState) -> dict[str, Any]:
    """
    Core LLM node — writes or refines the post.
    On subsequent iterations, injects reviewer feedback into messages
    so the LLM knows what to fix.
    """
    iteration: int = state["iteration"] + 1
    print(f"[writer] iteration={iteration}")

    messages: list[BaseMessage] = list(state["messages"])

    feedback: str = state.get("review_feedback", "")
    if feedback and feedback != "APPROVED":
        messages.append(
            HumanMessage(content=(
                f"Revise the post based on this feedback: {feedback}. "
                "Make sure it has emojis, hashtags, and is over 200 characters."
            ))
        )

    result: BaseMessage = llm_with_tools.invoke(messages)
    return {
        "messages":  [result],
        "draft":     result.content,
        "iteration": iteration,
    }


# prebuilt node — reads tool_calls from the last AIMessage and runs them
tool_node: ToolNode = ToolNode(tools)


def reviewer_node(state: BlogState) -> dict[str, Any]:
    """
    Quality gate — checks the draft against three criteria.
    Returns "APPROVED" or a comma-separated list of what needs fixing.
    """
    print("[reviewer] checking draft quality")
    draft: str = state.get("draft", "")

    has_hashtags: bool = "#" in draft
    long_enough: bool  = len(draft) > 200
    has_emojis: bool   = any(ord(c) > 127 for c in draft)

    if has_hashtags and long_enough and has_emojis:
        print("   ✅ APPROVED")
        return {"review_feedback": "APPROVED"}

    issues: list[str] = []
    if not has_hashtags:
        issues.append("Add relevant hashtags (e.g. #AI #Python)")
    if not long_enough:
        issues.append("Make the post longer — at least 200 characters")
    if not has_emojis:
        issues.append("Add emojis to make it more engaging")

    feedback: str = ", ".join(issues)
    print(f"   ❌ Needs improvement: {feedback}")
    return {"review_feedback": feedback}


def output_node(state: BlogState) -> dict[str, Any]:
    """
    Final node — logs a summary and stores the approved post
    in final_post so the API can return it.
    """
    print("[output] post approved — storing result")
    separator: str = "=" * 50
    print(f"\n{separator}")
    print(f"Topic      : {state['topic']}")
    print(f"Sources    : {', '.join(state['sources'])}")
    print(f"Iterations : {state['iteration']}")
    print(f"\n{state['draft']}")
    print(f"{separator}\n")
    return {"final_post": state["draft"]}
