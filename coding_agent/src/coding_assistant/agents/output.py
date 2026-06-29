from typing import Any
from ..state import ProjectState

from dotenv import load_dotenv

import os,certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

#Uses windows trusted certs from truststore
import truststore
truststore.inject_into_ssl()

load_dotenv()


def output_node(state: ProjectState) -> dict[str, Any]:
    """
    Final node — collects results and prints summary.
    No LLM call — pure Python.
    """
    print("\n[output] finalising results...")

    is_solved: bool = state.get("test_status") == "pass"
    separator: str  = "=" * 60

    print(f"\n{separator}")
    print(f"  🤖 Coding Assistant — Result")
    print(f"{separator}")
    print(f"  Question      : {state['question'][:80]}")
    print(f"  Language      : {state['language']}")
    print(f"  Code attempts : {state.get('code_attempts', 0)}")
    print(f"  Test attempts : {state.get('test_attempts', 0)}")
    print(f"  Status        : {'SOLVED' if is_solved else 'UNSOLVED'}")
    print(f"  Total cost    : ${state.get('total_cost_usd', 0.0):.4f}")
    print(f"{separator}")
    print(f"\n--- Generated Code ---\n")
    print(state.get("code", "No code generated"))
    print(f"\n--- Test Results ---\n")
    print(state.get("test_results", "No tests run"))
    print(f"{separator}\n")

    return {
        "final_code":      state.get("code", ""),
        "final_test_code": state.get("test_code", ""),
        "is_solved":       is_solved,
    }
