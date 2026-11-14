"""Сырой запрос -> top-k без онбординга. Для blind eval и отладки retrieval.

Не заменяет API: тот же Engine, тот же каталог, пустой Profile().
Пишет JSON в stdout, ничего не сохраняет на диск.

Требования: pip install -r backend/requirements.txt (scikit-learn уже там).
В окружении без sklearn скрипт не запустится — это ожидаемо, для запуска
используйте машину с полным окружением или Docker.

Пример: python -m scripts.query "хочу открыть кофейню" --top 10 --baseline --pretty
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.catalog import load_catalog  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.models import Profile  # noqa: E402
from app.semantic import optional_encoder  # noqa: E402


def capture(engine, query, top, baseline):
    route = engine.recommend(query, Profile(), limit=top, baseline=baseline)
    return {
        "algorithm": route.algorithm,
        "match_scope": route.match_scope,
        "clarification": route.clarification,
        "notice": route.notice,
        "excluded_count": route.excluded_count,
        "candidate_count": route.candidate_count,
        "material_ids": [item.material.id for item in route.items],
        "items": [
            {
                "rank": rank,
                "material_id": item.material.id,
                "title": item.material.title,
                "score": round(item.score, 6),
            }
            for rank, item in enumerate(route.items, start=1)
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Сырой запрос через Engine без профиля.")
    parser.add_argument("query")
    parser.add_argument(
        "--profile",
        default="empty",
        choices=["empty"],
        help="пока поддерживается только пустой профиль: cold start",
    )
    parser.add_argument("--top", type=int, default=10, choices=range(1, 11))
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="добавить выдачу baseline (parse_intent(baseline=True))",
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="включить энкодер из SEMANTIC_MODEL_DIR, если он есть",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    materials, mode, version = load_catalog()
    encoder, reason = optional_encoder() if args.semantic else (None, None)
    if args.semantic and encoder is None:
        print(f"ВНИМАНИЕ: энкодер недоступен ({reason}), работаем лексически", file=sys.stderr)
    engine = Engine(materials, mode, version, semantic=encoder)

    payload = {
        "query": args.query,
        "profile": "empty",
        "top": args.top,
        "catalog_mode": mode,
        "catalog_version": version,
        "materials": len(materials),
        "semantic": encoder is not None,
        "solution": capture(engine, args.query, args.top, baseline=False),
    }
    if args.baseline:
        payload["baseline"] = capture(engine, args.query, args.top, baseline=True)

    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
