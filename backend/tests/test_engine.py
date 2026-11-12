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
    assert all(set(i.signals) == {"relevance", "diversity_penalty"} for i in route.items)
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
