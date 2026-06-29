# 🤖 AI Coding Assistant

A multi-agent LangGraph system that takes a coding problem, writes code, generates independent test cases, validates them, runs them, and iterates until solved.

---

## Architecture

```
User → question + language
            ↓
      [Orchestrator]        ← supervisor — decides who runs next
      ↙           ↘
  [Coder]       [Tester]    ← parallel — independent agents
      ↘           ↙
      [Orchestrator]
           ↓
     [Validator]            ← checks tests match problem statement
           ↓
       [Runner]             ← runs pytest, returns pass/fail
           ↓
     pass → [Output]
     fail → [Coder] ← retry up to 3 times
```

## Patterns Used

| Pattern | Where |
|---|---|
| Supervisor | Orchestrator coordinates all agents |
| Parallel generation | Coder + Tester run independently |
| Reflection | Coder retries based on test failure output |
| Test validation | Supervisor validates tests before running |
| Cost tracking | Every LLM call tracked and displayed |

---

## Setup

```bash
# Clone and install
git clone https://github.com/subhrajitpyne/GenAI_Assignments
cd coding_agent
pip install -r requirements.txt
cp .env.example .env
# Add OPENAI_API_KEY to .env

# Run
cd backend
python main.py

# Open browser
http://localhost:8000
```

## Run Tests

```bash
pytest tests/ -v
```

---

## Tech Stack

- **LangGraph 1.2** — multi-agent orchestration
- **LangChain 1.3** — LLM integrations
- **FastAPI** — REST API + SSE streaming
- **OpenAI GPT-4o-mini** — all agents
- **pytest** — test execution inside the agent

## Author

**Subhrajit Pyne** — [GitHub](https://github.com/subhrajitpyne)
