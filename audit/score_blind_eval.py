#!/usr/bin/env python3
"""Score a filled blind-eval CSV: Precision@10 / pooled Recall@10 / NDCG@10.

Только stdlib. Не запускается на пустом шаблоне: если строк для разметки нет,
скрипт завершается с кодом 2 и ничего не пишет.

Что считает
-----------
Для каждой размеченной пары (запрос -> список материалов):
  * Precision@k  = |top_k ∩ relevant| / k_eff
  * pooled Recall@k = |top_k ∩ relevant| / |relevant|
  * NDCG@k       = DCG@k_eff / IDCG@k_eff, бинарная релевантность (1/0)
  * MRR@k        = 1 / позиция первого релевантного (0, если нет)
где k_eff = min(k, число фактически показанных материалов).

Метрики считаются и для решения (`top_*`), и для бейзлайна (`baseline_top_*`),
если baseline-колонки заполнены.

Честные ограничения (попадают в отчёт, не только в docstring)
--------------------------------------------------------------
1. Это **pooled recall**, а не истинный recall: размечен только пул показанных
   карточек. Материал, которого система не показала, никто не оценивал.
2. Неразименённые карточки в выдаче считаются нерелевантными (0), их число
   выводится в отчёт отдельным счётчиком.
3. NDCG — бинарный (градуированной шкалы в CSV нет).
4. Агрегация — macro-среднее по парам, не micro.
5. При n < 10 пар метрики нестабильны: в отчёт попадает предупреждение.

Разметка (см. audit/blind_eval_queries.md)
------------------------------------------
* `human_relevant_ids`, `human_irrelevant_ids`: id через `|` или `;`.
* Пустая `human_relevant_ids` -> пара пропускается с warning.
* Строка, начинающаяся с `# example`, игнорируется.
* `notes`, содержащий `out_of_scope`, исключает пару из метрик (учитывается
  отдельно как кейс «правильный отказ»).

Использование
-------------
    python audit/score_blind_eval.py --validate-only      # проверить CSV, не считать
    python audit/score_blind_eval.py                      # посчитать и написать отчёт
    python audit/score_blind_eval.py --k 10 --input audit/blind_eval_template.csv \
        --output audit/blind_eval_report.md
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "blind_eval_template.csv"
DEFAULT_OUTPUT = SCRIPT_DIR / "blind_eval_report.md"
DEFAULT_K = 10

EXAMPLE_MARKER = "# example"
SYSTEMS = ("solution", "baseline")

REQUIRED_COLUMNS = [
    "query_id",
    "query_text",
    "category",
    "expected_topic",
    "human_relevant_ids",
    "human_irrelevant_ids",
    "notes",
]


def top_columns(system: str, k: int) -> list[str]:
    prefix = "" if system == "solution" else "baseline_"
    return [f"{prefix}top_{position}_material_id" for position in range(1, k + 1)]


def split_ids(value: str) -> list[str]:
    """Разбирает `a|b;c` и запятые. Терпит пробелы и пустые значения."""
    if not value:
        return []
    parts = re.split(r"[|;,]", value)
    return [part.strip() for part in parts if part.strip()]


def dedupe_keep_order(values: list[str]) -> tuple[list[str], int]:
    seen: set[str] = set()
    output: list[str] = []
    duplicates = 0
    for value in values:
        if value in seen:
            duplicates += 1
            continue
        seen.add(value)
        output.append(value)
    return output, duplicates


@dataclass
class Pair:
    query_id: str
    query_text: str
    category: str
    expected_topic: str
    notes: str
    tops: dict[str, list[str]]
    relevant: list[str]
    irrelevant: list[str]
    warnings: list[str] = field(default_factory=list)


@dataclass
class Score:
    query_id: str
    category: str
    system: str
    k_eff: int
    shown: int
    hits: int
    unjudged: int
    precision: float
    recall: float
    ndcg: float
    mrr: float


def load_pairs(path: Path, k: int) -> tuple[list[Pair], list[str], list[str]]:
    """Возвращает (пары, глобальные ошибки, глобальные предупреждения)."""
    errors: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return [], [f"Файл не найден: {path}"], warnings

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [name for name in REQUIRED_COLUMNS if name not in header]
        if missing:
            errors.append("В CSV нет обязательных столбцов: " + ", ".join(missing))
            return [], errors, warnings
        for column in top_columns("solution", k) + top_columns("baseline", k):
            if column not in header:
                warnings.append(f"В CSV нет столбца {column}: он считается пустым.")
        rows = list(reader)

    pairs: list[Pair] = []
    for index, row in enumerate(rows, start=2):
        first_cell = (row.get("query_id") or "").strip()
        if first_cell.casefold().startswith(EXAMPLE_MARKER):
            continue
        if not first_cell and not (row.get("query_text") or "").strip():
            continue  # полностью пустая строка

        item_warnings: list[str] = []
        tops: dict[str, list[str]] = {}
        for system in SYSTEMS:
            values = [(row.get(column) or "").strip() for column in top_columns(system, k)]
            values = [value for value in values if value]
            unique, duplicates = dedupe_keep_order(values)
            if duplicates:
                item_warnings.append(f"{system}: повторяющиеся id в выдаче ({duplicates}), оставлен первый")
            if len(unique) > k:
                item_warnings.append(f"{system}: больше {k} id, лишние отброшены")
                unique = unique[:k]
            tops[system] = unique

        relevant = split_ids(row.get("human_relevant_ids") or "")
        irrelevant = split_ids(row.get("human_irrelevant_ids") or "")
        conflicts = sorted(set(relevant) & set(irrelevant))
        if conflicts:
            item_warnings.append(
                "id одновременно в relevant и irrelevant (считаем релевантным): " + ", ".join(conflicts)
            )
        not_shown = sorted(set(relevant) - set(tops["solution"]) - set(tops["baseline"]))
        if not_shown:
            item_warnings.append(
                "relevant id, которых нет в выдаче (recall будет < 1): " + ", ".join(not_shown)
            )

        pairs.append(
            Pair(
                query_id=first_cell or f"row{index}",
                query_text=(row.get("query_text") or "").strip(),
                category=(row.get("category") or "unspecified").strip() or "unspecified",
                expected_topic=(row.get("expected_topic") or "").strip(),
                notes=(row.get("notes") or "").strip(),
                tops=tops,
                relevant=relevant,
                irrelevant=irrelevant,
                warnings=item_warnings,
            )
        )
    return pairs, errors, warnings


def score_pairs(pairs: list[Pair], k: int) -> tuple[list[Score], list[Score], list[str], list[Pair]]:
    scores: list[Score] = []
    baseline_scores: list[Score] = []
    warnings: list[str] = []
    skipped: list[Pair] = []

    for pair in pairs:
        for message in pair.warnings:
            warnings.append(f"[{pair.query_id}] {message}")

        if "out_of_scope" in pair.notes.casefold():
            warnings.append(f"[{pair.query_id}] помечено out_of_scope: в метрики не идёт")
            skipped.append(pair)
            continue
        if not pair.relevant:
            warnings.append(
                f"[{pair.query_id}] пустой human_relevant_ids: пара пропущена "
                "(если это честный отказ — поставьте out_of_scope в notes)"
            )
            skipped.append(pair)
            continue

        relevant = set(pair.relevant)
        for system in SYSTEMS:
            tops = pair.tops[system]
            if not tops:
                if system == "baseline":
                    continue  # baseline может отсутствовать целиком
                warnings.append(f"[{pair.query_id}] пустая выдача решения: пара пропущена")
                skipped.append(pair)
                break
            k_eff = min(k, len(tops))
            shown = tops[:k_eff]
            hits = sum(1 for material_id in shown if material_id in relevant)
            unjudged = sum(
                1 for material_id in shown if material_id not in relevant and material_id not in set(pair.irrelevant)
            )
            dcg = sum(
                1.0 / math.log2(position + 2)
                for position, material_id in enumerate(shown)
                if material_id in relevant
            )
            ideal_hits = min(len(relevant), k_eff)
            idcg = sum(1.0 / math.log2(position + 2) for position in range(ideal_hits))
            ndcg = dcg / idcg if idcg > 0 else 0.0
            mrr = next(
                (1.0 / (position + 1) for position, material_id in enumerate(shown) if material_id in relevant),
                0.0,
            )
            entry = Score(
                query_id=pair.query_id,
                category=pair.category,
                system=system,
                k_eff=k_eff,
                shown=len(shown),
                hits=hits,
                unjudged=unjudged,
                precision=hits / k_eff,
                recall=hits / len(relevant),
                ndcg=ndcg,
                mrr=mrr,
            )
            scores.append(entry) if system == "solution" else baseline_scores.append(entry)
            if k_eff < k:
                warnings.append(
                    f"[{pair.query_id}] {system}: показано {k_eff} < {k}; метрики @{k} считаны по k_eff={k_eff}"
                )
    return scores, baseline_scores, warnings, skipped


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(scores: list[Score]) -> dict[str, float]:
    return {
        "n": float(len(scores)),
        "precision": mean([item.precision for item in scores]),
        "recall": mean([item.recall for item in scores]),
        "ndcg": mean([item.ndcg for item in scores]),
        "mrr": mean([item.mrr for item in scores]),
        "k_eff": mean([float(item.k_eff) for item in scores]),
        "unjudged": mean([float(item.unjudged) for item in scores]),
    }


def fmt(value: float) -> str:
    return f"{value:.3f}"


def render_report(
    *,
    input_path: Path,
    output_path: Path,
    k: int,
    pairs: list[Pair],
    scores: list[Score],
    baseline_scores: list[Score],
    warnings: list[str],
    skipped: list[Pair],
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    solution = summarize(scores)
    baseline = summarize(baseline_scores) if baseline_scores else None

    annotated = {pair.query_id for pair in pairs} - {pair.query_id for pair in skipped}
    baseline_pair_ids = {item.query_id for item in baseline_scores}
    paired_ids = sorted(annotated & baseline_pair_ids)

    lines: list[str] = []
    lines.append("# Blind eval — отчёт")
    lines.append("")
    lines.append(f"- Сгенерирован: {now}")
    lines.append(f"- Вход: `{input_path}`")
    lines.append(f"- k: {k}")
    lines.append(f"- Строк в CSV (без example): {len(pairs)}")
    lines.append(f"- Оценено пар: {len(annotated)}")
    lines.append(f"- Пропущено пар: {len(skipped)}")
    lines.append(f"- Пар с baseline: {len(paired_ids)}")
    lines.append("")

    # --- предупреждения о методе, до цифр
    lines.append("## Ограничения этого расчёта (читать до цифр)")
    lines.append("")
    lines.append("1. **Pooled Recall**, не истинный recall: размечен только пул показанных карточек.")
    lines.append("2. Неразименённые карточки в выдаче считаются нерелевантными (0).")
    lines.append("   Среднее число таких карточек на пару: " + (f"{solution['unjudged']:.2f}" if scores else "—") + ".")
    lines.append("3. NDCG бинарный (градуированной шкалы в CSV нет).")
    lines.append("4. Агрегация — macro по парам.")
    if len(annotated) < 10:
        lines.append(f"5. **n = {len(annotated)} < 10: метрики нестабильны**, доверительный интервал широкий.")
    lines.append("6. Это метки людей на малом наборе; они не превращаются в «доказанное превосходство».")
    lines.append("")

    if not baseline_scores:
        lines.append("## Baseline")
        lines.append("")
        lines.append("**baseline не оценён: нет разделения в capture.**")
        lines.append("")
        lines.append("Baseline-колонки (`baseline_top_*`) пусты или не сняты. Метрики ниже относятся")
        lines.append("только к решению. Подменять baseline выводом решения нельзя — сравнивать не с чем.")
        lines.append("")

    # --- сводная таблица
    lines.append("## Сводка")
    lines.append("")
    header = "| Система | пар | Precision@k | pooled Recall@k | NDCG@k | MRR@k | средний k_eff |"
    lines.append(header)
    lines.append("|---|---|---|---|---|---|---|")
    lines.append(
        f"| решение | {int(solution['n'])} | {fmt(solution['precision'])} | {fmt(solution['recall'])} | "
        f"{fmt(solution['ndcg'])} | {fmt(solution['mrr'])} | {solution['k_eff']:.1f} |"
    )
    if baseline:
        lines.append(
            f"| baseline | {int(baseline['n'])} | {fmt(baseline['precision'])} | {fmt(baseline['recall'])} | "
            f"{fmt(baseline['ndcg'])} | {fmt(baseline['mrr'])} | {baseline['k_eff']:.1f} |"
        )
    else:
        lines.append("| baseline | — | — | — | — | — | — |")
    lines.append("")

    if baseline and paired_ids:
        by_id = {item.query_id: item for item in baseline_scores}
        solution_by_id = {item.query_id: item for item in scores}
        deltas = {
            "precision": mean([solution_by_id[qid].precision - by_id[qid].precision for qid in paired_ids]),
            "recall": mean([solution_by_id[qid].recall - by_id[qid].recall for qid in paired_ids]),
            "ndcg": mean([solution_by_id[qid].ndcg - by_id[qid].ndcg for qid in paired_ids]),
        }
        lines.append("### Разница на общих парах (решение − baseline)")
        lines.append("")
        lines.append(f"Пар в сравнении: {len(paired_ids)}")
        lines.append("")
        lines.append("| Метрика | Δ |")
        lines.append("|---|---|")
        lines.append(f"| Precision@{k} | {deltas['precision']:+.3f} |")
        lines.append(f"| pooled Recall@{k} | {deltas['recall']:+.3f} |")
        lines.append(f"| NDCG@{k} | {deltas['ndcg']:+.3f} |")
        lines.append("")

    # --- по категориям
    if scores:
        lines.append("## По категориям запросов (решение)")
        lines.append("")
        lines.append("| Категория | пар | P@k | R@k | NDCG@k |")
        lines.append("|---|---|---|---|---|")
        grouped: dict[str, list[Score]] = defaultdict(list)
        for item in scores:
            grouped[item.category].append(item)
        for category in sorted(grouped):
            group = grouped[category]
            lines.append(
                f"| {category} | {len(group)} | {fmt(mean([i.precision for i in group]))} | "
                f"{fmt(mean([i.recall for i in group]))} | {fmt(mean([i.ndcg for i in group]))} |"
            )
        lines.append("")

    # --- построчно
    if scores:
        lines.append("## Построчно (решение)")
        lines.append("")
        lines.append("| query_id | k_eff | hits | P | R | NDCG | неразмечено |")
        lines.append("|---|---|---|---|---|---|---|")
        for item in scores:
            lines.append(
                f"| {item.query_id} | {item.k_eff} | {item.hits} | {fmt(item.precision)} | "
                f"{fmt(item.recall)} | {fmt(item.ndcg)} | {item.unjudged} |"
            )
        lines.append("")

    # --- пропуски и предупреждения
    lines.append("## Пропущенные пары")
    lines.append("")
    if skipped:
        for pair in skipped:
            reason = "out_of_scope" if "out_of_scope" in pair.notes.casefold() else "нет human_relevant_ids"
            lines.append(f"- `{pair.query_id}` — {reason}")
    else:
        lines.append("- нет")
    lines.append("")

    lines.append("## Предупреждения")
    lines.append("")
    if warnings:
        for message in warnings:
            lines.append(f"- {message}")
    else:
        lines.append("- нет")
    lines.append("")

    lines.append("## Как воспроизвести")
    lines.append("")
    lines.append("```")
    lines.append(f"python audit/score_blind_eval.py --input {input_path.name} --output {output_path.name} --k {k}")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Посчитать blind-eval метрики по размеченному CSV.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="только проверить структуру CSV, ничего не считать и не писать",
    )
    args = parser.parse_args(argv)

    if args.k != DEFAULT_K:
        print(
            f"Внимание: k={args.k}, а столбцы шаблона рассчитаны на {DEFAULT_K}. "
            "Для k>10 нужны дополнительные столбцы top_*.",
            file=sys.stderr,
        )

    pairs, errors, load_warnings = load_pairs(args.input, args.k)
    for error in errors:
        print(f"ОШИБКА: {error}", file=sys.stderr)
    if errors:
        return 2

    for message in load_warnings:
        print(f"ВНИМАНИЕ: {message}", file=sys.stderr)

    if not pairs:
        print(
            f"ОШИБКА: в {args.input} нет размеченных строк (только заголовок и/или example).\n"
            "Шаблон не считается: сначала заполните пары и разметьте human_relevant_ids.",
            file=sys.stderr,
        )
        return 2

    if args.validate_only:
        print(f"OK: структура корректна, строк для разметки: {len(pairs)}")
        for pair in pairs:
            print(f"  {pair.query_id}: top={len(pair.tops['solution'])}, relevant={len(pair.relevant)}")
        return 0

    scores, baseline_scores, warnings, skipped = score_pairs(pairs, args.k)

    if not scores:
        for message in warnings:
            print(f"ВНИМАНИЕ: {message}", file=sys.stderr)
        print(
            "ОШИБКА: ни одной пары не удалось оценить (все human_relevant_ids пусты или out_of_scope).\n"
            "Отчёт не записан — иначе получились бы нули, выданные за метрики.",
            file=sys.stderr,
        )
        return 3

    report = render_report(
        input_path=args.input,
        output_path=args.output,
        k=args.k,
        pairs=pairs,
        scores=scores,
        baseline_scores=baseline_scores,
        warnings=load_warnings + warnings,
        skipped=skipped,
    )
    args.output.write_text(report, encoding="utf-8")

    solution = summarize(scores)
    print(f"Оценено пар: {int(solution['n'])}")
    print(
        f"Precision@{args.k}(k_eff по доступным)={solution['precision']:.3f}  "
        f"pooled Recall@{args.k}={solution['recall']:.3f}  "
        f"NDCG@{args.k}={solution['ndcg']:.3f}  MRR@{args.k}={solution['mrr']:.3f}"
    )
    if baseline_scores:
        baseline = summarize(baseline_scores)
        print(f"baseline: n={int(baseline['n'])}  P={baseline['precision']:.3f}  "
              f"R={baseline['recall']:.3f}  NDCG={baseline['ndcg']:.3f}")
    else:
        print("baseline не оценён: нет разделения в capture")
    print(f"Отчёт: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
