import json

from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


def test_ready_and_real_catalog(client):
    assert client.get("/api/ready").json()["materials"] == 36
    page = client.get("/api/catalog?limit=3&offset=2").json()
    assert page["total"] == 36 and len(page["items"]) == 3
    assert all("demo_content" not in m for m in page["items"])


def test_session_and_feedback_roundtrip(client):
    data = client.get("/api/bootstrap")
    assert "HttpOnly" in data.headers["set-cookie"] and "SameSite=strict" in data.headers["set-cookie"]
    payload = {"query": "Хочу привлечь клиентов", "profile": {"industry": "HoReCa"}}
    first = client.post("/api/recommendations", json=payload).json()["items"][0]["material"]["id"]
    assert client.post("/api/feedback", json={"material_id": first, "signal": "completed"}).json()["saved"]
    route = client.post("/api/recommendations", json=payload).json()
    assert first not in [i["material"]["id"] for i in route["items"]]
    assert client.get("/api/progress").json()["items"][0]["signal"] == "completed"
    assert client.get("/api/bootstrap").json()["profile"]["industry"] == "HoReCa"
    assert client.post("/api/feedback", json={"material_id": first, "signal": "reset"}).status_code == 200
    assert not client.get("/api/progress").json()["items"]


def test_sessions_isolated(client):
    client.get("/api/bootstrap")
    client.post("/api/feedback", json={"material_id": "demo-cash-flow", "signal": "completed"})
    other = TestClient(app)
    try:
        assert other.get("/api/bootstrap").json()["signals"] == {}
        assert other.get("/api/progress").json()["items"] == []
        assert len(client.get("/api/progress").json()["items"]) == 1
    finally:
        other.close()


def test_invalid_inputs(client):
    assert client.post("/api/recommendations", json={"query": "x" * 1501}).status_code == 422
    assert client.post("/api/recommendations", json={"limit": 100}).status_code == 422
    assert client.post("/api/recommendations", json={"profile": {"experience": "expert"}}).status_code == 422
    assert (
        client.post("/api/feedback", json={"material_id": "missing", "signal": "completed"}).status_code
        == 404
    )
    assert client.get("/api/catalog/missing").status_code == 404
    assert client.get("/api/catalog?limit=1000").status_code == 422
    assert client.post("/api/recommendations", content="x" * 17000).status_code == 413
    assert (
        client.post(
            "/api/feedback",
            headers={"Sec-Fetch-Site": "cross-site"},
            json={"material_id": "demo-cash-flow", "signal": "helpful"},
        ).status_code
        == 403
    )


def test_compare_computes_both_algorithms_and_no_fake_metrics(client):
    comparison = client.post(
        "/api/demo/compare",
        json={"query": "Маркетинг и привлечение клиентов", "profile": {"format": "document"}},
    ).json()
    assert comparison["baseline"]["algorithm"] != comparison["personal"]["algorithm"]
    assert comparison["baseline"]["catalog_version"] == comparison["personal"]["catalog_version"]
    assert comparison["personal"]["active_profile_fields"] == ["format"]
    assert client.get("/api/evaluation/results").json()["metrics"] is None


def test_progress_survives_new_application_lifespan(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "application.db"))
    with TestClient(app) as first:
        first.get("/api/bootstrap")
        cookies = dict(first.cookies)
        first.post("/api/feedback", json={"material_id": "demo-cash-flow", "signal": "completed"})
    with TestClient(app) as restarted:
        restarted.cookies.update(cookies)
        assert restarted.get("/api/progress").json()["items"][0]["material"]["id"] == "demo-cash-flow"


def test_evaluation_report_requires_matching_algorithm_and_catalog(client, tmp_path, monkeypatch):
    engine = app.state.recommender
    path = tmp_path / "results.json"
    result = {
        "status": "awaiting_human_judgments",
        "catalog_version": engine.version,
        "algorithm_version": engine.algorithm_id,
        "metrics": None,
        "note": "No human labels",
    }
    path.write_text(json.dumps(result))
    monkeypatch.setenv("EVALUATION_PATH", str(path))
    assert client.get("/api/evaluation/results").json()["note"] == "No human labels"
    result["algorithm_version"] = "different-version"
    path.write_text(json.dumps(result))
    assert client.get("/api/evaluation/results").json()["status"] == "stale_catalog"


def test_database_failure_returns_safe_503(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("internal database configuration"))

    monkeypatch.setattr(Session, "execute", unavailable)
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert "internal database" not in response.text
