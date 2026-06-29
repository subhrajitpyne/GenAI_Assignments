const API_BASE = "http://localhost:8000/api";

// ── State ─────────────────────────────────────────────────────────────────────
let totalCost     = 0.0;
let totalTokens   = 0;
let callCount     = 0;
let costBreakdown = [];

// ── Run agent ─────────────────────────────────────────────────────────────────
async function runAgent() {
    const question = document.getElementById("questionInput").value.trim();
    const language = document.getElementById("languageSelect").value;

    if (!question) {
        showError("Please enter a problem statement.");
        return;
    }

    // reset UI
    hideError();
    resetPipeline();
    resetOutputPanels();
    resetCost();
    setLoading(true);
    showStatus("running", "⏳ Running agents...", "");

    try {
        await streamAgent(question, language);
    } catch (err) {
        showError(`Failed: ${err.message}`);
        setLoading(false);
    }
}

// ── Stream agent events ───────────────────────────────────────────────────────
async function streamAgent(question, language) {
    const response = await fetch(`${API_BASE}/stream`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ question, language }),
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${response.status}`);
    }

    const reader  = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text  = decoder.decode(value);
        const lines = text.split("\n\n").filter(Boolean);

        for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const data = JSON.parse(line.replace("data: ", ""));
            handleEvent(data);
        }
    }
}

// ── Handle each SSE event ─────────────────────────────────────────────────────
function handleEvent(data) {
    if (data.error) {
        showError(data.error);
        setLoading(false);
        return;
    }

    if (data.done) {
        setLoading(false);
        return;
    }

    // highlight active pipeline step
    if (data.node) {
        activateStep(data.node);
    }

    // append agent notes to log
    if (data.notes && data.notes.length > 0) {
        data.notes.forEach(note => appendLog(note));
    }

    // accumulate cost
    if (data.cost) {
        totalCost   += data.cost;
        callCount   += 1;
        totalTokens += 0;   // individual token tracking via notes
        updateCostDisplay();
    }

    // final result
    if (data.node === "output") {
        markStepDone("output");
        if (data.final_code) {
            showCode(data.final_code);
        }
        if (data.is_solved !== null && data.is_solved !== undefined) {
            const solved = data.is_solved;
            showStatus(
                solved ? "solved" : "unsolved",
                solved ? "✅ Solved" : "❌ Unsolved",
                `Cost: $${totalCost.toFixed(4)} · Calls: ${callCount}`,
            );
        }
        if (data.test_status) {
            markStepDone(data.test_status === "pass" ? "runner" : "runner");
        }
    }
}

// ── Pipeline helpers ──────────────────────────────────────────────────────────
const STEP_IDS = [
    "orchestrator", "coder", "tester",
    "validate_tests", "runner", "output",
];

function activateStep(nodeName) {
    const id = `step-${nodeName}`;
    const el = document.getElementById(id);
    if (!el) return;

    // deactivate previously active
    STEP_IDS.forEach(s => {
        const e = document.getElementById(`step-${s}`);
        if (e) e.classList.remove("active");
    });

    el.classList.add("active");
    el.classList.remove("done");
    showLog();
}

function markStepDone(nodeName) {
    const el = document.getElementById(`step-${nodeName}`);
    if (!el) return;
    el.classList.remove("active");
    el.classList.add("done");
}

function resetPipeline() {
    STEP_IDS.forEach(s => {
        const el = document.getElementById(`step-${s}`);
        if (el) el.classList.remove("active", "done");
    });
}

// ── Log ───────────────────────────────────────────────────────────────────────
function appendLog(note) {
    const log   = document.getElementById("agentLog");
    const entry = document.createElement("div");
    entry.className   = "log-entry";
    entry.textContent = note;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

function showLog() {
    document.getElementById("logPanel").classList.remove("d-none");
}

// ── Code output ───────────────────────────────────────────────────────────────
function showCode(code) {
    document.getElementById("codeOutput").textContent = code;
    document.getElementById("codePanel").classList.remove("d-none");
}

function copyCode() {
    const code = document.getElementById("codeOutput").textContent;
    navigator.clipboard.writeText(code).then(() => {
        const btn = document.querySelector(".copy-btn");
        btn.textContent = "✅ Copied!";
        setTimeout(() => { btn.textContent = "📋 Copy"; }, 2000);
    });
}

// ── Status ────────────────────────────────────────────────────────────────────
function showStatus(type, label, meta) {
    const panel  = document.getElementById("statusPanel");
    const badge  = document.getElementById("statusBadge");
    const metaEl = document.getElementById("statusMeta");

    panel.classList.remove("d-none");
    badge.className   = `status-badge ${type}`;
    badge.textContent = label;
    metaEl.textContent = meta;
}

// ── Cost ──────────────────────────────────────────────────────────────────────
function resetCost() {
    totalCost     = 0.0;
    totalTokens   = 0;
    callCount     = 0;
    costBreakdown = [];
    document.getElementById("costPanel").classList.add("d-none");
    document.getElementById("costGrid").innerHTML = "";
}

function updateCostDisplay() {
    const panel = document.getElementById("costPanel");
    const grid  = document.getElementById("costGrid");
    panel.classList.remove("d-none");

    grid.innerHTML = `
        <div class="cost-row">
            <span>LLM calls so far</span>
            <span>${callCount}</span>
        </div>
        <div class="cost-row total">
            <span>💰 Total cost</span>
            <span>$${totalCost.toFixed(4)}</span>
        </div>
    `;
}

// ── Loading ───────────────────────────────────────────────────────────────────
function setLoading(loading) {
    const btn     = document.getElementById("runBtn");
    const text    = document.getElementById("btnText");
    const spinner = document.getElementById("btnSpinner");

    btn.disabled        = loading;
    text.textContent    = loading ? "Running..." : "⚡ Run Agent";
    spinner.classList.toggle("d-none", !loading);
}

// ── Error ─────────────────────────────────────────────────────────────────────
function showError(msg) {
    const el = document.getElementById("errorAlert");
    el.textContent = msg;
    el.classList.remove("d-none");
}
function hideError() {
    document.getElementById("errorAlert").classList.add("d-none");
}

// ── Reset output ──────────────────────────────────────────────────────────────
function resetOutputPanels() {
    ["statusPanel", "logPanel", "codePanel", "testPanel"].forEach(id => {
        document.getElementById(id)?.classList.add("d-none");
    });
    document.getElementById("agentLog").innerHTML   = "";
    document.getElementById("codeOutput").textContent = "";
}
