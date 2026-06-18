# 🤖 AI Blog Post Generator

A multi-agent LangGraph application that researches a topic and generates
a professional LinkedIn post using parallel agents, ReAct loops, and a
Reflection pattern.

---

## Architecture

```
[intake_node]
      |
      ├──────────────────┐
[researcher]      [trend_finder]     ← Parallel agents
      |                  |
      └──────────────────┘
             |
      [aggregator_node]
             |
       [writer_node]  ←──────────────┐
             |                       |
     writer_router?                  |
             |                       |
        ┌────┴────┐                  |
      tools     reviewer        [tool_node]
        |            |               |
   [tool_node]  review_router?       |
                     |               |
               ┌─────┴─────┐        |
             writer       output ────┘
                             |
                            END
```

## Patterns Used

| Pattern | Where |
|---|---|
| Parallel execution | `researcher` + `trend_finder` run simultaneously |
| Fan-in | Both converge at `aggregator` |
| ReAct loop | `tools → writer` loopback |
| Reflection | `reviewer → writer` until approved |
| Conditional edges | `writer_router` + `review_router` |

---

## Setup

```bash
# Clone
git clone https://github.com/subhrajitpyne/linkedin_blog-post-generator
cd blog-post-generator

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Add your API keys to .env
```

---

## Run

**Backend:**
```bash
cd backend
python main.py
# API running at http://localhost:8000
# Docs at http://localhost:8000/docs
```

**Frontend:**
```bash
# Open frontend/index.html in your browser
# Or serve with VS Code Live Server extension
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/generate` | Generate LinkedIn post |

**Request body:**
```json
{ "topic": "LangGraph" }
```

**Response:**
```json
{
  "topic":      "LangGraph",
  "final_post": "🚀 Just discovered LangGraph...",
  "sources":    ["researcher", "trend_finder", "get_hashtags"],
  "iterations": 2
}
```

---

## Tests

```bash
pytest tests/ -v
```

---

## Tech Stack

- **LangGraph 1.0** — Multi-agent orchestration
- **LangChain 1.0** — LLM integrations
- **FastAPI** — REST API backend
- **Bootstrap 5** — Frontend UI
- **OpenAI GPT-4o-mini** — LLM

---

## Author

**Subhrajit Pyne** — [Code & Automate](https://hashnode.com)
