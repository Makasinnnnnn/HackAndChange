"""Query intent and source taxonomy; no retrieval, scores, database or LLM calls."""

from __future__ import annotations

import re
from dataclasses import dataclass

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
    "Франчайзинг": ("франшиз", "франчайз"),
    "Команда": (
        "сотрудник",
        "команд",
        "найм",
        "нанят",
        "персонал",
        "делегир",
        "работник",
        "подчиненн",
        "передать ответственность",
    ),
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
    topics = [topic for topic, stems in TOPICS.items() if any(s.replace("ё", "е") in lowered for s in stems)]
    if lowered.strip() in {"ип", "ооо"} and "Запуск бизнеса" not in topics:
        topics.append("Запуск бизнеса")
    return topics


TOPIC_ALIASES = {
    "Управление командой": "Команда",
    "Лидерство": "Команда",
    "Законы": "Право",
    "Первые шаги": "Запуск бизнеса",
    "Регистрация бизнеса": "Запуск бизнеса",
    "Финансы и учет": "Финансы",
    "Финансы и учёт": "Финансы",
    "Маркeтплейсы": "Маркетплейсы",
}


def material_topics(material):
    return {TOPIC_ALIASES.get(topic, topic) for topic in material.topics}


def industry_key(value):
    return (
        value.casefold().replace("ё", "е").translate(str.maketrans({"c": "с", "a": "а", "e": "е", "o": "о"}))
    )


SECTOR_TERMS = {
    "medical": ("лаборатор", "медицин", "клиник", "инвитро"),
    "beauty": ("маникюр", "бьюти", "салон красоты", "парикмахер", "барбершоп"),
    "food": ("кофейн", "кафе", "ресторан", "пекарн"),
    "construction": ("строитель", "ремонт квартир", "недвижим"),
    "marketplace": ("маркетплейс", "wildberries", "ozon"),
    "retail": ("магазин", "одежд", "розниц", "ретейл", "ритейл", "бутик"),
    "production": ("производств", "фабрик", "завод"),
    "logistics": ("логист", "грузоперевоз", "транспортная компания"),
}


def sectors_for(value):
    text = value.casefold()
    return {sector for sector, terms in SECTOR_TERMS.items() if any(term in text for term in terms)}


SECTOR_INDUSTRIES = {
    "medical": {"Услуги"},
    "beauty": {"Услуги"},
    "food": {"HoReCa"},
    "construction": {"Строительство и недвижимость"},
    "marketplace": {"Marketplace", "ECom", "Розница"},
    "retail": {"Розница", "Оптовая торговля"},
    "production": {"Производство"},
    "logistics": {"Транспорт и логистика"},
}
BROAD_CHANNELS = {"B2B", "B2G", "ECom"}


def sector_compatibility(material, requested):
    """Explicit title/metadata conflicts are exclusions, not weak negative boosts."""
    if not requested:
        return True
    title_sectors = sectors_for(material.title)
    if title_sectors:
        return bool(requested & title_sectors)
    allowed = {industry_key(label) for sector in requested for label in SECTOR_INDUSTRIES.get(sector, set())}
    specific = {industry_key(label) for label in material.industries if label not in BROAD_CHANNELS}
    if specific and not allowed.intersection(specific):
        return False
    # A named business-plan/opening subject is specialized even without industry tags.
    subject = re.search(r"(?:бизнес[ -]план|открыть|открытие|запуск)\s+([а-яё-]+)", material.title.casefold())
    generic = {
        "бизнес",
        "бизнеса",
        "предприятия",
        "компании",
        "проекта",
        "с",
        "для",
        "по",
        "своего",
        "нового",
        "собственного",
        "ип",
        "ооо",
    }
    if subject and subject.group(1) not in generic:
        return False
    return True


def retrieval_query(query):
    lowered = query.casefold().replace("ё", "е")
    additions = []
    if any(stem in lowered for stem in ("подчиненн", "передать ответственность", "делегир")):
        additions.append("делегирование полномочия распределение задач управление командой")
    if "франшиз" in lowered or "франчайз" in lowered:
        additions.append("франчайзинг выбор покупка франшизы")
    if any(stem in lowered for stem in ("открыт", "запуст", "с нуля")):
        additions.append("запуск бизнеса бизнес-план стартовые расходы")
    if lowered.strip() in {"ип", "ооо"}:
        additions.append(
            "регистрация бизнеса индивидуальный предприниматель общество с ограниченной ответственностью"
        )
    if lowered.strip() in {"налог", "налоги", "налогообложение"}:
        additions.append("налогообложение налоговый учет")
    if lowered.strip() in {"кофе", "кафе", "кофейня"}:
        additions.append("кофейня кафе открытие управление")
    return query + (" " + " ".join(additions) if additions else "")


@dataclass(frozen=True)
class QueryIntent:
    query: str
    search: str
    topics: frozenset[str]
    sectors: frozenset[str]
    vague: bool
    opening: bool
    closing: bool


def parse_intent(query: str, baseline=False) -> QueryIntent:
    query = query.strip()
    topics = frozenset(topics_for(query))
    meaningful = [
        word
        for word in re.findall(r"[а-яёa-z0-9]+", query.casefold())
        if word not in STOP_WORDS and (len(word) > 2 or word in {"ип", "ооо"})
    ]
    return QueryIntent(
        query,
        query if baseline else retrieval_query(query),
        topics,
        frozenset(sectors_for(query)),
        not query or (not topics and not meaningful),
        "Запуск бизнеса" in topics,
        any(term in query.casefold() for term in ("закры", "ликвид", "прекрат")),
    )


def sector_match(material, requested) -> bool:
    if requested & sectors_for(material.title):
        return True
    narrow = {
        industry_key(label)
        for sector in requested
        for label in SECTOR_INDUSTRIES.get(sector, set())
        if label != "Услуги"
    }
    return bool(narrow & {industry_key(label) for label in material.industries})
