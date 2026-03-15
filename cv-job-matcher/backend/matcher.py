"""CV–job matching using sentence-transformers and cosine similarity."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from job_sources import Job

# Lazy-load model to avoid slow startup when only parsing CV or fetching jobs
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def score_jobs(cv_text: str, jobs: list["Job"], top_k: int = 20) -> list[tuple["Job", float]]:
    """
    Rank jobs by semantic similarity to the CV. Returns top_k jobs with scores in [0, 1].
    """
    if not cv_text or not jobs:
        return []

    model = _get_model()
    # Combine title + description for each job
    job_texts = [f"{j.title}. {j.description}" for j in jobs]
    cv_emb = model.encode(cv_text, convert_to_tensor=False)
    job_embs = model.encode(job_texts, convert_to_tensor=False)

    import numpy as np
    from numpy.linalg import norm

    def cos_sim(a, b):
        return float(np.dot(a, b) / (norm(a) * norm(b) + 1e-9))

    scored = [(jobs[i], cos_sim(cv_emb, job_embs[i])) for i in range(len(jobs))]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
