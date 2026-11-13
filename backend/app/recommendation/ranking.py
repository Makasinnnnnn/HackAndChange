"""Bounded profile bonuses and deterministic diversity selection."""

from dataclasses import dataclass

from ..models import Material
from .intent import FORMAT_NAMES, industry_key, material_topics
from .policy import DIVERSITY_PENALTY, TASK_COVERAGE_BONUS, WEIGHTS


@dataclass
class Candidate:
    material: Material
    signals: dict[str, float]
    reasons: list[str]
    score: float
    rank_score: float = 0.0
    diversity_penalty: float = 0.0
    coverage_bonus: float = 0.0
    coverage_priority: bool = False


def profile_score(material, profile, liked_topics, query, relevance, signals, reasons):
    checks = {
        "industry": None
        if not profile.industry or not material.industries
        else float(
            any(industry_key(profile.industry) == industry_key(value) for value in material.industries)
        ),
        "stage": None
        if not profile.stage or (not material.stage and "Запуск бизнеса" not in material_topics(material))
        else float(profile.stage in material.stage)
        if material.stage
        else float(profile.stage in {"idea", "start"}),
        "experience": None
        if not profile.experience or material.difficulty is None
        else float(profile.experience == material.difficulty),
        "format": None if not profile.format else float(profile.format == material.source_type),
        "urgency": None
        if not profile.urgency
        else float(
            material.source_type
            in (
                {"article", "document", "calculator"} if profile.urgency == "quick" else {"course", "webinar"}
            )
        ),
    }
    labels = {
        "industry": f"Есть отраслевая метка «{profile.industry}»",
        "stage": "Подходит для выбранного этапа бизнеса"
        if material.stage
        else "В каталоге это раздел о запуске бизнеса",
        "experience": "Соответствует указанному опыту",
        "format": "Выбран предпочитаемый формат: " + FORMAT_NAMES[material.source_type],
        "urgency": "Подходит для быстрого применения"
        if profile.urgency == "quick"
        else "Подходит для последовательного обучения",
    }
    for key, value in checks.items():
        if value is not None:
            signals[key] = value
            if value:
                reasons.append(labels[key])
    if liked_topics:
        signals["feedback"] = float(bool(liked_topics & material_topics(material)))
        if signals["feedback"]:
            reasons.append("Тема связана с материалами, которые вы отметили полезными")
    bonus = sum(
        (0.04 if k == "industry" and profile.industry in {"Услуги", "B2B", "B2G"} else WEIGHTS[k]) * v
        for k, v in signals.items()
        if k in WEIGHTS and k != "relevance"
    )
    score = relevance * (1.0 + bonus / WEIGHTS["relevance"])
    if material.source_type == "glossary" and not any(
        word in query.casefold() for word in ("что такое", "термин", "определение")
    ):
        score *= 0.75
    return score


def select(candidates, limit, baseline=False):
    remaining = list(candidates)
    selected = []
    while remaining and len(selected) < limit:

        def rank(candidate):
            penalty = (
                0.0
                if baseline
                else DIVERSITY_PENALTY
                * sum(
                    previous.material.source_type == candidate.material.source_type for previous in selected
                )
            )
            covered = {key for previous in selected for key in previous.signals if key.startswith("task_")}
            coverage = (
                0.0
                if baseline
                else TASK_COVERAGE_BONUS
                * sum(key.startswith("task_") and key not in covered for key in candidate.signals)
            )
            return candidate.score - penalty + coverage, candidate.signals["relevance"], candidate.material.id

        covered_tasks = {key for previous in selected for key in previous.signals if key.startswith("task_")}
        uncovered_pool = [
            candidate
            for candidate in remaining
            if any(key.startswith("task_") and key not in covered_tasks for key in candidate.signals)
        ]
        prioritize_coverage = bool(not baseline and selected and uncovered_pool)
        chosen = max(uncovered_pool if prioritize_coverage else remaining, key=rank)
        chosen.coverage_priority = prioritize_coverage
        chosen.rank_score = rank(chosen)[0]
        covered = {key for previous in selected for key in previous.signals if key.startswith("task_")}
        chosen.coverage_bonus = (
            0.0
            if baseline
            else TASK_COVERAGE_BONUS
            * sum(key.startswith("task_") and key not in covered for key in chosen.signals)
        )
        chosen.diversity_penalty = max(0.0, chosen.score + chosen.coverage_bonus - chosen.rank_score)
        selected.append(chosen)
        remaining.remove(chosen)
    return selected
