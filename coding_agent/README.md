# 🤖 Multi-Agent Coding Assistant

A production-grade coding assistant built on **LangGraph Supervisor Pattern**.
Accepts a coding problem in natural language, auto-detects the programming language,
and uses a team of specialised agents to write, test, validate, and iterate on the
solution until all tests pass.

---

## Architecture

```
User types problem (language auto-detected from prompt)
            ↓
      [Orchestrator]              ← supervisor — decides who runs next
            ↓
        [Coder]                   ← writes solution in detected language
            ↓
        [Tester]                  ← generates test cases independently (never sees code)
            ↓
      [Orchestrator]
            ↓
      [Validator]                 ← checks tests match the problem statement
            ↓
        [Runner]                  ← pytest for Python / LLM eval for Java & JS
            ↓
      pass → [Output]             ← final result + cost breakdown
      fail → [Coder]  ← Reflection loop — retries up to 5 times using exact failure output
```

---

## Agent Pipeline

| Agent | Role | LLM? |
|---|---|---|
| **Orchestrator** | Reads state and decides which agent runs next using `with_structured_output` | ✅ Yes |
| **Coder** | Writes solution in the detected language. On retry — fixes based on exact test failure output | ✅ Yes |
| **Tester** | Generates test cases from problem statement only — never sees the code (TDD) | ✅ Yes |
| **Validator** | Checks if test cases correctly test the problem requirements before execution | ✅ Yes |
| **Runner** | Executes tests — real `pytest` for Python, LLM evaluation for Java and JavaScript | ❌ No (Python) / ✅ Yes (others) |
| **Output** | Collects final result, prints summary with cost breakdown | ❌ No |

---

## Patterns Used

| Pattern | Where |
|---|---|
| Supervisor / Orchestrator | Orchestrator routes between all agents dynamically |
| Reflection | Coder retries up to 5 times based on exact pytest failure output |
| LLM Router | `with_structured_output` + Pydantic for deterministic routing decisions |
| Test Validation | Validator checks tests semantically before runner executes them |
| Conditional edges | `orchestrator_router`, `test_validation_router`, `test_result_router`, `post_coder_router` |
| State with reducers | `operator.add` for cost/tokens/notes, `add_messages` for conversation history |
| Checkpointing | `InMemorySaver` — state persists across agent hops within one session |
| Cost tracking | Every LLM call tracked via `BaseCallbackHandler` — displayed in UI |
| SSE Streaming | Pipeline events streamed token by token to frontend |
| Auto language detection | Language extracted from prompt — no dropdown needed |

---

## Project Structure

```
coding_agent/
│
├── src/coding_assistant/
│   ├── state.py                  # Shared state TypedDict
│   ├── graph.py                  # Graph assembly and compilation
│   ├── routers.py                # All routing functions
│   ├── cost_tracker.py           # Token cost tracking callback handler
│   │
│   ├── agents/
│   │   ├── orchestrator.py       # Supervisor — routes between specialists
│   │   ├── coder.py              # Writes and fixes code
│   │   ├── tester.py             # Generates test cases
│   │   ├── validator.py          # Validates tests against problem
│   │   ├── runner.py             # Executes tests
│   │   └── output.py            # Formats and stores final result
│   │
│   └── tools/
│       ├── file_tools.py         # write_file, read_file tools
│       └── test_tools.py         # check_syntax, run_tests tools
│
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── api/routes.py             # /api/stream, /api/run, /api/health
│   └── core/config.py            # Pydantic settings, loads .env
│
├── frontend/
│   ├── index.html                # Single-page UI
│   ├── css/style.css             # Dark GitHub-style theme
│   └── js/app.js                 # SSE client, language detection, pipeline animation
│
├── workspace/                    # Generated code files saved here at runtime
├── tests/                        # Unit tests for agents and graph
└── requirements.txt
```

---

## File Reference

### `src/coding_assistant/state.py`
Defines `ProjectState` — the shared TypedDict that flows through every node.

| Field | Type | Reducer | Purpose |
|---|---|---|---|
| `question` | `str` | — | User's coding problem |
| `language` | `str` | — | Auto-detected language (python/java/javascript) |
| `code` | `str` | — | Latest generated solution |
| `test_code` | `str` | — | Latest generated test cases |
| `function_name` | `str` | — | Extracted function name — passed to tester |
| `test_validation_status` | `str` | — | "valid" or "invalid" |
| `test_results` | `str` | — | Full pytest / LLM evaluation output |
| `test_status` | `str` | — | "pass" or "fail" |
| `code_attempts` | `int` | — | How many times coder ran |
| `test_attempts` | `int` | — | How many times tester ran |
| `messages` | `list[BaseMessage]` | `add_messages` | Conversation history |
| `agent_notes` | `list[str]` | `operator.add` | Audit trail from all agents |
| `prompt_tokens` | `int` | `operator.add` | Accumulates across all nodes |
| `completion_tokens` | `int` | `operator.add` | Accumulates across all nodes |
| `total_cost_usd` | `float` | `operator.add` | Running cost in USD |
| `final_code` | `str` | — | Approved solution — returned to frontend |
| `is_solved` | `bool` | — | True if all tests passed |

---

### `src/coding_assistant/graph.py`
Assembles and compiles the full LangGraph graph.

```
build_graph()
  ├── Registers all 6 nodes
  ├── Entry: START → orchestrator
  ├── orchestrator → conditional (orchestrator_router)
  ├── tester → orchestrator (always reports back)
  ├── validate_tests → conditional (test_validation_router)
  ├── runner → conditional (test_result_router)
  ├── coder → conditional (post_coder_router) ← KEY: always goes to runner
  └── output → END
```

**Key design decision:** `coder` routes directly to `runner` via `post_coder_router`
— never back to orchestrator. This prevents orchestrator from skipping runner after retries.

---

### `src/coding_assistant/routers.py`
All routing functions — pure Python, no LLM calls.

| Router | Source node | Decides |
|---|---|---|
| `orchestrator_router` | `orchestrator` | Which specialist runs next — reads `state["next"]` |
| `test_validation_router` | `validate_tests` | Run tests or regenerate — checks `test_validation_status` |
| `test_result_router` | `runner` | Fix code or finish — checks `test_status` and `code_attempts` |
| `post_coder_router` | `coder` | Always → runner (unless max attempts) — prevents orchestrator bypass |

---

### `src/coding_assistant/cost_tracker.py`
`SessionCostTracker(BaseCallbackHandler)` — hooks into every LLM call automatically.

- `on_llm_end()` fires after every LLM response — extracts token counts
- Handles both OpenAI (`prompt_tokens`) and Anthropic (`input_tokens`) naming
- `to_dict()` serialises breakdown for API response
- `display()` prints formatted cost table to console

---

### `src/coding_assistant/agents/orchestrator.py`
Supervisor node — decides which agent runs next.

- LLM: `gpt-4o-mini` with `temperature=0` — deterministic routing
- `OrchestratorDecision` Pydantic model — `next` field + `reason`
- Reads full state context and returns `state["next"]`
- Routes to: `coder` · `tester` · `validate_tests` · `runner` · `output`

---

### `src/coding_assistant/agents/coder.py`
Writes or fixes code based on the problem statement.

- LLM: `gpt-4o-mini` with `temperature=0.2` — precise but slightly creative
- First run — writes from scratch in the detected language
- Retry — reads exact pytest failure output and fixes accordingly
- `_strip_code_fences()` — removes markdown backticks if LLM adds them
- `_strip_test_functions()` — removes `def test_*` from solution (Python only)
- `_extract_function_name()` — extracts function name per language (Python/Java/JS/Go)
- Saves `function_name` to state — tester uses it for correct import

---

### `src/coding_assistant/agents/tester.py`
Generates test cases from the problem statement only.

- LLM: `gpt-4o-mini` with `temperature=0.1`
- **Never reads `state["code"]`** — tests are independent of implementation
- Language-aware prompts — Python gets `pytest`, Java gets `JUnit`, JS gets `Jest`
- Reads `state["function_name"]` from coder — uses exact function name in import
- On retry — injects validator's rejection reason so LLM knows what to fix

---

### `src/coding_assistant/agents/validator.py`
Validates test cases against the problem statement — before execution.

- LLM: `gpt-4o-mini` with `temperature=0`
- `TestValidationResult` Pydantic model — `status` ("valid"/"invalid") + `reason`
- Does NOT run tests — reads them semantically
- Language-aware validation rules — JS/Java don't require `test_` prefix
- Prevents bad tests from wasting coder retry attempts

---

### `src/coding_assistant/agents/runner.py`
Executes tests and returns pass/fail with full output.

**Python:**
- Reads `solution.py` + `test_solution.py`
- Removes import lines from test file
- Auto-aliases function names — if test calls `factorial()` but solution has `calculate_factorial()`, adds `factorial = calculate_factorial`
- Combines into `combined_test.py` — runs with `pytest`
- `time.sleep(0.5)` ensures latest code version is read after coder write

**Java / JavaScript:**
- No runtime required — LLM mentally traces through code
- `_run_llm_tests()` uses `gpt-4o-mini` with structured output
- Returns `TestEvaluation` — `verdict`, `passed_tests`, `failed_tests`, `reason`

---

### `src/coding_assistant/agents/output.py`
Final node — no LLM call.

- Reads `state["code"]` and `state["test_results"]`
- Sets `is_solved = (test_status == "pass")`
- Prints formatted summary to console
- Returns `final_code`, `final_test_code`, `is_solved`

---

### `src/coding_assistant/tools/file_tools.py`
LangChain `@tool` decorated functions for file operations.

| Tool | Purpose |
|---|---|
| `write_file(path, content)` | Saves generated code/tests to `workspace/` |
| `read_file(path)` | Reads file content — used by runner |
| `get_file_extension(language)` | Maps language name → file extension |

---

### `src/coding_assistant/tools/test_tools.py`
LangChain `@tool` decorated functions for code validation.

| Tool | Purpose |
|---|---|
| `check_syntax(code, language)` | `ast.parse()` for Python, skipped for others |
| `run_tests(test_file, solution_file)` | Runs `pytest` via `subprocess` — used by runner |

---

### `backend/main.py`
FastAPI application entry point.

- `reload=False` — prevents uvicorn from restarting when workspace files change
- CORS middleware — allows frontend to call API
- `StaticFiles` — serves `frontend/` at `/static/`
- Root route `/` returns `index.html`

---

### `backend/api/routes.py`
API endpoints.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Liveness check |
| `/api/run` | POST | Blocking — returns full result |
| `/api/stream` | POST | SSE streaming — sends node updates as they happen |

**`_detect_language(question)`** — detects Java, JavaScript, or Python from prompt.
Java is checked before JavaScript to prevent `"java"` matching inside `"javascript"`.

---

### `frontend/js/app.js`
SSE client + UI logic.

- `detectLanguage()` — mirrors backend detection, updates badge as user types
- `streamAgent()` — consumes SSE stream from `/api/stream`
- `handleEvent()` — routes each event to correct UI update
- `activateStep()` / `markStepDone()` — animates pipeline steps
- `Ctrl+Enter` shortcut to run agent

---

### `workspace/`
Generated files at runtime — gitignored except `.gitkeep`.

| File | Created by |
|---|---|
| `solution.py` / `.java` / `.js` | `coder_node` via `write_file` |
| `test_solution.py` / `.java` / `.js` | `tester_node` via `write_file` |
| `combined_test.py` | `runner_node` — merged file for pytest |

---

## Setup

```bash
# Clone
git clone https://github.com/subhrajitpyne/GenAI_Assignments
cd coding_agent

# Install
pip install -r requirements.txt
cp .env.example .env
# Add OPENAI_API_KEY to .env

# Run — reload=False is important
cd backend
python main.py

# Open browser
http://localhost:8000
```

---

## Run Tests

```bash
pytest tests/ -v
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Multi-agent orchestration | LangGraph 1.2 |
| LLM integrations | LangChain 1.3 |
| LLM model | OpenAI GPT-4o-mini |
| REST API + SSE streaming | FastAPI |
| Test execution | pytest |
| Frontend | HTML · CSS · Bootstrap 5 · Vanilla JS |

---

## Author

**Subhrajit Pyne** — BigFix Engineer & AI Developer @ Wolters Kluwer
- 💼 [LinkedIn](https://www.linkedin.com/in/subhrajit-pyne-305a90b4/)
- 🐙 [GitHub](https://github.com/subhrajitpyne)