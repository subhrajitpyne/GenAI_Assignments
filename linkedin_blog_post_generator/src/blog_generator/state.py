import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class BlogState(TypedDict):
    """
    Shared state that flows through every node in the graph.

    Fields with reducers accumulate values across nodes.
    Fields without reducers are plain overwrites — last write wins.
    """

    # what the user wants to write about
    topic: str

    # full conversation history — add_messages handles deduplication
    messages: Annotated[list[BaseMessage], add_messages]

    # filled by researcher_node and trend_finder_node (parallel)
    research: str
    trends: str

    # the current working draft — overwritten on each writer iteration
    draft: str

    # feedback from reviewer_node — "APPROVED" means we're done
    review_feedback: str

    # which agents/tools contributed — operator.add appends across nodes
    sources: Annotated[list[str], operator.add]

    # how many writer iterations have run
    iteration: int

    # the final approved post — set once by output_node
    final_post: str
