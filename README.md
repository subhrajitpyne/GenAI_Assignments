# 🧠 GenAI Projects — Subhrajit Pyne

A collection of Generative AI projects built during the Codebasics Agentic AI Bootcamp.

---

## 📁 Projects

### 🤖 [Blog Post Generator](./blog_post_generator/)
AI-powered LinkedIn post generator built on LangGraph multi-agent architecture.
- Parallel agents (researcher + trend finder)
- ReAct loop with tools
- Reflection pattern (self-review cycle)
- FastAPI backend + HTML/CSS/Bootstrap frontend
- **Stack:** LangGraph 1.0 · LangChain 1.0 · FastAPI · Python

---

### 🏥 [MediBot](./medibot/)
RAG-based medical Q&A chatbot with hybrid retrieval and RBAC.
- Hybrid retrieval (BM25 sparse + RRF fusion + cross-encoder reranking)
- Role-based access control enforced at Qdrant metadata filter level
- **Stack:** FastAPI · Qdrant · Docling · HybridChunker · Python

---

### 👨‍💻 [Multi-Agent Coding Assistant](./coding_agent/)
Production-grade coding assistant built on LangGraph Supervisor pattern.
Accepts a coding problem in natural language, auto-detects the programming
language, and uses a team of specialised agents to write, test, validate,
and iterate on the solution until all tests pass.

**Agent pipeline:**
- 🎯 **Orchestrator** — supervisor that routes between specialists using `with_structured_output`
- 💻 **Coder** — writes solution in the detected language (Python / Java / JavaScript)
- 🧪 **Tester** — generates independent test cases without seeing the code (TDD)
- 🔍 **Validator** — verifies test cases match the problem before execution
- ▶️ **Runner** — real `pytest` for Python · LLM evaluation for Java and JavaScript
- 🔁 **Reflection loop** — coder retries up to 5 times using exact failure output

**Key features:**
- Auto language detection from prompt — no dropdown needed
- Combine + alias approach solves function name mismatches at runtime
- Token cost tracked per LLM call — displayed in UI
- SSE streaming — pipeline animates in real time
- FastAPI serves both API and frontend from one command

**Stack:** LangGraph 1.0 · LangChain 1.0 · FastAPI · OpenAI GPT-4o-mini · pytest · Python

---

## 👤 Author
**Subhrajit Pyne** — BigFix Engineer & AI Developer @ Wolters Kluwer
- 💼 [LinkedIn](https://www.linkedin.com/in/subhrajit-pyne-305a90b4/)
- 🐙 [GitHub](https://github.com/subhrajitpyne)