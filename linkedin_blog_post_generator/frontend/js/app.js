const API_BASE = "http://localhost:8000/api";

// ── Generate ─────────────────────────────────────────────────────────────────
async function generatePost() {
    const topic = document.getElementById("topicInput").value.trim();

    if (!topic) {
        showError("Please enter a topic before generating.");
        return;
    }

    hideError();
    setLoading(true);
    hideResult();
    animatePipeline();

    try {
        const response = await fetch(`${API_BASE}/generate`, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ topic }),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Server error: ${response.status}`);
        }

        const data = await response.json();
        displayResult(data);

    } catch (error) {
        showError(`Failed to generate post: ${error.message}`);
        resetPipeline();
    } finally {
        setLoading(false);
    }
}

// ── Display result ────────────────────────────────────────────────────────────
function displayResult(data) {
    document.getElementById("topicChip").textContent   = `📌 ${data.topic}`;
    document.getElementById("iterChip").textContent    = `🔁 ${data.iterations} iteration${data.iterations !== 1 ? "s" : ""}`;
    document.getElementById("sourcesChip").textContent = `🔗 Sources: ${data.sources.join(", ")}`;
    document.getElementById("postContent").textContent = data.final_post;

    document.getElementById("resultSection").classList.remove("d-none");
    completePipeline();

    // Smooth scroll to result
    setTimeout(() => {
        document.getElementById("resultSection").scrollIntoView({ behavior: "smooth" });
    }, 200);
}

// ── Copy post ─────────────────────────────────────────────────────────────────
function copyPost() {
    const content = document.getElementById("postContent").textContent;
    navigator.clipboard.writeText(content).then(() => {
        const btn = document.getElementById("copyBtn");
        btn.textContent = "✅ Copied!";
        setTimeout(() => { btn.textContent = "📋 Copy"; }, 2000);
    });
}

// ── Loading state ─────────────────────────────────────────────────────────────
function setLoading(loading) {
    const btn     = document.getElementById("generateBtn");
    const btnText = document.getElementById("btnText");
    const spinner = document.getElementById("btnSpinner");

    btn.disabled = loading;
    btnText.textContent = loading ? "Generating..." : "Generate";
    spinner.classList.toggle("d-none", !loading);
}

// ── Error ─────────────────────────────────────────────────────────────────────
function showError(message) {
    const alert = document.getElementById("errorAlert");
    alert.textContent = message;
    alert.classList.remove("d-none");
}

function hideError() {
    document.getElementById("errorAlert").classList.add("d-none");
}

// ── Result visibility ─────────────────────────────────────────────────────────
function hideResult() {
    document.getElementById("resultSection").classList.add("d-none");
}

// ── Pipeline animation ────────────────────────────────────────────────────────
const STEPS = ["step-research", "step-write", "step-review", "step-output"];
let pipelineTimer = null;

function animatePipeline() {
    resetPipeline();
    let i = 0;
    pipelineTimer = setInterval(() => {
        if (i > 0) document.getElementById(STEPS[i - 1])?.classList.remove("active");
        if (i < STEPS.length) {
            document.getElementById(STEPS[i])?.classList.add("active");
            i++;
        } else {
            clearInterval(pipelineTimer);
        }
    }, 900);
}

function completePipeline() {
    clearInterval(pipelineTimer);
    STEPS.forEach(id => {
        const el = document.getElementById(id);
        el?.classList.remove("active");
        el?.classList.add("done");
    });
}

function resetPipeline() {
    clearInterval(pipelineTimer);
    STEPS.forEach(id => {
        const el = document.getElementById(id);
        el?.classList.remove("active", "done");
    });
}
