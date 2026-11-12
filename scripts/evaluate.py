"""Prepare blind candidate pools and calculate metrics only after human annotation."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog import load_catalog  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.evaluation import metrics  # noqa: E402
from app.models import Profile  # noqa: E402
from app.semantic import optional_encoder  # noqa: E402

QUERIES = [
    "Хочу привлечь клиентов в кофейню",
    "Как выбрать каналы продвижения бизнеса",
    "Нужен план рекламы для небольшого магазина",
    "Как оценить стоимость привлечения клиента",
    "Как избежать кассового разрыва",
    "Нужен платежный календарь для бизнеса",
    "Как рассчитать маржу и себестоимость",
    "Хочу научиться управлять финансами компании",
    "Как подготовиться к выбору налогового режима",
    "Нужен чек-лист документов для бухгалтера",
    "Хочу системно разобраться в налоговом учете",
    "Кто отвечает за налоговую отчетность в компании",
    "Планирую нанять первого сотрудника",
    "Нужен шаблон вопросов для собеседования",
    "Как научиться делегировать сотрудникам",
    "Хочу системно управлять растущей командой",
    "С чего начать запуск своего бизнеса",
    "Нужен бизнес-план на одной странице",
    "Как проверить идею перед открытием кофейни",
    "Хочу обучение запуску бизнеса с нуля",
    "Как найти узкое место в воронке продаж",
    "Нужен сценарий разговора с клиентом",
    "Как увеличить повторные продажи",
    "Хочу выстроить систему продаж в агентстве",
    "Что проверить в договоре с подрядчиком",
    "Нужен чек-лист проверки договора",
    "Как организовать проверку контрагента",
    "Как защитить бизнес при работе с подрядчиком",
    "Как начать продавать на маркетплейсе",
    "Нужна таблица расходов товара на маркетплейсе",
    "Как организовать работу магазина на маркетплейсе",
    "Как проверить прибыльность товара на Ozon",
]


def profiles():
    return [
        {
            "id": f"q{i + 1:02}",
            "query": query,
            "split": "test" if i % 3 == 0 else "dev",
            "profile": {
                "experience": "beginner" if i % 2 == 0 else "experienced",
                "urgency": "quick" if i % 4 in {0, 1} else "deep",
                **({"format": "document"} if i % 4 == 1 else {}),
            },
        }
        for i, query in enumerate(QUERIES)
    ]


def prepare(engine: Engine, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    judgments = directory / "judgments.csv"
    if judgments.exists():
        raise SystemExit("Judgments already exist; refusing to overwrite human work. Choose a new directory.")
    rows = []
    for p in profiles():
        profile = Profile.model_validate(p["profile"])
        candidates = {
            i.material.id
            for baseline in [True, False]
            for i in engine.recommend(p["query"], profile, limit=10, baseline=baseline).items
        }
        for mid in sorted(candidates):
            material = engine.by_id[mid]
            rows.append(
                {
                    "profile_id": p["id"],
                    "split": p["split"],
                    "query": p["query"],
                    "profile": json.dumps(p["profile"], ensure_ascii=False),
                    "material_id": mid,
                    "title": material.title,
                    "description": material.description,
                    "grade": "",
                    "label_source": "human",
                    "judge": "",
                    "catalog_version": engine.version,
                    "algorithm_version": engine.algorithm_id,
                }
            )
    (directory / "profiles.json").write_text(
        json.dumps(profiles(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with judgments.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {
        "status": "awaiting_human_judgments",
        "profiles": len(profiles()),
        "pairs_to_judge": len(rows),
        "catalog_version": engine.version,
        "algorithm_version": engine.algorithm_id,
        "metrics": None,
    }


def calculate(engine: Engine, directory: Path):
    records = list(csv.DictReader((directory / "judgments.csv").open(encoding="utf-8-sig")))
    judged = defaultdict(dict)
    for row in records:
        if row["catalog_version"] != engine.version or row.get("algorithm_version") != engine.algorithm_id:
            raise ValueError("Catalog changed: rebuild a separate evaluation pool")
        if row["grade"] == "":
            continue
        if row["label_source"] != "human" or not row["judge"].strip():
            raise ValueError("Quality report requires explicit human labels and judge attribution")
        grade = int(row["grade"])
        if grade not in range(4) or row["material_id"] not in engine.by_id:
            raise ValueError("Invalid relevance grade or material ID")
        judged[row["profile_id"]][row["material_id"]] = grade
    scores = {"dev": defaultdict(list), "test": defaultdict(list)}
    skipped = []
    for profile in profiles():
        qrels = judged[profile["id"]]
        routes = {
            name: engine.recommend(
                profile["query"], Profile.model_validate(profile["profile"]), baseline=name == "baseline"
            )
            for name in ["baseline", "personal"]
        }
        if not qrels or any(any(i.material.id not in qrels for i in r.items) for r in routes.values()):
            skipped.append(profile["id"])
            continue
        for name, route in routes.items():
            scores[profile["split"]][name].append(metrics([i.material.id for i in route.items], qrels))
    averaged = {
        split: {
            name: {key: sum(v[key] for v in values) / len(values) for key in values[0]}
            for name, values in groups.items()
            if values
        }
        for split, groups in scores.items()
    }
    return {
        "status": "calculated" if any(averaged.values()) else "awaiting_human_judgments",
        "catalog_version": engine.version,
        "algorithm_version": engine.algorithm_id,
        "metrics": averaged if any(averaged.values()) else None,
        "judged_profiles": len(profiles()) - len(skipped),
        "unjudged_profiles": skipped,
        "label_source": "human",
        "note": "Recall оценивается только относительно пула размеченных кандидатов. Это offline-оценка, не рост конверсии.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "calculate"])
    parser.add_argument("--directory", type=Path, default=ROOT / ".private/evaluation-demo")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--semantic", action="store_true")
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not directory.is_relative_to((ROOT / ".private").resolve()):
        raise SystemExit("Evaluation files stay under .private/ to prevent catalog leakage")
    if args.full:
        os.environ["CATALOG_MODE"] = "full"
        os.environ["CATALOG_PATH"] = str(ROOT / ".private/catalog.json")
    catalog, mode, version = load_catalog()
    semantic = None
    if args.semantic:
        os.environ["SEMANTIC_MODEL_DIR"] = str(ROOT / ".private/models/e5")
        semantic, reason = optional_encoder()
        if semantic is None:
            raise SystemExit(
                "Semantic evaluation requested but the local model is unavailable: " + str(reason)
            )
    engine = Engine(catalog, mode, version, semantic=semantic)
    result = prepare(engine, directory) if args.action == "prepare" else calculate(engine, directory)
    (directory / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
