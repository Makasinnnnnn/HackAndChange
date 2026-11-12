"""Offline metrics for explicitly judged query/material pairs; no fabricated labels."""

from __future__ import annotations

import math


def metrics(ranked_ids: list[str], relevance: dict[str, int], k=5) -> dict[str, float]:
    top = ranked_ids[:k]
    if any(mid not in relevance for mid in top):
        raise ValueError("All retrieved top-k materials must be judged")
    positive = {mid for mid, grade in relevance.items() if grade >= 2}
    hits = sum(mid in positive for mid in top)
    dcg = sum((2 ** relevance[mid] - 1) / math.log2(i + 2) for i, mid in enumerate(top))
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum((2**grade - 1) / math.log2(i + 2) for i, grade in enumerate(ideal))
    reciprocal = next((1 / (i + 1) for i, mid in enumerate(top) if mid in positive), 0)
    return {
        "precision_at_5": hits / k,
        "pooled_recall_at_5": hits / len(positive) if positive else 0,
        "ndcg_at_5": dcg / idcg if idcg else 0,
        "mrr_at_5": reciprocal,
    }
