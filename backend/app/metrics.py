"""
Lighthouse AI — RAG Metrics Engine
Computes retrieval relevance and groundedness scores for RAG spans.
Falls back gracefully if sentence-transformers is not installed.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger("lighthouse.metrics")

_model = None
_model_loaded = False


def get_model():
    global _model, _model_loaded
    if _model_loaded:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Sentence transformer model loaded")
    except ImportError:
        logger.warning("sentence-transformers not installed — RAG scoring disabled")
        _model = None
    except Exception as e:
        logger.warning(f"Could not load sentence transformer: {e}")
        _model = None
    _model_loaded = True
    return _model


def compute_retrieval_relevance(query: str, chunks: list) -> Optional[float]:
    model = get_model()
    if model is None or not chunks:
        return None
    try:
        from sentence_transformers import util
        chunk_texts = [c.get("text", str(c)) if isinstance(c, dict) else str(c) for c in chunks]
        if not chunk_texts:
            return None
        query_emb = model.encode(query, convert_to_tensor=True)
        chunk_embs = model.encode(chunk_texts, convert_to_tensor=True)
        scores = util.cos_sim(query_emb, chunk_embs)[0]
        return round(float(scores.mean().item()), 4)
    except Exception as e:
        logger.warning(f"Relevance scoring failed: {e}")
        return None


def compute_groundedness(response: str, chunks: list) -> Optional[float]:
    model = get_model()
    if model is None or not chunks or not response:
        return None
    try:
        from sentence_transformers import util
        chunk_texts = [c.get("text", str(c)) if isinstance(c, dict) else str(c) for c in chunks]
        if not chunk_texts:
            return None
        response_emb = model.encode(response, convert_to_tensor=True)
        chunk_embs = model.encode(chunk_texts, convert_to_tensor=True)
        scores = util.cos_sim(response_emb, chunk_embs)[0]
        return round(float(scores.max().item()), 4)
    except Exception as e:
        logger.warning(f"Groundedness scoring failed: {e}")
        return None


def score_span(
    retrieval_query: Optional[str],
    retrieval_chunks_json: Optional[str],
    output_json: Optional[str],
) -> dict:
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
                groundedness = compute_groundedness(" ".join(str(r) for r in response), chunks)
        except Exception:
            pass

    return {
        "relevance_score": relevance,
        "groundedness_score": groundedness,
    }