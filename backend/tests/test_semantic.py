import os

import pytest
from app.semantic import optional_encoder


def test_missing_model_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("SEMANTIC_MODEL_DIR", str(tmp_path / "missing"))
    encoder, reason = optional_encoder()
    assert encoder is None and reason == "local_model_unavailable"


def test_no_model_is_a_supported_configuration(monkeypatch):
    monkeypatch.delenv("SEMANTIC_MODEL_DIR", raising=False)
    assert optional_encoder() == (None, "not_enabled")


@pytest.mark.skipif(
    not os.getenv("TEST_SEMANTIC_MODEL_DIR"), reason="Optional local ONNX weights not requested"
)
def test_real_local_encoder_handles_paraphrase_and_preserves_baseline(engine, monkeypatch):
    from app.engine import Engine
    from app.models import Profile

    monkeypatch.setenv("SEMANTIC_MODEL_DIR", os.environ["TEST_SEMANTIC_MODEL_DIR"])
    semantic, reason = optional_encoder()
    assert semantic is not None, reason
    model = Engine(engine.materials, semantic=semantic)
    query = "Как перестать делать всю работу самому и передать ответственность подчиненным?"
    result = model.recommend(query, Profile(urgency="quick"))
    assert result.items and result.items[0].material.id == "demo-delegation"
    assert result.algorithm == "e5-hybrid-personal-v2"
    a = engine.recommend(query, baseline=True)
    b = model.recommend(query, baseline=True)
    assert [i.material.id for i in a.items] == [i.material.id for i in b.items]
    assert not model.recommend("Квантовая гравитация и телепортация нейтрино").items
