"""
Lighthouse AI SDK — trace every step of your AI agent runs.

Usage:
    from lighthouse import Lighthouse

    lh = Lighthouse(api_key="lh_test_key")

    @lh.trace
    def run_agent(query):
        with lh.span("llm_call", model="claude-sonnet-4-6") as s:
            response = call_llm(query)
            s.record(input=query, output=response, tokens=150)
        return response
"""

from .Sdk import Lighthouse, Span

__all__ = ["Lighthouse", "Span"]
__version__ = "0.1.0"