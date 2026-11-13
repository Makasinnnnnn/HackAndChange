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


@pytest.mark.parametrize(
    "query",
    [
        "Как увеличить прибыль без увеличения рекламного бюджета?",
        "Как увеличить продажи, не увеличивая расходы на рекламу?",
        "Как повысить рентабельность с тем же рекламным бюджетом?",
        "Хочу повысить доход без дополнительных затрат на рекламу",
    ],
)
@pytest.mark.parametrize("baseline", [False, True])
def test_fixed_ad_spend_requires_a_concrete_mechanism(query, baseline):
    materials = [
        Material(
            id="seasonal",
            source_type="article",
            title="Праздничная реклама: рост продаж",
            topics=["Маркетинг"],
        ),
        Material(
            id="broad",
            source_type="course",
            title="Обучение маркетингу",
            description="Общий обзор инструментов",
            topics=["Маркетинг"],
        ),
        Material(
            id="retain",
            source_type="article",
            title="Повторные продажи и удержание клиентов",
            topics=["Продажи"],
        ),
        Material(
            id="margin", source_type="article", title="Маржинальность и ценообразование", topics=["Финансы"]
        ),
    ]
    route = Engine(materials).recommend(query, baseline=baseline)
    assert route.items
    assert {item.material.id for item in route.items} <= {"retain", "margin"}
    assert all(any(key.startswith("constraint_") for key in item.signals) for item in route.items)
    assert all(any("ограничение" in reason for reason in item.reasons) for item in route.items)
    if not baseline:
        assert len({item.next_action for item in route.items}) == len(route.items)


def test_constraint_does_not_ban_advertising_efficiency():
    materials = [
        Material(
            id="ad",
            source_type="article",
            title="Как повысить эффективность рекламы и снизить стоимость привлечения",
            topics=["Маркетинг"],
        )
    ]
    route = Engine(materials).recommend("Как увеличить прибыль без увеличения рекламного бюджета?")
    assert [item.material.id for item in route.items] == ["ad"]


def test_seasonal_campaign_is_still_eligible_when_requested():
    material = Material(
        id="ad",
        source_type="article",
        title="Праздничная реклама: как увеличить продажи",
        topics=["Маркетинг"],
    )
    assert Engine([material]).recommend("Как запустить праздничную рекламу и увеличить продажи?").items


def test_unrelated_optimization_is_not_profit_evidence():
    material = Material(
        id="hr", source_type="article", title="Как сократить время найма сотрудников", topics=["Команда"]
    )
    route = Engine([material]).recommend("Как увеличить прибыль без увеличения рекламного бюджета?")
    assert not route.items and route.clarification


def test_constrained_general_query_does_not_invent_a_marketplace_or_fill_with_definitions():
    materials = [
        Material(
            id="retain",
            source_type="article",
            title="Повторные продажи и удержание клиентов",
            description="Как увеличить прибыль",
            topics=["Продажи"],
        ),
        Material(
            id="market", source_type="article", title="Маржинальность на маркетплейсах", topics=["Финансы"]
        ),
        Material(id="term", source_type="glossary", title="Маржинальность", topics=["Финансы"]),
    ]
    engine = Engine(materials)
    for baseline in (False, True):
        route = engine.recommend(
            "Как увеличить прибыль без увеличения рекламного бюджета?", baseline=baseline
        )
        assert [item.material.id for item in route.items] == ["retain"]
    from app.recommendation.eligibility import exclusion_reason
    from app.recommendation.intent import parse_intent

    specialized = parse_intent("Как увеличить прибыль на маркетплейсах без увеличения рекламного бюджета?")
    assert exclusion_reason(materials[1], specialized, {}) is None


@pytest.mark.parametrize(
    "query,bad_title,good_title",
    [
        ("Как закрыть ИП, а не открыть новое?", "Как открыть ИП", "Как закрыть ИП"),
        (
            "Не хочу покупать франшизу. Как запустить свой бизнес?",
            "Как выбрать франшизу",
            "Бизнес-план: запуск бизнеса",
        ),
        (
            "Какие отчёты сдаёт ИП без сотрудников?",
            "Отчётность при найме сотрудника",
            "Налоговая отчётность ИП",
        ),
        ("Как мотивировать команду?", "Как мотивировать клиентов оставлять отзывы", "Мотивация сотрудников"),
        (
            "Как проверить бизнес-идею до аренды помещения?",
            "Договор аренды помещения",
            "Как проверить спрос на продукт",
        ),
        (
            "Как работать с возражениями клиентов?",
            "Возражение на акт налоговой проверки",
            "Как работать с возражениями покупателей",
        ),
        ("Как зарегистрировать ИП?", "Как зарегистрировать профиль на площадке", "Как открыть ИП"),
        ("Как перейти на УСН?", "Как перейти на НПД", "Переход на УСН"),
        (
            "Как организовать закупки на производстве?",
            "Как участвовать в госзакупках",
            "Управление закупками и снабжение",
        ),
    ],
)
def test_operation_and_subject_are_not_replaced_by_keyword_overlap(query, bad_title, good_title):
    materials = [
        Material(id="bad", source_type="article", title=bad_title),
        Material(id="good", source_type="article", title=good_title),
    ]
    for baseline in (False, True):
        route = Engine(materials).recommend(query, baseline=baseline)
        assert [item.material.id for item in route.items] == ["good"]
        assert route.items[0].reasons and route.items[0].next_action


def test_unspecified_contract_type_is_clarified_instead_of_guessed():
    route = Engine([Material(id="employment", source_type="document", title="Трудовой договор")]).recommend(
        "Нужен шаблон договора, а не курс по продажам"
    )
    assert not route.items and "Какой договор" in route.clarification


def test_multiple_operations_preserve_weaker_but_specific_second_clause():
    materials = [
        Material(id="plan", source_type="article", title="Как составить бизнес-план"),
        Material(id="demand", source_type="article", title="Как проверить спрос на продукт"),
        Material(id="noise", source_type="article", title="Кассовые ордера и отчётность"),
    ]
    route = Engine(materials).recommend("Как составить бизнес-план и проверить спрос?")
    assert {item.material.id for item in route.items} == {"plan", "demand"}
    assert any(item.signals.get("coverage_bonus", 0) > 0 for item in route.items)


def test_missing_part_of_compound_task_is_disclosed():
    route = Engine(
        [Material(id="retain", source_type="article", title="Как удержать постоянных клиентов")]
    ).recommend("Как повысить цены и удержать постоянных клиентов?")
    assert route.items and "части запроса" in route.notice and "цена" in route.notice


def test_task_caches_are_immutable_across_calls():
    from app.recommendation.tasks import query_tasks, task_matches

    before = task_matches("Бизнес-план: проверка спроса")
    query_tasks("Бизнес-план: проверка спроса")
    assert before == task_matches("Бизнес-план: проверка спроса")
    assert isinstance(before, frozenset)


@pytest.mark.parametrize("query", ["Какая погода завтра в Томске?", "Как решить квадратное уравнение?"])
def test_nonbusiness_query_cannot_match_on_question_words(query):
    materials = [
        Material(
            id="business",
            source_type="article",
            title="Какая система налогов поможет решить задачу бизнеса",
            topics=["Финансы"],
        )
    ]
    assert not Engine(materials).recommend(query).items


@pytest.mark.parametrize(
    "query,bad_title,good_title",
    [
        ("Как оценить спрос?", "Всё, что вы боялись спросить", "Как проверить спрос на продукт"),
        (
            "Как руководителю давать обратную связь?",
            "Обратная связь клиентов о продукте",
            "Обратная связь сотрудникам",
        ),
        (
            "Как разрешить конфликт между сотрудниками?",
            "Судебная доверенность для конфликта",
            "Конфликты в команде сотрудников",
        ),
        (
            "Как увеличить прибыль без найма дополнительных сотрудников?",
            "Найм сотрудников для роста прибыли",
            "Рентабельность и маржинальность",
        ),
        (
            "Как оформить возврат денег покупателю?",
            "Акт возврата товара поставщику",
            "Политика возвратов товаров покупателями",
        ),
        (
            "Как настроить продвижение в Яндексе?",
            "Продвижение бизнеса на Авито",
            "Продвижение бизнеса в Яндексе",
        ),
        (
            "Как открыть салон красоты и удержать клиентов?",
            "Программа лояльности магазина одежды",
            "Программа лояльности клиентов салона красоты",
        ),
    ],
)
def test_subject_and_negation_regressions_from_semantic_audit(query, bad_title, good_title):
    route = Engine(
        [
            Material(id="bad", source_type="article", title=bad_title),
            Material(id="good", source_type="article", title=good_title),
        ]
    ).recommend(query)
    assert [item.material.id for item in route.items] == ["good"]


def test_tax_comparison_does_not_return_an_incidental_declaration():
    route = Engine(
        [
            Material(
                id="form",
                source_type="document",
                title="Декларация УСН",
                description="Налоговый режим и сравнение с патентом",
            ),
            Material(
                id="compare",
                source_type="article",
                title="Как выбрать налоговый режим: сравнение УСН и патента",
            ),
        ]
    ).recommend("Чем патент отличается от УСН?")
    assert [item.material.id for item in route.items] == ["compare"]


def test_typo_normalization_preserves_original_query():
    query = "хачу аткрыть кафейню и панять скока денег нада"
    route = Engine(
        [
            Material(id="plan", source_type="article", title="Бизнес-план кофейни"),
            Material(id="close", source_type="article", title="Как закрыть ИП"),
        ]
    ).recommend(query)
    assert route.query == query
    assert [item.material.id for item in route.items] == ["plan"]


def test_calculation_does_not_match_recalculation_or_subword_cost():
    from app.recommendation.tasks import query_tasks

    assert "cost_calculation" not in query_tasks("Как рассчитать себестоимость товара и установить цену?")
    assert "cost_calculation" not in query_tasks("Перерасчёт стоимости патента")
    assert "cost_calculation" in query_tasks("Как рассчитать затраты на перевозку?")


def test_calculator_format_does_not_admit_unrelated_calendar():
    route = Engine(
        [
            Material(
                id="tax", source_type="calculator", title="Калькулятор налогов для ИП", topics=["Налоги"]
            ),
            Material(id="days", source_type="calculator", title="Калькулятор календарных дней"),
        ]
    ).recommend("Нужен калькулятор налогов для ИП, а не определение налога")
    assert [item.material.id for item in route.items] == ["tax"]


def test_demand_validation_does_not_become_operational_forecasting():
    route = Engine(
        [
            Material(id="forecast", source_type="article", title="Прогнозирование спроса для закупок"),
            Material(id="validate", source_type="article", title="Как проверить спрос на продукт"),
        ]
    ).recommend("Как проверить бизнес-идею до покупки оборудования?")
    assert [item.material.id for item in route.items] == ["validate"]


def test_past_tax_year_is_not_offered_as_current_unless_explicitly_requested():
    from datetime import date

    year = date.today().year
    materials = [
        Material(id="old", source_type="article", title=f"Налоговая отчётность в {year - 1} году"),
        Material(id="current", source_type="article", title=f"Налоговая отчётность в {year} году"),
    ]
    assert [
        item.material.id for item in Engine(materials).recommend("Как сдавать налоговую отчётность?").items
    ] == ["current"]
    assert Engine(materials).recommend(f"Налоговая отчётность в {year - 1} году").items


def test_explicit_task_evidence_is_not_rejected_as_unknown_low_similarity(monkeypatch):
    from app.recommendation.index import Evidence

    engine = Engine([Material(id="retain", source_type="article", title="Повторные продажи")])
    monkeypatch.setattr(
        engine.index, "search", lambda *args: Evidence(np.array([0.0]), np.array([0.0]), np.array([0.7]))
    )
    assert engine.recommend("Как построить программу лояльности?").items


def test_compound_route_covers_second_operation_before_repeating_first():
    from app.recommendation.ranking import Candidate, select

    candidates = [
        Candidate(
            Material(id=str(i), title="Материал", source_type="article"),
            {"relevance": score, task: 1},
            [],
            score,
        )
        for i, (score, task) in enumerate(
            [
                (0.9, "task_retention"),
                (0.85, "task_retention"),
                (0.8, "task_retention"),
                (0.4, "task_costing"),
            ]
        )
    ]
    result = select(candidates, 3)
    assert result[1].material.id == "3" and result[1].coverage_priority


def test_actual_demo_starter_recognizes_visitors_as_customer_acquisition():
    from app.recommendation.intent import parse_intent

    assert (
        "acquisition" in parse_intent("В моей кофейне мало клиентов. Как привлечь новых посетителей?").tasks
    )


def test_referral_request_is_not_replaced_by_generic_content_marketing():
    route = Engine(
        [
            Material(id="content", source_type="article", title="Контент-маркетинг для клиентов"),
            Material(id="referral", source_type="article", title="Реферальная программа для клиентов"),
        ]
    ).recommend("Как получать клиентов через рекомендации и сарафанное радио?")
    assert [item.material.id for item in route.items] == ["referral"]
