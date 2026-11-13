"""Recommendation pipeline: intent → hard eligibility → retrieval → rank → evidence."""

from __future__ import annotations

import time
from uuid import uuid4

from .models import Profile, Route
from .recommendation.eligibility import exclusion_reason
from .recommendation.explanation import constraint_evidence, recommendation, task_reasons
from .recommendation.index import SearchIndex
from .recommendation.intent import (
    material_topics,
    parse_intent,
    sector_compatibility,
    sector_match,
    topics_for,
)
from .recommendation.policy import (
    BASELINE_VERSION,
    CONSTRAINT_LIMIT,
    GENERAL_LIMIT,
    GENERAL_RELATIVE_FLOOR,
    MIN_RELEVANCE,
    PERSONAL_VERSION,
    SEMANTIC_CONFIG,
    TASK_DESCRIPTION_BONUS,
    TASK_TITLE_BONUS,
    WEIGHTS,
)
from .recommendation.ranking import Candidate, profile_score, select
from .recommendation.tasks import TASKS, task_evidence, task_matches, task_shortlist

__all__ = ["Engine", "SEMANTIC_CONFIG", "WEIGHTS", "sector_compatibility", "topics_for"]


class Engine:
    def __init__(self, materials, mode="demo", version="test", semantic=None):
        self.materials, self.mode, self.version = materials, mode, version
        self.by_id = {material.id: material for material in materials}
        self.semantic = semantic
        self.algorithm_id = ("e5-hybrid-" if semantic else "lexical-") + PERSONAL_VERSION
        self.index = SearchIndex(materials, semantic)
        # Compatibility for existing local diagnostics; all index ownership lives in SearchIndex.
        for name in ("documents", "word", "char", "word_matrix", "char_matrix", "semantic_matrix"):
            setattr(self, name, getattr(self.index, name))

    def recommend(self, query, profile=None, feedback=None, limit=5, baseline=False):
        if not isinstance(limit, int) or not 1 <= limit <= 10:
            raise ValueError("limit must be an integer between 1 and 10")
        started = time.perf_counter()
        profile = profile or Profile()
        feedback = feedback or {}
        intent = parse_intent(query, baseline)
        route_args = dict(
            route_id=str(uuid4()),
            algorithm=BASELINE_VERSION if baseline else self.algorithm_id,
            query=intent.query,
            profile=profile,
            catalog_mode=self.mode,
            catalog_version=self.version,
            active_profile_fields=[],
        )
        excluded_count = 0

        def response(items=None, clarification=None, notice=None, count=0, general=False):
            items = items or []
            active = (
                []
                if baseline
                else [
                    key
                    for key, value in profile.model_dump().items()
                    if value is not None and any(item.signals.get(key, 0) > 0 for item in items)
                ]
            )
            return Route(
                **{**route_args, "active_profile_fields": active},
                match_scope="general" if general else "task",
                items=items,
                clarification=clarification,
                notice=notice,
                elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                excluded_count=excluded_count,
                candidate_count=count,
            )

        if not self.materials:
            return response(clarification="Каталог пока пуст. Подключите материалы.")
        if intent.vague:
            return response(
                clarification="Какую задачу решаем: привлечь клиентов, разобраться с финансами или запустить бизнес?"
            )
        if intent.clarification:
            return response(clarification=intent.clarification)
        eligible = []
        for index, material in enumerate(self.materials):
            reason = exclusion_reason(material, intent, feedback, baseline)
            if reason == "feedback":
                excluded_count += 1
            if reason is None:
                eligible.append(index)
        if not eligible:
            return response(
                clarification="Подходящих доступных материалов не осталось. Уточните задачу или проверьте отметки изученного."
                if excluded_count
                else "В каталоге нет подтверждённого материала по этой конкретной задаче. Уточните запрос или выберите смежную тему."
            )

        evidence = self.index.search(intent.search, baseline)
        word_peak = float(evidence.word[eligible].max())
        char_peak = float(evidence.char[eligible].max())
        semantic_peak = float(evidence.semantic[eligible].max()) if evidence.semantic is not None else 0.0
        if (
            not intent.topics
            and not intent.tasks
            and word_peak < 0.10
            and char_peak < 0.18
            and semantic_peak < SEMANTIC_CONFIG["floor"]
        ):
            return response(
                clarification="В каталоге нет уверенного совпадения. Опишите бизнес-задачу другими словами."
            )
        if (
            not baseline
            and evidence.semantic is not None
            and not intent.topics
            and not intent.tasks
            and word_peak < SEMANTIC_CONFIG["unknown_word_floor"]
            and semantic_peak < SEMANTIC_CONFIG["unknown_floor"]
        ):
            return response(
                clarification="Точного материала не нашли. Уточните задачу или выберите более общее направление."
            )

        liked_topics = set()
        for mid, signal in feedback.items():
            if signal == "helpful" and mid in self.by_id:
                liked_topics.update(material_topics(self.by_id[mid]))
        candidates = []
        lexical = evidence.lexical
        for index in eligible:
            material = self.materials[index]
            matched_topics = intent.topics & material_topics(material)
            lexical_relevance = min(
                1.0,
                float(lexical[index])
                + ((0.20 if baseline else 0.0 if intent.tasks else 0.12) if matched_topics else 0),
            )
            matched_tasks = task_evidence(material, intent.tasks)
            title_tasks = intent.tasks & task_matches(material.title)
            if matched_tasks:
                lexical_relevance = min(
                    1.0, lexical_relevance + (TASK_TITLE_BONUS if title_tasks else TASK_DESCRIPTION_BONUS)
                )
            semantic_similarity = float(evidence.semantic[index]) if evidence.semantic is not None else None
            if (
                semantic_similarity is not None
                and lexical_relevance < SEMANTIC_CONFIG["lexical_evidence"]
                and semantic_similarity
                < max(SEMANTIC_CONFIG["floor"], semantic_peak - SEMANTIC_CONFIG["margin"])
            ):
                continue
            semantic_relevance = (
                max(0.0, (semantic_similarity - SEMANTIC_CONFIG["offset"]) / SEMANTIC_CONFIG["span"])
                if semantic_similarity is not None
                else 0.0
            )
            relevance = (
                min(
                    1.0,
                    (1 - SEMANTIC_CONFIG["weight"]) * lexical_relevance
                    + SEMANTIC_CONFIG["weight"] * semantic_relevance,
                )
                if semantic_similarity is not None
                else lexical_relevance
            )
            if relevance < MIN_RELEVANCE:
                continue
            signals = {"relevance": round(relevance, 6)}
            if semantic_similarity is not None:
                signals["semantic_similarity"] = round(semantic_similarity, 6)
            reasons = (
                ["По задаче: " + ", ".join(sorted(matched_topics)).lower()]
                if matched_topics
                else [
                    "Близость задачи и описания рассчитана локальной моделью E5"
                    if semantic_similarity is not None and lexical[index] < 0.075
                    else "Найдено текстовое совпадение с темой поиска"
                ]
            )
            if matched_tasks:
                signals.update({"task_" + key: 1.0 for key in sorted(matched_tasks)})
                reasons = task_reasons(material, matched_tasks)
            if "fixed_ad_spend" in intent.constraints:
                constraint_signals, reasons = constraint_evidence(material)
                signals.update(constraint_signals)
            if not baseline and intent.sectors and not sector_match(material, intent.sectors):
                reasons.insert(0, "Общий бизнес-материал; совпадение вашей отрасли не подтверждено")
            score = (
                relevance
                if baseline
                else profile_score(material, profile, liked_topics, intent.query, relevance, signals, reasons)
            )
            candidates.append(Candidate(material, signals, reasons, score))

        count = len(candidates)
        if not candidates:
            return response(
                clarification="Точного материала не нашли. Уточните задачу или выберите более общее направление."
            )
        if intent.tasks:
            candidates = task_shortlist(candidates, GENERAL_RELATIVE_FLOOR)
            limit = min(limit, CONSTRAINT_LIMIT)
        elif intent.constraints or intent.requested_format or not baseline:
            strongest = max(candidate.score for candidate in candidates)
            candidates = [
                candidate for candidate in candidates if candidate.score >= strongest * GENERAL_RELATIVE_FLOOR
            ]
            limit = min(limit, CONSTRAINT_LIMIT)
        chosen = select(candidates, limit, baseline)
        general = (
            not baseline
            and bool(intent.sectors)
            and not any(sector_match(candidate.material, intent.sectors) for candidate in chosen)
        )
        if general:
            strongest = max(candidate.score for candidate in candidates)
            candidates = [
                candidate for candidate in candidates if candidate.score >= strongest * GENERAL_RELATIVE_FLOOR
            ]
            chosen = select(candidates, min(limit, GENERAL_LIMIT), baseline)
        items = [recommendation(candidate) for candidate in chosen]
        notice = None
        if general:
            notice = "Отраслевое совпадение не подтверждено. Это общие материалы по бизнес-задаче; подборка ограничена тремя позициями."
        elif max(item.signals["relevance"] for item in items) < 0.20:
            notice = "Совпадение слабое: это ближайшие материалы, а не точный ответ. Уточните задачу для более полезной подборки."
        missing_tasks = intent.tasks - {
            key.removeprefix("task_") for item in items for key in item.signals if key.startswith("task_")
        }
        if missing_tasks:
            missing = (
                "Нет подтверждённого материала для части запроса: "
                + "; ".join(TASKS[key][0] for key in sorted(missing_tasks))
                + "."
            )
            notice = (notice + " " if notice else "") + missing
        return response(items=items, notice=notice, count=count, general=general)
