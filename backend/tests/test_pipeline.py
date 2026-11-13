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

@pytest.mark.parametrize('query', [
    'Как увеличить прибыль без увеличения рекламного бюджета?',
    'Как увеличить продажи, не увеличивая расходы на рекламу?',
    'Как повысить рентабельность с тем же рекламным бюджетом?',
    'Хочу повысить доход без дополнительных затрат на рекламу',
])
@pytest.mark.parametrize('baseline', [False, True])
def test_fixed_ad_spend_requires_a_concrete_mechanism(query, baseline):
    materials = [
        Material(id='seasonal', source_type='article', title='Праздничная реклама: рост продаж', topics=['Маркетинг']),
        Material(id='broad', source_type='course', title='Обучение маркетингу', description='Общий обзор инструментов', topics=['Маркетинг']),
        Material(id='retain', source_type='article', title='Повторные продажи и удержание клиентов', topics=['Продажи']),
        Material(id='margin', source_type='article', title='Маржинальность и ценообразование', topics=['Финансы']),
    ]
    route = Engine(materials).recommend(query, baseline=baseline)
    assert route.items
    assert {item.material.id for item in route.items} <= {'retain', 'margin'}
    assert all(any(key.startswith('constraint_') for key in item.signals) for item in route.items)
    assert all(any('ограничение' in reason for reason in item.reasons) for item in route.items)
    if not baseline:
        assert len({item.next_action for item in route.items}) == len(route.items)


def test_constraint_does_not_ban_advertising_efficiency():
    materials = [Material(id='ad', source_type='article', title='Как повысить эффективность рекламы и снизить стоимость привлечения', topics=['Маркетинг'])]
    route = Engine(materials).recommend('Как увеличить прибыль без увеличения рекламного бюджета?')
    assert [item.material.id for item in route.items] == ['ad']


def test_seasonal_campaign_is_still_eligible_when_requested():
    material = Material(id='ad', source_type='article', title='Праздничная реклама: как увеличить продажи', topics=['Маркетинг'])
    assert Engine([material]).recommend('Как запустить праздничную рекламу и увеличить продажи?').items


def test_unrelated_optimization_is_not_profit_evidence():
    material = Material(id='hr', source_type='article', title='Как сократить время найма сотрудников', topics=['Команда'])
    route = Engine([material]).recommend('Как увеличить прибыль без увеличения рекламного бюджета?')
    assert not route.items and route.clarification


def test_constrained_general_query_does_not_invent_a_marketplace_or_fill_with_definitions():
    materials = [
        Material(id='retain', source_type='article', title='Повторные продажи и удержание клиентов', description='Как увеличить прибыль', topics=['Продажи']),
        Material(id='market', source_type='article', title='Маржинальность на маркетплейсах', topics=['Финансы']),
        Material(id='term', source_type='glossary', title='Маржинальность', topics=['Финансы']),
    ]
    engine = Engine(materials)
    for baseline in (False, True):
        route = engine.recommend('Как увеличить прибыль без увеличения рекламного бюджета?', baseline=baseline)
        assert [item.material.id for item in route.items] == ['retain']
    from app.recommendation.eligibility import exclusion_reason
    from app.recommendation.intent import parse_intent

    specialized = parse_intent('Как увеличить прибыль на маркетплейсах без увеличения рекламного бюджета?')
    assert exclusion_reason(materials[1], specialized, {}) is None
