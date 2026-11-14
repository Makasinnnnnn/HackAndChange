"""Query intent and source taxonomy; no retrieval, scores, database or LLM calls."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .tasks import query_tasks, text_key

TOPICS = {
    "Маркетинг": ("клиент", "продвиж", "маркет", "реклам", "кофейн", "посетител", "соцсет", "привлеч"),
    "Финансы": (
        "прибыл",
        "рентабельност",
        "финанс",
        "кассов",
        "бюджет",
        "денег",
        "денеж",
        "расход",
        "выручк",
        "доход",
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
    "какая",
    "какой",
    "какие",
    "какую",
    "почему",
    "зачем",
    "когда",
    "где",
    "ли",
    "или",
    "нужен",
    "нужна",
    "решить",
    "делать",
    "узнать",
    "понять",
    "можно",
    "свой",
    "своего",
    "своем",
    "своём",
    "такое",
    "кто",
    "такой",
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
    "logistics": ("логист", "перевозк", "перевозить", "перевозу", "грузоперевоз", "транспортная компания"),
    "foreign_trade": ("импорт", "таможенн", "экспорт"),
    "vending": ("вендинг", "торговых автомат"),
    "social": ("социального бизнеса", "социальное предприниматель"),
}


def sectors_for(value):
    text = value.casefold()
    if text.strip() == "кофе":
        return {"food"}
    found = {sector for sector, terms in SECTOR_TERMS.items() if any(term in text for term in terms)}
    if re.search(r"салон\w*\s+красот", text):
        found.add("beauty")
    return found


SECTOR_INDUSTRIES = {
    "medical": {"Услуги"},
    "beauty": {"Услуги"},
    "food": {"HoReCa"},
    "construction": {"Строительство и недвижимость"},
    "marketplace": {"Marketplace", "ECom", "Розница"},
    "retail": {"Розница", "Оптовая торговля"},
    "production": {"Производство"},
    "logistics": {"Транспорт и логистика"},
    "foreign_trade": {"ВЭД"},
    "vending": {"Розница"},
    "social": {"Услуги"},
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


AD_SPEND_CONSTRAINT = re.compile(
    r"без\s+(?:увеличения|роста|повышения|дополнительных)\s+(?:рекламн\w*\s+бюджет\w*|(?:расход\w*|затрат\w*|бюджет\w*)\s+на\s+реклам\w*)"
    r"|не\s+увеличивая\s+(?:рекламн\w*\s+бюджет\w*|(?:расход\w*|затрат\w*)\s+на\s+реклам\w*)"
    r"|с\s+(?:тем\s+же|прежним)\s+рекламн\w*\s+бюджет\w*"
)

# Evidence comes from the title/description, never a broad catalog topic alone.
PROFIT_MECHANISMS = {
    "retention": ("повторн", "удержани", "лояльност"),
    "conversion": ("конверси", "воронк", "средний чек", "среднего чека", "допродаж"),
    "margin": ("маржин", "рентабельност", "ценообразован", "наценк"),
    "costs": ("сократ", "снизи", "оптимизац", "себестоим", "издержк"),
    "ad_efficiency": (
        "roas",
        "romi",
        "стоимость привлечения",
        "стоимости привлечения",
        "эффективность рекламы",
        "эффективности рекламы",
    ),
    "organic": ("без рекламного бюджета", "бесплатное продвиж", "органическое продвиж", "сарафан"),
}


def profit_mechanisms(material):
    text = (material.title + " " + material.description).casefold().replace("ё", "е")
    matched = {key for key, terms in PROFIT_MECHANISMS.items() if any(term in text for term in terms)}
    # Cutting/optimizing something unrelated (e.g. hiring time) is not cost evidence.
    if "costs" in matched and not any(term in text for term in ("расход", "затрат", "себестоим", "издержк")):
        matched.remove("costs")
    return matched


@dataclass(frozen=True)
class QueryIntent:
    query: str
    search: str
    topics: frozenset[str]
    sectors: frozenset[str]
    vague: bool
    opening: bool
    closing: bool
    constraints: frozenset[str] = frozenset()
    tasks: frozenset[str] = frozenset()
    requested_format: str | None = None
    excluded_formats: frozenset[str] = frozenset()
    entity: str | None = None
    definition: bool = False
    clarification: str | None = None
    platforms: frozenset[str] = frozenset()
    comparison_terms: tuple[str, ...] = ()


PLATFORMS = {
    "ozon": r"\bozon\b",
    "wildberries": r"\bwildberries\b|\bwb\b|вайлдбер",
    "yandex": r"яндекс",
    "avito": r"авито",
}
TAX_SUBJECTS = {
    "usn": r"\bусн\b",
    "patent": r"патент",
    "npd": r"самозанят|\bнпд\b",
    "ip": r"\bип\b",
    "ooo": r"\bооо\b",
}


def platforms_for(text):
    return frozenset(key for key, pattern in PLATFORMS.items() if re.search(pattern, text_key(text)))


def informative_words(text):
    return {
        word
        for word in re.findall(r"[а-яa-z0-9]+", text_key(text))
        if word not in STOP_WORDS and len(word) > 2
    }


def positive_request(query):
    """Strip explicitly rejected alternatives, while retaining original text in Route."""
    text = text_key(query)
    corrections = {
        "аткрыть": "открыть",
        "кафейню": "кофейню",
        "кафейня": "кофейня",
        "скока": "сколько",
        "панять": "понять",
        "бизнасе": "бизнесе",
        "прибыл": "прибыль",
    }
    text = re.sub(r"[а-я]+", lambda match: corrections.get(match.group(), match.group()), text)
    constraints = set()
    if re.search(r"(?:не хочу|не планирую|без)\s+(?:(?:покупать|покупки|выбора)\s+)?франшиз", text):
        constraints.add("no_franchise")
        text = re.sub(
            r"(?:не хочу|не планирую|без)\s+(?:(?:покупать|покупки|выбора)\s+)?франшиз\w*", "", text
        )
    if re.search(r"без\s+(?:сотрудник|работник|персонал)", text):
        constraints.add("no_employees")
        text = re.sub(r"без\s+(?:сотрудник|работник|персонал)\w*", "", text)
    if re.search(r"без\s+скид", text):
        constraints.add("no_discounts")
    if re.search(r"без\s+(?:найма|увеличения штата)", text):
        constraints.add("no_hiring")
        text = re.sub(r"без\s+(?:найма|увеличения штата)(?:\s+дополнительных)?(?:\s+сотрудников)?", "", text)
    if re.search(r"сохранить\s+(?:сотрудник|команд|персонал)", text):
        constraints.add("preserve_staff")
    if re.search(r"без\s+(?:увольнени|сокращени\w* штат)", text):
        constraints.add("preserve_staff")
    if re.search(r"перейти.{0,40}на усн", text):
        constraints.add("target_usn")
    # The alternative after 'а не' is not the requested task or format.
    excluded_formats = set()
    alternative = re.search(r"\bа не\b(.*)", text)
    if alternative:
        if "курс" in alternative.group(1):
            excluded_formats.add("course")
        text = text[: alternative.start()]
    # A validation-before-investment request must not become a lease-contract search.
    text = re.sub(r"\bдо\s+(?:аренды|покупки|найма)\b.*", "", text)
    return text.strip(), constraints, frozenset(excluded_formats)


def parse_intent(query: str, baseline=False) -> QueryIntent:
    query = query.strip()
    lowered = query.casefold().replace("ё", "е")
    constrained_profit = bool(AD_SPEND_CONSTRAINT.search(lowered)) and any(
        term in lowered for term in ("прибыл", "рентабельност", "доход", "продаж", "выручк")
    )
    positive_query, constraints, excluded_formats = positive_request(query)
    if constrained_profit:
        positive_query = AD_SPEND_CONSTRAINT.sub("", positive_query).strip(" .?!")
        if not baseline:
            positive_query += " повторные продажи удержание клиентов маржинальность конверсия снижение затрат"
        constraints.add("fixed_ad_spend")
    tasks = query_tasks(positive_query if not constrained_profit else AD_SPEND_CONSTRAINT.sub("", lowered))
    if "profitability" in tasks and re.search(
        r"(?:рассчит|посчит|расчет|формул)\w*.{0,20}(?:марж|рентабельност)", positive_query
    ):
        constraints.add("financial_calculation")
    if sectors_for(positive_query) and not tasks and re.search(r"\bзакрыть\b", positive_query):
        tasks = tasks | {"closing"}
    # A symptom of an operating business is not a request for start-up capital.
    # Only infer a diagnostic goal when no more specific action was requested.
    if not tasks and re.search(
        r"не\s+(?:принос\w*|дает|дает\w*)\s+(?:мне\s+)?(?:денег|доход\w*|прибыл\w*)"
        r"|не\s+зарабатыва\w*|не\s+окупа\w*|(?:работа\w*|работаем|работаю)\s+в\s+минус"
        r"|\bубыточ\w*|\bубытки\b|(?:нет|мало)\s+прибыл\w*|прибыл\w*\s+(?:нет|падает|снизилась)",
        positive_query,
    ):
        tasks = frozenset({"profitability"})
        constraints.add("profit_diagnosis")
        positive_query += " рентабельность маржинальность экономика действующего бизнеса"
    if "откры" in positive_query and sectors_for(positive_query) and "сколько денег" in positive_query:
        tasks = tasks | {"business_plan"}
    if re.search(
        r"(?:рассчитать|посчитать|нет).{0,20}прибыл|прибыл.{0,20}(?:комисси|возврат)", positive_query
    ) and sectors_for(positive_query) == {"marketplace"}:
        tasks = frozenset({"profitability"})
    if constrained_profit:
        tasks = frozenset()  # Alternative profit mechanisms, not a conjunction of expansion terms.
    if "no_hiring" in constraints and "прибыл" in positive_query:
        tasks = frozenset({"profitability"})
    if "marketplace" in sectors_for(positive_query) and re.search(
        r"прибыл.{0,12}нет|нет.{0,12}прибыл", positive_query
    ):
        tasks = frozenset({"profitability"})
    if positive_query.strip() in {"ип", "ооо"}:
        tasks = frozenset({"registration"})
    topics = frozenset(topics_for(positive_query))
    definition = (
        any(term in lowered for term in ("что такое", "определение", "термин"))
        or len(re.findall(r"[а-яa-z]+", lowered)) <= 2
    )
    requested_format = (
        "document"
        if any(term in positive_query for term in ("шаблон", "образец"))
        else "calculator"
        if "калькулятор" in positive_query
        else None
    )
    entity = (
        "ип"
        if re.search(r"\bип\b", positive_query) and not re.search(r"\bооо\b", positive_query)
        else "ооо"
        if re.search(r"\bооо\b", positive_query) and not re.search(r"\bип\b", positive_query)
        else None
    )
    earning_only = (
        bool(re.search(r"(?:заработать|зарабатывать).{0,15}(?:денег|деньги)", lowered))
        and not tasks
        and not sectors_for(query)
    )
    vague_wish = not tasks and bool(
        re.search(r"(?:все|всё)\s+(?:стало|было)\s+хорошо|помоги\s*$", positive_query)
    )
    meaningful = [
        word
        for word in re.findall(r"[а-яёa-z0-9]+", query.casefold())
        if word not in STOP_WORDS and (len(word) > 2 or word in {"ип", "ооо"})
    ]
    clarification = (
        "Какой договор нужен: поставки, услуг, аренды или трудовой?" if tasks == {"contract"} else None
    )
    if (
        not tasks
        and not constraints
        and not requested_format
        and "Запуск бизнеса" not in topics
        and (topics or sectors_for(positive_query))
        and not re.search(r"что такое|определение|термин", lowered)
    ):
        clarification = (
            "Пока определена только общая тема, а конкретная задача не ясна. "
            "Что нужно: привлечь клиентов, проверить рентабельность, "
            "спланировать платежи или управлять командой?"
        )
    return QueryIntent(
        query,
        positive_query if baseline else retrieval_query(positive_query),
        topics,
        frozenset(sectors_for(positive_query)),
        not query or (not topics and not meaningful) or earning_only or vague_wish,
        "Запуск бизнеса" in topics and "closing" not in tasks,
        "closing" in tasks,
        frozenset(constraints),
        tasks,
        requested_format,
        excluded_formats,
        entity,
        definition,
        clarification,
        platforms_for(positive_query),
        tuple(key for key, pattern in TAX_SUBJECTS.items() if re.search(pattern, positive_query))
        if re.search(r"отлич|сравн|совмещ", positive_query)
        else (),
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
