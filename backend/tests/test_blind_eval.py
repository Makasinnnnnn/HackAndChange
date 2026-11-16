"""Independent, synthetic checks for the contributor's CSV evaluation tool."""

import csv
import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("blind_eval", ROOT / "audit/score_blind_eval.py")
evaluation = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = evaluation
spec.loader.exec_module(evaluation)


def pair(solution, relevant, irrelevant=(), baseline=(), notes=""):
    return evaluation.Pair("q1", "Авторский запрос", "test", "", notes,
                           {"solution": list(solution), "baseline": list(baseline)},
                           list(relevant), list(irrelevant))


def test_short_ranking_does_not_inflate_precision_or_ndcg():
    scores, _, _, _ = evaluation.score_pairs([pair(["a"], ["a", "b"])], 10)
    assert scores[0].precision == pytest.approx(0.1)
    assert scores[0].recall == pytest.approx(0.5)
    assert scores[0].ndcg == pytest.approx(1 / (1 + 1 / math.log2(3)))


def test_empty_solution_is_a_measured_failure_not_a_skipped_pair():
    scores, baseline, _, skipped = evaluation.score_pairs([pair([], ["a"], baseline=["a"])], 10)
    assert not skipped
    assert scores[0].precision == scores[0].recall == scores[0].ndcg == 0
    assert baseline[0].recall == 1


def test_explicit_all_negative_judgments_count_as_zero():
    scores, _, _, skipped = evaluation.score_pairs([pair(["a"], [], ["a"])], 10)
    assert len(scores) == 1 and not skipped
    assert scores[0].precision == scores[0].recall == scores[0].ndcg == 0


def test_explicitly_captured_empty_baseline_counts_as_failure():
    row = pair(["a"], ["a"])
    row.baseline_captured = True
    scores, baseline, _, skipped = evaluation.score_pairs([row], 10)
    assert not skipped and len(scores) == len(baseline) == 1
    assert baseline[0].precision == baseline[0].recall == 0


def test_unjudged_pooled_material_skips_both_systems():
    scores, baseline, warnings, skipped = evaluation.score_pairs(
        [pair(["a"], ["a"], baseline=["unjudged"])], 10
    )
    assert not scores and not baseline and len(skipped) == 1 and warnings


def test_out_of_scope_false_positive_is_visible_in_report():
    rows = [pair(["a"], [], notes="out_of_scope")]
    scores, baseline, warnings, skipped = evaluation.score_pairs(rows, 10)
    report = evaluation.render_report(input_path=Path("input.csv"), output_path=Path("report.md"),
                                      k=10, pairs=rows, scores=scores, baseline_scores=baseline,
                                      warnings=warnings, skipped=skipped)
    assert "ошибочная непустая выдача решения: 1" in report


def write_csv(path, rows):
    fields = evaluation.REQUIRED_COLUMNS + evaluation.top_columns("solution", 10)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({"query_id": "q1", "query_text": "Авторский запрос", **row})


def test_conflicting_judgments_duplicate_queries_and_rank_gaps_are_errors(tmp_path):
    path = tmp_path / "input.csv"
    write_csv(path, [{"human_relevant_ids": "a", "human_irrelevant_ids": "a"}, {},
                     {"query_id": "q2", "top_2_material_id": "a"}])
    _, errors, _ = evaluation.load_pairs(path, 10)
    assert len(errors) == 3


def test_report_cannot_publish_real_details_outside_private(tmp_path):
    path = tmp_path / "input.csv"
    write_csv(path, [{"top_1_material_id": "a", "human_relevant_ids": "a"}])
    output = tmp_path / "public.md"
    assert evaluation.main(["--input", str(path), "--output", str(output)]) == 2
    assert not output.exists()


@pytest.mark.parametrize("k", ["0", "-1", "11"])
def test_invalid_cutoff_is_rejected(k):
    with pytest.raises(SystemExit) as error:
        evaluation.main(["--k", k])
    assert error.value.code == 2
