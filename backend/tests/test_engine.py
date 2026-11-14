import json

import pytest
from app.catalog import load_catalog
from app.engine import Engine
from app.models import Material, Profile
from pydantic import ValidationError

QUERY = "В кофейне мало клиентов. Хочу привлечь новых клиентов"


@pytest.mark.parametrize("query", ["", " ", "Помогите с бизнесом", "бизнес"])
def test_cold_start_clarifies_without_random_results(engine, query):
    route = engine.recommend(query)
    assert route.clarification and not route.items


def test_new_user_gets_explainable_route_without_onboarding(engine):
    route = engine.recommend(QUERY)
    assert route.items and not route.active_profile_fields
    assert all(i.reasons and i.next_action for i in route.items)
    assert all({"relevance", "diversity_penalty"} <= set(i.signals) for i in route.items)
    assert all(not (set(i.signals) & {"industry", "stage", "experience", "format", "urgency", "feedback"}) for i in route.items)
    assert len({i.material.id for i in route.items}) == len(route.items)


def test_empty_catalog():
    route = Engine([]).recommend(QUERY)
    assert route.items == [] and route.clarification


def test_out_of_catalog_query_does_not_promise_an_answer(engine):
    route = engine.recommend("Квантовая гравитация и телепортация нейтрино")
    assert not route.items and route.clarification


@pytest.mark.parametrize("signal", ["known", "completed", "not_relevant"])
def test_feedback_excludes_material(engine, signal):
    first = engine.recommend(QUERY).items[0].material.id
    route = engine.recommend(QUERY, feedback={first: signal})
    assert first not in [i.material.id for i in route.items]
    assert route.excluded_count == 1


def test_baseline_independent_of_profile_and_feedback(engine):
    baseline = engine.recommend(QUERY, baseline=True)
    personal_input = engine.recommend(
        QUERY,
        Profile(industry="HoReCa", format="document"),
        {baseline.items[0].material.id: "completed"},
        baseline=True,
    )
    assert [i.model_dump() for i in baseline.items] == [i.model_dump() for i in personal_input.items]
    assert not personal_input.active_profile_fields


def test_explicit_format_changes_ranking(engine):
    docs = engine.recommend("Нужен план продвижения и маркетинг", Profile(format="document", urgency="quick"))
    assert docs.items[0].material.source_type == "document"
    assert any("формат" in r for r in docs.items[0].reasons)


def test_industry_explanations_require_material_metadata(engine):
    route = engine.recommend(QUERY, Profile(industry="HoReCa"))
    for item in route.items:
        claims = [r for r in item.reasons if "отраслевая" in r]
        assert bool(claims) == ("HoReCa" in item.material.industries)


def test_price_not_used_as_boost(engine):
    a = engine.recommend(QUERY)
    for material in engine.materials:
        material.price = 999999 if material.access == "paid" else None
    b = engine.recommend(QUERY)
    assert [i.material.id for i in a.items] == [i.material.id for i in b.items]


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "//evil.test/a", "file:///secret", "https://user:password@example.com"]
)
def test_unsafe_links_rejected(url):
    with pytest.raises(ValidationError):
        Material(id="bad", source_type="article", title="Title", url=url)


def test_closed_content_cannot_enter_api_model():
    for provenance, access in [("organizer", "free"), ("synthetic", "paid")]:
        with pytest.raises(ValidationError):
            Material(
                id="bad",
                source_type="course",
                title="Title",
                provenance=provenance,
                access=access,
                demo_content="Private text",
            )


def test_catalog_dedup_and_publication_filter(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            [
                dict(id="a", source_type="article", title="Same title"),
                dict(id="b", source_type="article", title="Same title"),
                dict(id="c", source_type="course", title="Draft", published=False),
            ]
        )
    )
    materials, _, _ = load_catalog(path)
    assert [m.id for m in materials] == ["a"]


@pytest.mark.parametrize("query", ["франшиза", "кофе"])
def test_short_input_searches_a_task_or_asks_for_one(query):
    material = Material(id="short", source_type="course", title="Франшиза кофейни", description="Как выбрать франшизу и открыть кофейню")
    route = Engine([material]).recommend(query)
    if query == "кофе":
        assert not route.items and route.clarification
    else:
        assert route.items


def test_real_source_topic_aliases_and_bounded_personalization():
    relevant = Material(id="relevant", source_type="course", title="Как управлять командой", description="Делегирование задач и полномочий сотрудникам", topics=["Управление командой"], industries=["HoReСa"], difficulty="beginner")
    generic = Material(id="generic", source_type="article", title="Новости бизнеса")
    engine = Engine([relevant, generic])
    route = engine.recommend("делегирование сотрудникам", Profile(industry="HoReCa", experience="beginner"))
    assert route.items[0].material.id == "relevant"
    assert route.items[0].signals["industry"] == 1
    assert route.items[0].signals["experience"] == 1


def test_opening_intent_does_not_recommend_closure():
    materials = [Material(id="start", source_type="course", title="Открытие бизнеса: бизнес-план", topics=["Первые шаги"]), Material(id="close", source_type="article", title="Как закрыть ИП", topics=["Первые шаги"])]
    route = Engine(materials).recommend("Хочу открыть бизнес с нуля")
    assert route.items and all(i.material.id != "close" for i in route.items)


def test_explicit_sector_mismatch_is_not_rescued_by_broad_service_profile():
    materials = [Material(id="plan", source_type="course", title="Как открыть бизнес: бизнес-план", topics=["Первые шаги"]), Material(id="beauty", source_type="article", title="Как открыть маникюрную студию", topics=["Первые шаги"], industries=["Услуги"])]
    route = Engine(materials).recommend("Открыть медицинскую лабораторию", Profile(industry="Услуги"))
    assert route.items and all(i.material.id != "beauty" for i in route.items)
    assert "общие материалы" in route.notice


def test_unmatched_profile_field_does_not_claim_to_affect_additive_ranking():
    material = Material(id="cafe", source_type="course", title="Как привлечь клиентов", topics=["Маркетинг"], industries=["HoReCa"])
    route = Engine([material]).recommend("Как привлечь клиентов", Profile(industry="Услуги"))
    assert route.items
    assert "industry" not in route.active_profile_fields
    assert not any("отраслевая" in reason for reason in route.items[0].reasons)


@pytest.mark.parametrize("other_industry", ["Розница", "Производство", "Строительство и недвижимость"])
def test_medical_query_rejects_different_industry_metadata(other_industry):
    materials = [Material(id="general", source_type="course", title="Как составить бизнес-план", topics=["Первые шаги"]), Material(id="wrong", source_type="article", title="Бизнес-план магазина одежды с нуля: выбираем нишу", industries=[other_industry])]
    route = Engine(materials).recommend("медицинский бизнес открыть томск бабки тачки телки", Profile(industry="Услуги"))
    assert route.items and "wrong" not in {i.material.id for i in route.items}
    assert route.match_scope == "general"
    assert any("не подтверждено" in reason for reason in route.items[0].reasons)


def test_unlabelled_specialized_startup_subject_is_not_general_fallback():
    from app.engine import sector_compatibility
    assert not sector_compatibility(Material(id="a", source_type="article", title="Бизнес-план зоомагазина"), {"medical"})
    assert sector_compatibility(Material(id="b", source_type="article", title="Как составить бизнес-план: пошаговая инструкция"), {"medical"})
    assert sector_compatibility(Material(id="c", source_type="article", title="Бизнес-план медицинской клиники"), {"medical"})
