"""Behavioral contracts across pipeline components, using original synthetic fixtures."""

import numpy as np
import pytest
from app.engine import Engine
from app.models import Material, Profile


class SectorDistractorEncoder:
    def encode(self, documents, query=False):
        if query:
            return np.array([[1.0, 0.0]])
        return np.array([[0.86, (1 - 0.86**2) ** 0.5], [0.99, (1 - 0.99**2) ** 0.5]])


def test_incompatible_high_similarity_cannot_suppress_eligible_candidate():
    materials = [
        Material(
            id="general",
            source_type="article",
            title="Общие принципы",
            description="Обзор для предпринимателей",
        ),
        Material(id="retail", source_type="article", title="Торговля одеждой", industries=["Розница"]),
    ]
    route = Engine(materials, semantic=SectorDistractorEncoder()).recommend("Открыть медицинскую клинику")
    assert [item.material.id for item in route.items] == ["general"]
    assert route.match_scope == "general"


def test_generic_sector_fallback_is_short_instead_of_filling_five_slots():
    materials = [
        Material(
            id=str(i),
            source_type="article",
            title=f"Бизнес-план: расчёт расходов {i}",
            topics=["Первые шаги"],
        )
        for i in range(8)
    ]
    route = Engine(materials).recommend("Открыть медицинский бизнес", limit=5)
    assert 1 <= len(route.items) <= 3
    assert route.match_scope == "general"
    assert all("не подтверждено" in item.reasons[0] for item in route.items)


def test_query_constraints_shared_by_baseline_but_feedback_is_personal():
    materials = [
        Material(id="general", source_type="course", title="Бизнес-план", topics=["Первые шаги"]),
        Material(
            id="retail", source_type="article", title="Бизнес-план магазина одежды", industries=["Розница"]
        ),
    ]
    engine = Engine(materials)
    query = "Открыть медицинский бизнес"
    baseline = engine.recommend(query, Profile(industry="Розница"), {"general": "completed"}, baseline=True)
    assert [item.material.id for item in baseline.items] == ["general"]
    assert not engine.recommend(query, feedback={"general": "completed"}).items


def test_empty_vocabulary_and_unpublished_content_do_not_crash():
    route = Engine([Material(id="empty", title="...", source_type="article", published=False)]).recommend(
        "Нужен бизнес-план"
    )
    assert not route.items and route.clarification


@pytest.mark.parametrize("limit", [0, 11, 1.5])
def test_invalid_internal_limit_is_rejected_explicitly(limit):
    with pytest.raises(ValueError):
        Engine([]).recommend("налоги", limit=limit)


def test_scope_describes_displayed_items_not_a_weak_unselected_candidate(monkeypatch):
    from app.recommendation.index import Evidence

    materials = [
        Material(id=str(i), source_type="article", title=f"Бизнес-план {i}", topics=["Первые шаги"])
        for i in range(6)
    ]
    materials.append(Material(id="medical", source_type="article", title="Медицинская лаборатория"))
    engine = Engine(materials)
    values = np.array([0.9] * 6 + [0.1])
    monkeypatch.setattr(engine.index, "search", lambda *args: Evidence(values, values, None))
    route = engine.recommend("Открыть медицинскую лабораторию")
    assert route.match_scope == "general"
    assert len(route.items) <= 3
    assert all(item.material.id != "medical" for item in route.items)
