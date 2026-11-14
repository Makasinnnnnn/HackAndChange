"""Capture original 120-query matrix locally; never publish catalog-derived outputs."""

import argparse
import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def cases(suite="original"):
    if suite == "natural":
        data = json.loads((ROOT / "scripts/audit_natural_queries.json").read_text(encoding="utf-8"))
        result = [{**case, "split": "regression"} for case in data["cases"]]
        assert len(result) == 150 and len({case["query"] for case in result}) == 150
        return result
    data = json.loads((ROOT / "scripts/audit_queries.json").read_text(encoding="utf-8"))
    result = []
    for group_index, group in enumerate(data["groups"]):
        for index, query in enumerate(group["queries"]):
            result.append(
                {
                    "id": f"{group['name']}-{index + 1:02d}",
                    "group": group["name"],
                    "goal": group["goal"],
                    "query": query,
                    "split": "development" if index < (7 if group_index < 8 else 6) else "validation",
                }
            )
    assert len(result) == 120 and len({c["query"] for c in result}) == 120
    assert sum(c["split"] == "development" for c in result) == 80
    return result


def capture(base, output, split="all", suite="original", expect_algorithm=None):
    if suite == "natural" and split != "all":
        raise ValueError("Natural suite is a regression set, not an independent dev/test split")
    output = output.resolve()
    if not output.is_relative_to((ROOT / ".private").resolve()):
        raise ValueError("Catalog-derived audit evidence must stay in .private")
    if output.exists():
        raise ValueError("Use a new filename to preserve previous evidence")
    results = []
    with httpx.Client(base_url=base, timeout=60) as client:
        for _attempt in range(45):
            try:
                ready = client.get("/api/ready")
                if ready.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("API did not become ready in 45 attempts")
        ready.raise_for_status()
        for case in cases(suite):
            if split != "all" and case["split"] != split:
                continue
            started = time.perf_counter()
            # No source users or history. One explicit synthetic profile for every case.
            response = client.post("/api/recommendations", json={"query": case["query"], "profile": {}})
            response.raise_for_status()
            route = response.json()
            if expect_algorithm and route["algorithm"] != expect_algorithm:
                raise ValueError("Unexpected live algorithm: wait for the intended server version")
            assert route["catalog_version"] == ready.json()["catalog_version"]
            assert len({i["material"]["id"] for i in route["items"]}) == len(route["items"])
            assert all(item["reasons"] and item["next_action"] for item in route["items"])
            results.append(
                {**case, "http_ms": round((time.perf_counter() - started) * 1000, 2), "route": route}
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"catalog": ready.json(), "cases": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"cases": len(results), "split": split, "catalog": ready.json()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:3080")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=["all", "development", "validation"], default="all")
    parser.add_argument("--suite", choices=["original", "natural"], default="original")
    parser.add_argument("--expect-algorithm")
    args = parser.parse_args()
    print(
        json.dumps(
            capture(args.base, args.output, args.split, args.suite, args.expect_algorithm), ensure_ascii=False
        )
    )
