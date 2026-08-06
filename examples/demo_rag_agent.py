"""
Demo: A simulated RAG agent traced by Lighthouse.

This agent does 3 things:
1. Retrieves chunks from a fake knowledge base
2. Generates an answer using the retrieved chunks
3. Lighthouse captures the retrieval data (query, chunks, scores)

Run it:
    $env:PYTHONPATH = "."
    python examples/demo_rag_agent.py
"""

import time
import random
from lighthouse import Lighthouse

lh = Lighthouse(api_key="lh-test-key-123", endpoint="http://localhost:8000", debug=True)


# Fake knowledge base
KNOWLEDGE_BASE = [
    {"doc_id": "doc-1", "text": "Agent observability is the practice of monitoring AI agent behavior in production."},
    {"doc_id": "doc-2", "text": "RAG pipelines retrieve relevant documents before generating answers."},
    {"doc_id": "doc-3", "text": "Hallucinations occur when an LLM generates claims not supported by the context."},
    {"doc_id": "doc-4", "text": "The capital of France is Paris. It is known for the Eiffel Tower."},
    {"doc_id": "doc-5", "text": "Retrieval relevance scoring measures how well chunks match the query."},
]


def fake_retrieve(query: str, top_k: int = 3) -> tuple[list[dict], list[float]]:
    """Simulate a retrieval step with relevance scores."""
    time.sleep(random.uniform(0.1, 0.3))
    # Return top_k chunks with fake scores (some deliberately low)
    chunks = KNOWLEDGE_BASE[:top_k]
    scores = [round(random.uniform(0.3, 0.95), 2) for _ in range(top_k)]
    return chunks, scores


def fake_generate(query: str, chunks: list[dict]) -> str:
    """Simulate LLM generation from retrieved chunks."""
    time.sleep(random.uniform(0.3, 0.6))
    context = " ".join(c["text"] for c in chunks)
    return f"Based on the retrieved context: {context[:100]}... The answer is that observability matters."


@lh.trace
def rag_agent(query: str) -> str:
    """A simple RAG agent: retrieve → generate."""

    # Step 1: Retrieve relevant chunks
    with lh.span("retrieve", span_type="retrieval") as s:
        chunks, scores = fake_retrieve(query, top_k=3)
        s.log_retrieval(
            query=query,
            chunks=chunks,
            scores=scores,
            top_k=3,
        )

    # Step 2: Generate answer from chunks
    with lh.span("generate", span_type="llm_call", model="claude-sonnet-4-6") as s:
        answer = fake_generate(query, chunks)
        s.record(
            input={"query": query, "context": chunks},
            output=answer,
            tokens_in=250,
            tokens_out=100,
        )

    return answer


if __name__ == "__main__":
    print("Running RAG agent with Lighthouse tracing...\n")
    result = rag_agent("What is agent observability and why does it matter?")
    print(f"\nAgent answer: {result}")
    print("\nWaiting for flush...")
    time.sleep(3)
    print("Done! Check your traces at http://localhost:8000/v1/traces")