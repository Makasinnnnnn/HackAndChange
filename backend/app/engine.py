"""Deterministic lexical retrieval and evidence-based personal reranking.

This is a lexical/metadata system, not an embedding model or a generative LLM.
"""

from __future__ import annotations

import re
import time
from uuid import uuid4

from sklearn.feature_extraction.text import TfidfVectorizer

from .models import Material, Profile, Recommendation, Route

WEIGHTS = {
    "relevance": 0.60,
    "industry": 0.11,
    "stage": 0.08,
    "experience": 0.06,
    "format": 0.09,
    "urgency": 0.06,
    "feedback": 0.05,
}
SEMANTIC_CONFIG = {
    "floor": 0.81,
    "margin": 0.008,
    "lexical_evidence": 0.18,
    "offset": 0.65,
    "span": 0.35,
    "weight": 0.4,
}
TOPICS = {
    "Маркетинг": ("клиент", "продвиж", "маркет", "реклам", "кофейн", "посетител", "соцсет", "привлеч"),
    "Финансы": (
        "прибыл",
        "финанс",
        "кассов",
        "бюджет",
        "денег",
        "денеж",
        "расход",
        "выручк",
        "цену",
        "ценообраз",
    ),
    "Налоги": ("налог", "усн", "ндс", "бухгалт", "отчет", "отчёт"),
    "Команда": ("сотрудник", "команд", "найм", "нанят", "персонал", "делегир", "работник"),
    "Запуск бизнеса": ("откры", "начат", "запуск", "зарегистр", "бизнес-план", "с нуля", "идея"),
    "Продажи": ("продаж", "продав", "конверс", "сделк", "воронк", "возражен"),
    "Право": ("договор", "юрист", "право", "контрагент", "соглашен"),
    "Маркетплейсы": ("маркетплейс", "wildberries", "ozon", "вайлдбер"),
}
FORMAT_NAMES = {
    "article": "статья",
    "course": "курс",
    "document": "шаблон",
    "webinar": "вебинар",
    "podcast": "подкаст",
    "glossary": "термин",
    "calculator": "калькулятор",
}
STOP_WORDS = {
    "бизнес",
    "бизнесом",
    "помогите",
    "помоги",
    "хочу",
    "нужно",
    "мне",
    "как",
    "что",
    "это",
    "для",
    "все",
    "всё",
    "сделать",
}


def topics_for(text: str) -> list[str]:
    lowered = text.casefold().replace("ё", "е")
    return [topic for topic, stems in TOPICS.items() if any(s.replace("ё", "е") in lowered for s in stems)]


class Engine:
    def __init__(self, materials: list[Material], mode="demo", version="test", semantic=None):
        self.materials, self.mode, self.version = materials, mode, version
        self.by_id = {m.id: m for m in materials}
        self.documents = [" ".join([m.title, m.title, m.description, *m.topics, *m.tags]) for m in materials]
        self.word = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self.word_matrix = self.char_matrix = None
        if materials:
            self.word_matrix = self.word.fit_transform(self.documents)
            self.char_matrix = self.char.fit_transform(self.documents)
        self.semantic = semantic
        self.algorithm_id = "e5-hybrid-personal-v1" if semantic else "lexical-personal-v1"
        self.semantic_matrix = semantic.encode(self.documents) if semantic and materials else None

    def recommend(
        self,
        query: str,
        profile: Profile | None = None,
        feedback: dict[str, str] | None = None,
        limit=5,
        baseline=False,
    ) -> Route:
        start = time.perf_counter()
        query = query.strip()
        profile = profile or Profile()
        feedback = feedback or {}
        inferred_topics = topics_for(query)
        meaningful = [
            t for t in re.findall(r"[а-яa-z0-9]+", query.casefold()) if t not in STOP_WORDS and len(t) > 2
        ]
        vague = not query or (not inferred_topics and len(meaningful) < 2)
        active = [k for k, v in profile.model_dump().items() if v is not None]
        route_args = dict(
            route_id=str(uuid4()),
            algorithm="topic-baseline-v1" if baseline else self.algorithm_id,
            query=query,
            profile=profile,
            catalog_mode=self.mode,
            catalog_version=self.version,
            active_profile_fields=[],
        )
        if not self.materials:
            return Route(
                **route_args,
                items=[],
                clarification="Каталог пока пуст. Подключите материалы.",
                elapsed_ms=0,
                excluded_count=0,
                candidate_count=0,
            )
        if vague:
            return Route(
                **route_args,
                items=[],
                clarification="Какую задачу решаем: привлечь клиентов, разобраться с финансами или запустить бизнес?",
                elapsed_ms=round((time.perf_counter() - start) * 1000, 2),
                excluded_count=0,
                candidate_count=0,
            )
        word_scores = (self.word_matrix @ self.word.transform([query]).T).toarray().ravel()
        char_scores = (self.char_matrix @ self.char.transform([query]).T).toarray().ravel()
        lexical = 0.45 * word_scores + 0.55 * char_scores
        semantic_scores = None
        if self.semantic and not baseline:
            semantic_scores = (self.semantic_matrix @ self.semantic.encode([query], query=True).T).ravel()
        if (
            not inferred_topics
            and float(word_scores.max()) < 0.10
            and float(char_scores.max()) < 0.18
            and (semantic_scores is None or float(semantic_scores.max()) < SEMANTIC_CONFIG["floor"])
        ):
            return Route(
                **route_args,
                items=[],
                clarification="В каталоге нет уверенного совпадения. Опишите бизнес-задачу другими словами.",
                elapsed_ms=round((time.perf_counter() - start) * 1000, 2),
                excluded_count=0,
                candidate_count=0,
            )
        # Only query-derived topics affect baseline. No personal or format features.
        relevance = []
        lexical_evidence = []
        for i, material in enumerate(self.materials):
            matching_topics = set(inferred_topics) & set(material.topics)
            lexical_relevance = min(1.0, float(lexical[i]) + (0.20 if matching_topics else 0))
            lexical_evidence.append(lexical_relevance)
            semantic_relevance = (
                max(0.0, (float(semantic_scores[i]) - SEMANTIC_CONFIG["offset"]) / SEMANTIC_CONFIG["span"])
                if semantic_scores is not None
                else 0
            )
            relevance.append(
                min(
                    1.0,
                    (1 - SEMANTIC_CONFIG["weight"]) * lexical_relevance
                    + SEMANTIC_CONFIG["weight"] * semantic_relevance,
                )
                if semantic_scores is not None
                else lexical_relevance
            )
        candidates = []
        excluded = 0
        for i, material in enumerate(self.materials):
            if (
                semantic_scores is not None
                and lexical_evidence[i] < SEMANTIC_CONFIG["lexical_evidence"]
                and float(semantic_scores[i])
                < max(SEMANTIC_CONFIG["floor"], float(semantic_scores.max()) - SEMANTIC_CONFIG["margin"])
            ):
                continue
            if not baseline and feedback.get(material.id) in {"completed", "known", "not_relevant"}:
                excluded += 1
                continue
            # Profile boosts cannot rescue an unrelated candidate.
            if relevance[i] < 0.075:
                continue
            signals = {"relevance": round(relevance[i], 6)}
            if semantic_scores is not None:
                signals["semantic_similarity"] = round(float(semantic_scores[i]), 6)
            reasons = []
            matched_topics = set(inferred_topics) & set(material.topics)
            if matched_topics:
                reasons.append("По задаче: " + ", ".join(sorted(matched_topics)).lower())
            else:
                reasons.append(
                    "Близость задачи и описания рассчитана локальной моделью E5"
                    if semantic_scores is not None and lexical[i] < 0.075
                    else "В названии или описании есть слова и выражения из вашего запроса"
                )
            if not baseline:
                checks = {
                    "industry": None
                    if not profile.industry or not material.industries
                    else float(profile.industry in material.industries),
                    "stage": None
                    if not profile.stage or not material.stage
                    else float(profile.stage in material.stage),
                    "experience": None
                    if not profile.experience or material.difficulty is None
                    else float(profile.experience == material.difficulty),
                    "format": None if not profile.format else float(profile.format == material.source_type),
                    "urgency": None
                    if not profile.urgency
                    else float(
                        material.source_type
                        in (
                            {"article", "document", "calculator"}
                            if profile.urgency == "quick"
                            else {"course", "webinar"}
                        )
                    ),
                }
                labels = {
                    "industry": f"Есть отраслевая метка «{profile.industry}»",
                    "stage": "Подходит для выбранного этапа бизнеса",
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
                # Aggregate only explicit positive signals; do not infer absent history.
                liked = [
                    self.by_id[mid]
                    for mid, signal in feedback.items()
                    if signal == "helpful" and mid in self.by_id
                ]
                if liked:
                    signals["feedback"] = float(any(set(m.topics) & set(material.topics) for m in liked))
                    if signals["feedback"]:
                        reasons.append("Тема связана с материалами, которые вы отметили полезными")
                denom = sum(WEIGHTS[k] for k in signals if k in WEIGHTS)
                score = sum(WEIGHTS[k] * v for k, v in signals.items() if k in WEIGHTS) / denom
            else:
                score = relevance[i]
            candidates.append({"material": material, "signals": signals, "reasons": reasons, "score": score})
        selected = []
        while candidates and len(selected) < limit:

            def key(c):
                diversity = 0.0
                if selected and not baseline:
                    diversity = 0.035 * sum(
                        s["material"].source_type == c["material"].source_type for s in selected
                    )
                return (c["score"] - diversity, c["signals"]["relevance"], c["material"].id)

            chosen = max(candidates, key=key)
            chosen["rank_score"] = key(chosen)[0]
            chosen["diversity_penalty"] = chosen["score"] - chosen["rank_score"]
            candidates.remove(chosen)
            selected.append(chosen)
        items = []
        for chosen in selected:
            material = chosen["material"]
            action = {
                "document": "Заполните шаблон на примере одной реальной задачи вашего бизнеса.",
                "calculator": "Подставьте свои данные и проверьте, как меняется результат.",
                "course": "Посмотрите программу и сопоставьте её с пробелами в своих знаниях.",
                "glossary": "Проверьте, как этот термин применяется в вашей задаче.",
                "podcast": "Запишите одну идею, которую можно проверить на практике.",
                "webinar": "Составьте список вопросов по своей бизнес-задаче.",
            }.get(
                material.source_type, "Выберите одно действие из материала и проверьте его на своём бизнесе."
            )
            phase = (
                "Применить"
                if material.source_type in {"document", "calculator"}
                else "Углубиться"
                if material.source_type in {"course", "webinar"}
                else "Разобраться"
            )
            items.append(
                Recommendation(
                    material=material,
                    reasons=chosen["reasons"],
                    next_action=action,
                    phase=phase,
                    score=round(chosen["score"], 6),
                    rank_score=round(chosen["rank_score"], 6),
                    signals={**chosen["signals"], "diversity_penalty": round(chosen["diversity_penalty"], 6)},
                )
            )
        notice = None
        clarification = None
        if not baseline:
            route_args["active_profile_fields"] = [
                k for k in active if any(k in item.signals for item in items)
            ]
        if not items:
            clarification = (
                "Точного материала не нашли. Уточните задачу или выберите более общее направление."
            )
        elif max(i.signals["relevance"] for i in items) < 0.20:
            notice = "Совпадение слабое: это ближайшие материалы, а не точный ответ. Уточните задачу для более полезной подборки."
        return Route(
            **route_args,
            items=items,
            notice=notice,
            clarification=clarification,
            elapsed_ms=round((time.perf_counter() - start) * 1000, 2),
            excluded_count=excluded,
            candidate_count=len(candidates) + len(selected),
        )
