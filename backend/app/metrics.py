"""
Lighthouse AI — RAG Metrics Engine
Computes retrieval relevance and groundedness scores for RAG spans.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger("lighthouse.metrics")

# Lazy-load the model so startup isn't slow
_model = None

def get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Sentence transformer model loaded")
        except Exception as e:
            logger.warning(f"Could not load sentence transformer: {e}")
            _model = None
    return _model


def compute_retrieval_relevance(query: str, chunks: list[dict | str]) -> float:
    """
    Compute mean cosine similarity between the query and each retrieved chunk.
    Returns a score between 0 and 1.
    """
    model = get_model()
    if model is None or not chunks:
        return 0.0

    try:
        from sentence_transformers import util
        import torch

        # Extract text from chunks
        chunk_texts = []
        for c in chunks:
            if isinstance(c, dict):
                chunk_texts.append(c.get("text", str(c)))
            else:
                chunk_texts.append(str(c))

        if not chunk_texts:
            return 0.0

        query_emb = model.encode(query, convert_to_tensor=True)
        chunk_embs = model.encode(chunk_texts, convert_to_tensor=True)
        scores = util.cos_sim(query_emb, chunk_embs)[0]
        return float(scores.mean().item())

    except Exception as e:
        logger.warning(f"Relevance scoring failed: {e}")
        return 0.0


def compute_groundedness(response: str, chunks: list[dict | str]) -> float:
    """
    Compute how well the response is grounded in the retrieved chunks.
    Uses max cosine similarity between the response and any chunk.
    Returns a score between 0 and 1.
    """
    model = get_model()
    if model is None or not chunks or not response:
        return 0.0

    try:
        from sentence_transformers import util

        chunk_texts = []
        for c in chunks:
            if isinstance(c, dict):
                chunk_texts.append(c.get("text", str(c)))
            else:
                chunk_texts.append(str(c))

        if not chunk_texts:
            return 0.0

        response_emb = model.encode(response, convert_to_tensor=True)
        chunk_embs = model.encode(chunk_texts, convert_to_tensor=True)
        scores = util.cos_sim(response_emb, chunk_embs)[0]
        return float(scores.max().item())

    except Exception as e:
        logger.warning(f"Groundedness scoring failed: {e}")
        return 0.0


def score_span(
    retrieval_query: Optional[str],
    retrieval_chunks_json: Optional[str],
    output_json: Optional[str],
) -> dict:
    """
    Score a retrieval span. Returns relevance and groundedness scores.
    """
    if not retrieval_query or not retrieval_chunks_json:
        return {"relevance_score": None, "groundedness_score": None}

    try:
        chunks = json.loads(retrieval_chunks_json)
    except Exception:
        return {"relevance_score": None, "groundedness_score": None}

    relevance = compute_retrieval_relevance(retrieval_query, chunks)

    groundedness = None
    if output_json:
        try:
            response = json.loads(output_json)
            if isinstance(response, str):
                groundedness = compute_groundedness(response, chunks)
            elif isinstance(response, list):
                response_text = " ".join(str(r) for r in response)
                groundedness = compute_groundedness(response_text, chunks)
        except Exception:
            pass

    return {
        "relevance_score": round(relevance, 4),
        "groundedness_score": round(groundedness, 4) if groundedness is not None else None,
    }