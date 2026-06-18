from langchain_core.tools import tool


# Simple lookup tables — easy to extend later
_HASHTAG_MAP: dict[str, str] = {
    "langgraph": "#LangGraph #AI #Python #GenAI #LLM #AgenticAI",
    "langchain": "#LangChain #AI #Python #GenAI #LLM",
    "fastapi":   "#FastAPI #Python #API #Backend #WebDev",
    "ai":        "#AI #ArtificialIntelligence #MachineLearning #GenAI",
    "python":    "#Python #Programming #SoftwareDevelopment #Coding",
}

_EMOJI_MAP: dict[str, str] = {
    "technical":    "🔧 💻 ⚙️ 🛠️ 📊",
    "inspiring":    "🚀 💡 ✨ 🌟 🎯",
    "educational":  "📚 🎓 💡 🔍 📝",
    "excited":      "🔥 🚀 💥 ⚡ 🎉",
    "professional": "💼 📈 🤝 ✅ 🏆",
}

_DEFAULT_HASHTAGS: str = "#AI #Technology #Innovation #Python #GenAI"
_DEFAULT_EMOJIS: str   = "🚀 💡 🔥 ✨ 🤖"


@tool
def get_hashtags(topic: str) -> str:
    """Get trending hashtags for a LinkedIn post on the given topic."""
    topic_lower: str = topic.lower()
    for key, hashtags in _HASHTAG_MAP.items():
        if key in topic_lower:
            return f"Trending hashtags for '{topic}': {hashtags}"
    return f"Trending hashtags for '{topic}': {_DEFAULT_HASHTAGS}"


@tool
def get_emoji_suggestions(tone: str) -> str:
    """Get emoji suggestions that match the tone of a LinkedIn post."""
    tone_lower: str = tone.lower()
    for key, emojis in _EMOJI_MAP.items():
        if key in tone_lower:
            return f"Emojis for {tone} tone: {emojis}"
    return f"Emojis for {tone} tone: {_DEFAULT_EMOJIS}"


tools: list = [get_hashtags, get_emoji_suggestions]
