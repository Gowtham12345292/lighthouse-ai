"""
Demo: A simulated AI agent traced by Lighthouse.

This agent does 3 things:
1. Makes an LLM call to plan a task
2. Calls a tool (web search)
3. Makes another LLM call to summarize — this one FAILS

Run it:
    cd lighthouse-sdk
    python examples/demo_agent.py

You'll see the full trace printed to console with the execution tree,
latencies, inputs/outputs, and the error. This is the data that will
eventually flow into the Lighthouse dashboard.
"""

import time
import random
from lighthouse import Lighthouse

# Initialize with debug=True to see traces in console
lh = Lighthouse(api_key="lh_demo_key", debug=True)


def fake_llm_call(prompt: str, should_fail: bool = False) -> str:
    """Simulate an LLM API call with realistic latency."""
    time.sleep(random.uniform(0.3, 0.8))  # Simulate network latency
    if should_fail:
        raise TimeoutError("LLM API request timed out after 30s")
    return f"LLM response to: {prompt[:50]}"


def fake_tool_call(query: str) -> dict:
    """Simulate a tool call (e.g., web search)."""
    time.sleep(random.uniform(0.1, 0.3))
    return {
        "results": [
            {"title": "Result 1", "url": "https://example.com/1"},
            {"title": "Result 2", "url": "https://example.com/2"},
        ]
    }


# ── The agent ───────────────────────────────────────────────────────


@lh.trace
def research_agent(query: str) -> str:
    """A simple 3-step agent: plan → search → summarize."""

    # Step 1: LLM plans the research
    with lh.span("plan", span_type="llm_call", model="claude-sonnet-4-6") as s:
        plan = fake_llm_call(f"Create a research plan for: {query}")
        s.record(
            input=f"Create a research plan for: {query}",
            output=plan,
            tokens_in=25,
            tokens_out=150,
        )

    # Step 2: Tool call — web search
    with lh.span("web_search", span_type="tool_call") as s:
        results = fake_tool_call(query)
        s.record(input={"query": query}, output=results)

    # Step 3: LLM summarizes — THIS FAILS (simulating a real failure)
    with lh.span("summarize", span_type="llm_call", model="claude-sonnet-4-6") as s:
        summary = fake_llm_call(f"Summarize: {results}", should_fail=True)
        s.record(input=str(results), output=summary, tokens_in=200, tokens_out=300)

    return summary


# ── Run it ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running research agent with Lighthouse tracing...\n")
    try:
        result = research_agent("What is agent observability and why does it matter?")
        print(f"Agent result: {result}")
    except Exception as e:
        print(f"\nAgent failed (expected): {e}")
        print("But Lighthouse captured the full trace above ☝️")