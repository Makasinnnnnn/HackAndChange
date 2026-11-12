"""Reproducible technical benchmark; never claims human relevance or conversion."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from app.catalog import load_catalog  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.models import Profile  # noqa: E402
from app.semantic import optional_encoder  # noqa: E402
from evaluate import profiles  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semantic", action="store_true")
    args = parser.parse_args()
    os.environ["CATALOG_MODE"] = "full"
    os.environ["CATALOG_PATH"] = str(ROOT / ".private/catalog.json")
    os.environ["SEMANTIC_MODEL_DIR"] = str(ROOT / ".private/models/e5")
    started = time.perf_counter()
    catalog, mode, version = load_catalog()
    encoder, reason = optional_encoder() if args.semantic else (None, None)
    if args.semantic and encoder is None:
        raise SystemExit("Missing semantic encoder: " + str(reason))
    engine = Engine(catalog, mode, version, encoder)
    initialization = time.perf_counter() - started
    elapsed = {"baseline": [], "personal": []}
    empty = {"baseline": 0, "personal": 0}
    overlap = []
    for row in profiles():
        routes = {}
        for name in elapsed:
            start = time.perf_counter()
            route = engine.recommend(row["query"], Profile.model_validate(row["profile"]), baseline=name == "baseline")
            elapsed[name].append((time.perf_counter() - start) * 1000)
            ids = [i.material.id for i in route.items]
            assert len(ids) == len(set(ids)) and set(ids) <= engine.by_id.keys()
            assert all(np.isfinite(i.rank_score) for i in route.items)
            routes[name] = set(ids)
            empty[name] += not ids
        union = routes["baseline"] | routes["personal"]
        overlap.append(len(routes["baseline"] & routes["personal"]) / len(union) if union else 1)
    report = {"catalog_version": version, "algorithm": engine.algorithm_id, "materials": len(catalog), "profiles": len(profiles()), "initialization_seconds": round(initialization, 2), "latency_ms": {name: {"p50": round(float(np.percentile(values, 50)), 2), "p95": round(float(np.percentile(values, 95)), 2)} for name,values in elapsed.items()}, "empty_routes": empty, "mean_jaccard": round(float(np.mean(overlap)), 3), "invariants": "passed", "quality_metrics": None, "note": "Single-process local CPU timings, one pass, no HTTP/LLM time. Empty counts and overlap are diagnostics, not relevance quality. No human labels."}
    output = ROOT / (".private/benchmark-e5.json" if args.semantic else ".private/benchmark-lexical.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
