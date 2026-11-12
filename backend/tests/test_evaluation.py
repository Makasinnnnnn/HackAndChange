import pytest
from app.evaluation import metrics


def test_perfect_ranking():
    result = metrics(["a", "b", "c", "d", "e"], {"a": 3, "b": 2, "c": 0, "d": 0, "e": 0})
    assert result["precision_at_5"] == 0.4
    assert result["pooled_recall_at_5"] == 1
    assert result["ndcg_at_5"] == 1
    assert result["mrr_at_5"] == 1


def test_wrong_order_reduces_ndcg():
    labels = {"a": 3, "b": 2, "c": 0, "d": 0, "e": 0}
    result = metrics(["c", "d", "e", "b", "a"], labels)
    assert 0 < result["ndcg_at_5"] < 1
    assert result["mrr_at_5"] == 0.25


def test_missing_labels_are_not_treated_as_negative():
    with pytest.raises(ValueError):
        metrics(["a", "unjudged"], {"a": 3})
