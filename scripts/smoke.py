"""Exercise the live Docker stack without writing organizer data or credentials to stdout."""

import argparse
import json
from pathlib import Path

import httpx


def smoke(base: str, state_file: Path | None = None, verify_saved=False):
    with httpx.Client(base_url=base, timeout=30) as client:
        if verify_saved:
            state = json.loads(state_file.read_text())
            client.cookies.update(state["cookies"])
            response = client.get("/api/progress")
            response.raise_for_status()
            assert any(i["material"]["id"] == state["completed_id"] for i in response.json()["items"])
            return {"persistence_after_restart": "passed"}
        ready = client.get("/api/ready")
        ready.raise_for_status()
        boot = client.get("/api/bootstrap")
        boot.raise_for_status()
        payload = {
            "query": "Хочу привлечь клиентов в кофейню",
            "profile": {"urgency": "quick", "industry": "HoReCa"},
        }
        response = client.post("/api/recommendations", json=payload)
        response.raise_for_status()
        route = response.json()
        assert len(route["items"]) > 0 and all(i["reasons"] and i["next_action"] for i in route["items"])
        material = route["items"][0]["material"]["id"]
        feedback = client.post("/api/feedback", json={"material_id": material, "signal": "completed"})
        feedback.raise_for_status()
        again = client.post("/api/recommendations", json=payload)
        again.raise_for_status()
        assert material not in [i["material"]["id"] for i in again.json()["items"]]
        comparison = client.post("/api/demo/compare", json=payload)
        comparison.raise_for_status()
        compare = comparison.json()
        assert compare["baseline"]["catalog_version"] == compare["personal"]["catalog_version"]
        assert client.post("/api/recommendations", json={"query": "Помогите с бизнесом"}).json()[
            "clarification"
        ]
        assert client.post("/api/recommendations", json={"query": "x" * 1501}).status_code == 422
        assert client.get("/api/catalog/missing").status_code == 404
        if state_file:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(
                json.dumps({"cookies": dict(client.cookies), "completed_id": material}), encoding="utf-8"
            )
        return {"status": "passed", "catalog": ready.json(), "checks": 8}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:3080")
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--verify-saved", action="store_true")
    args = parser.parse_args()
    if args.state_file and not args.state_file.resolve().is_relative_to(
        (Path(__file__).resolve().parents[1] / ".private").resolve()
    ):
        raise SystemExit("Session state may only be stored under .private/")
    print(json.dumps(smoke(args.base, args.state_file, args.verify_saved), ensure_ascii=False))
