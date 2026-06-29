from typing import Any
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


# ── Pricing table — update as providers change ────────────────────────────────
_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {
        "input":  0.000150 / 1000,
        "output": 0.000600 / 1000,
    },
    "gpt-4o": {
        "input":  0.002500 / 1000,
        "output": 0.010000 / 1000,
    },
    "claude-haiku-4-5-20251001": {
        "input":  0.000800 / 1000,
        "output": 0.004000 / 1000,
    },
    "claude-sonnet-4-6": {
        "input":  0.003000 / 1000,
        "output": 0.015000 / 1000,
    },
}

_DEFAULT_MODEL: str = "gpt-4o-mini"


def calculate_cost(
    model_name:        str,
    prompt_tokens:     int,
    completion_tokens: int,
) -> float:
    """Calculate cost in USD for a given model and token counts."""
    pricing = _PRICING.get(model_name, _PRICING[_DEFAULT_MODEL])
    return (
        prompt_tokens     * pricing["input"] +
        completion_tokens * pricing["output"]
    )


class SessionCostTracker(BaseCallbackHandler):
    """
    Tracks token usage and cost across ALL LLM calls in one agent run.

    Plug into any LLM via callbacks=[tracker].
    Accumulates cost per agent call and total for the session.
    """

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        self.model_name:        str         = model_name
        self.prompt_tokens:     int         = 0
        self.completion_tokens: int         = 0
        self.call_count:        int         = 0
        self.call_breakdown:    list[dict]  = []

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Fires automatically after every LLM response."""
        usage = response.llm_output.get("token_usage", {}) if response.llm_output else {}

        # handle both OpenAI and Anthropic naming conventions
        p: int = (
            usage.get("prompt_tokens",  0) or
            usage.get("input_tokens",   0)
        )
        c: int = (
            usage.get("completion_tokens", 0) or
            usage.get("output_tokens",     0)
        )

        cost: float = calculate_cost(self.model_name, p, c)

        self.prompt_tokens     += p
        self.completion_tokens += c
        self.call_count        += 1

        self.call_breakdown.append({
            "call":             self.call_count,
            "prompt_tokens":    p,
            "output_tokens":    c,
            "cost_usd":         cost,
        })

    @property
    def total_cost(self) -> float:
        """Total cost in USD for all LLM calls so far."""
        return calculate_cost(
            self.model_name,
            self.prompt_tokens,
            self.completion_tokens,
        )

    def display(self) -> None:
        """Print a full cost breakdown to console."""
        print(f"\n{'='*50}")
        print(f"  💰 Cost Breakdown")
        print(f"{'='*50}")
        for call in self.call_breakdown:
            print(
                f"  Call {call['call']:>2} | "
                f"in: {call['prompt_tokens']:>6} | "
                f"out: {call['output_tokens']:>6} | "
                f"${call['cost_usd']:.6f}"
            )
        print(f"{'─'*50}")
        print(f"  Total calls   : {self.call_count}")
        print(f"  Total tokens  : {self.prompt_tokens + self.completion_tokens}")
        print(f"  Total cost    : ${self.total_cost:.4f}")
        print(f"{'='*50}\n")

    def to_dict(self) -> dict:
        """Serialise tracker data for API response."""
        return {
            "total_calls":       self.call_count,
            "prompt_tokens":     self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens":      self.prompt_tokens + self.completion_tokens,
            "total_cost_usd":    round(self.total_cost, 6),
            "formatted_cost":    f"${self.total_cost:.4f}",
            "breakdown":         self.call_breakdown,
        }
