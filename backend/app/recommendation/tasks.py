"""Controlled task evidence from titles/descriptions, independent of catalog IDs.

These are transparent retrieval heuristics, not human relevance labels or an LLM.
"""

import re
from functools import lru_cache

# Each family describes a business operation rather than a broad catalog topic.
TASKS = {
    "referrals": (
        "рекомендации и сарафанное радио",
        r"сарафан|реферальн|клиент.{0,12}рекомендац|рекомендац.{0,12}клиент",
    ),
    "market_entry": (
        "выход на маркетплейс",
        r"выйти.{0,20}маркетплейс|выход.{0,20}маркетплейс|начать продавать.{0,20}(?:ozon|wildberries|маркетплейс)|маркетплейсы.{0,5}с чего начать|чек[ -]листы.{0,25}продаж.{0,25}маркетплейс|зайти на маркетплейс",
    ),
    "niche": ("выбор ниши", r"выб(?:ра|ира)\w* ниш"),
    "purchase_plan": ("план первой закупки", r"перв\w* закуп|план\w* закуп|рассчит.{0,15}закуп"),
    "financial_basics": (
        "прибыль и расходы",
        r"прибыл.{0,15}расход|основы финанс|порядок в финанс|финансов\w* модел",
    ),
    "promotion": ("продвижение бизнеса", r"продвижени|продвигать"),
    "competitors": ("анализ конкурентов", r"анализ.{0,15}конкурент|анализирова\w* конкурент"),
    "logistics_optimization": (
        "организация логистики",
        r"улучшить логист|оптимизац\w* логист|организац\w* логист|управлени\w* логист",
    ),
    "commissions": ("комиссии площадок", r"комисси"),
    "demand": (
        "проверка спроса и бизнес-идеи",
        r"\bспрос(?:а|у|ом|е)?\b|customer development|custdev|кастдев|\bmvp\b|провери\w* бизнес[ -]?иде|интервью.*(?:покупател|клиент|потребител)",
    ),
    "business_plan": (
        "бизнес-план и бюджет запуска",
        r"бизнес[ -]?план|финансов\w* модел|финмодел|стартов\w* (?:расход|капитал|затрат)|бюджет\w* запуск",
    ),
    "registration": (
        "регистрация бизнеса",
        r"регистрац.{0,20}(?:бизнес|ип\b|ооо\b)|(?:ип|ооо)\s+регистраци|зарегистр.{0,15}(?:ип\b|ооо\b)|откры\w* (?:ип\b|ооо\b)|как самозанятому стать ип|форма регистрации ооо",
    ),
    "launch": (
        "запуск собственного бизнеса",
        r"(?:откры|запус|нача)\w*.{0,20}(?:бизнес|собственное дело)|первые шаги в бизнес|бизнес[ -]план|бизнес с нуля",
    ),
    "franchise": ("выбор и проверка франшизы", r"франшиз|франчайз|коммерческ\w* концесси"),
    "cash_flow": (
        "денежный поток и кассовый разрыв",
        r"кассов\w* разрыв|cash.?flow|движени\w* денежн|прибыл\w* есть.{0,8}а денег нет|выручк.{0,35}денег.{0,20}счет|прибыл.{0,25}выручк.{0,20}денег",
    ),
    "breakeven": ("точка безубыточности", r"безубыточ"),
    "costing": (
        "себестоимость и цена",
        r"себестоим|ценообразован|наценк|(?:повыс|повыш|установ|поднят)\w* цен",
    ),
    "cost_calculation": (
        "расчёт расходов",
        r"\b(?:рассчит|посчит|расчет)\w*.{0,30}\b(?:затрат|расход|стоимост)",
    ),
    "demand_forecast": ("прогнозирование спроса", r"прогноз.{0,20}спрос"),
    "sales_growth": ("рост продаж", r"(?:увелич|повыс|рост)\w*.{0,15}продаж"),
    "cost_reduction": (
        "снижение расходов",
        r"(?:сократ|снизи|снижен|оптимизац)\w* (?:.{0,25})?(?:расход|затрат|издерж)|ниже затрат",
    ),
    "profitability": ("маржа и рентабельность", r"маржин|рентабельност|фудкост|экономик\w* ресторан"),
    "receivables": ("дебиторская задолженность", r"дебитор|платят с задержк|отсрочк\w* платеж"),
    "management_accounts": ("управленческий учёт", r"управленческ\w* учет"),
    "tax_regime": (
        "выбор налогового режима",
        r"систем\w* налогооблож|налогов\w* режим|(?:выбор|выбрать|совмещ|отлич|перейти|переход).{0,40}(?:усн|патент|нпд|осно|аусн)|переходим с усн",
    ),
    "tax_payment": (
        "уплата налогов и взносов",
        r"страхов\w* взнос|фиксирован\w* взнос|плат\w* налог|налог\w* и взнос|единый налоговый счет|\bенс\b",
    ),
    "tax_reporting": (
        "налоговая отчётность",
        r"отчетност|налогов\w* отчет|какие отчеты|сдавать.{0,25}отчет|срок.{0,20}отчет",
    ),
    "tax_overdue": (
        "просроченная отчётность",
        r"пропустил.{0,20}срок|просроч.{0,25}отчет|не сдал.{0,20}отчет|опоздал.{0,20}отчет",
    ),
    "vat": ("НДС", r"\bндс\b"),
    "self_employed": ("расчёты самозанятого", r"самозанят|\bнпд\b"),
    "payments": (
        "приём оплаты и чеки",
        r"принима\w* оплат|прием оплат|выдава\w* чек|выставить счет|оплату и.{0,10}чек|кассов\w* чек",
    ),
    "tax_debt": ("налоговая задолженность", r"налогов\w* задолж|задолженност.{0,15}налог"),
    "recruitment": (
        "поиск и найм сотрудников",
        r"найм|наня|подбор.{0,20}(?:сотруд|персонал|команд)|перв\w* сотруд|собеседован|кандидат",
    ),
    "delegation": ("делегирование", r"делегир|передать ответственность|все делаю сам|полномочи"),
    "attrition": (
        "удержание сотрудников",
        r"почему сотрудник.{0,20}увольня|сотрудник.{0,20}увольняются|текучест|удерж.{0,15}(?:команд|сотруд|персонал)",
    ),
    "task_management": (
        "постановка задач команде",
        r"(?:постав|постанов|ставить).{0,25}задач|(?:управл|руковод).{0,20}команд",
    ),
    "motivation": ("мотивация команды", r"мотив|нематериальн|продуктивн.{0,15}работ"),
    "onboarding": ("адаптация сотрудника", r"адаптац|адаптиров"),
    "conflict": ("конфликты в команде", r"конфликт"),
    "feedback": ("обратная связь сотрудникам", r"обратн\w* связь|оценочн\w* встреч"),
    "burnout": ("выгорание", r"выгоран|выгорел"),
    "audience": ("целевая аудитория", r"целев\w* аудитори|портрет клиент|сегментац"),
    "ad_metrics": (
        "эффективность рекламы",
        r"эффективност\w* реклам|стоимост\w* привлечени|\bcac\b|\bromi\b|\broas\b",
    ),
    "organic": (
        "продвижение без платной рекламы",
        r"без платн\w* реклам|без рекламн\w* бюджет|без\s+(?:платной\s+)?рекламы|сарафан|рекомендаци.{0,15}клиент|реферальн|бесплатн\w* продвиж|контент[ -]маркетинг",
    ),
    "seasonal": ("сезонная рекламная кампания", r"новогодн|новому году|праздни|черн\w* пятниц"),
    "channels": (
        "каналы продвижения",
        r"канал\w* продвиж|стратеги\w* продвиж|где брать клиент|выбрать канал",
    ),
    "acquisition": (
        "привлечение клиентов",
        r"привле.{0,25}(?:клиент|посетител|покупател)|клиентов мало|мало клиент|первых клиент|поиск\w* клиент|поток\w* клиент|находить заказчик|канал\w* привлечени|локальн\w* продвиж|бизнеса на картах",
    ),
    "retention": (
        "повторные продажи и удержание",
        r"повторн\w* (?:продаж|покуп)|удерж\w* клиент|верну\w* клиент|клиент.{0,35}не возвращ|постоянн\w* (?:клиент|покуп)|программ\w* лояльност",
    ),
    "conversion": ("конверсия", r"конверси|посетител.{0,25}покупок мало|посетител.{0,25}не покуп"),
    "average_check": ("средний чек", r"средн\w* чек|допродаж|кросс[ -]?продаж"),
    "funnel": ("воронка продаж", r"воронк"),
    "objections": (
        "возражения покупателей",
        r"возражени.{0,20}(?:клиент|покупател)|работать с возражени|слишком дорого",
    ),
    "crm": ("CRM", r"\bcrm\b|\bсрм\b"),
    "service": (
        "клиентский сервис",
        r"обслуживани\w* клиент|клиентск\w* сервис|работ.{0,15}жалоб|отвечать на жалоб",
    ),
    "supply_contract": ("договор поставки", r"договор.{0,12}постав|поставщик|работы с поставщиками"),
    "claim": ("претензионная работа", r"претензи|претензия"),
    "employment": (
        "оформление сотрудника",
        r"оформ.{0,25}сотруд|трудов\w* (?:договор|кодекс|отношени)|прием\w* на работ|трудоустрой",
    ),
    "counterparty": ("проверка контрагента", r"провери\w* контрагент|риск\w* работ\w* с контрагент"),
    "trademark": ("товарный знак", r"товарн\w* знак|торгов\w* марк|защит.{0,20}названи"),
    "personal_data": ("персональные данные", r"персональн\w* данн"),
    "closing": (
        "закрытие бизнеса",
        r"закры\w* (?:ип|ооо|магазин|бизнес|компани)|ликвидац|прекращени\w* деятельност",
    ),
    "lease": ("аренда помещения", r"аренд\w* (?:коммерческ\w* |нежил\w* )?помещени|договор.{0,10}аренд"),
    "returns": ("возвраты товаров", r"возврат\w* (?:денег|товар)|возвратов|вернуть товар"),
    "founders": ("учредители и доли", r"учредител|дол[июя]\b|распределени\w* дол"),
    "product_selection": ("выбор товара", r"выбра\w* товар|выбор\w* товар|товар.{0,15}для старт"),
    "fulfilment": (
        "схемы хранения и доставки",
        r"схем\w* (?:хранени|работы с маркетплейс)|\bfbo\b|\bfbs\b|склад.{0,20}маркетплейс",
    ),
    "procurement": (
        "закупки и поставщики",
        r"управлени\w* закупк|организова\w* закупк|снабжени|выбор\w* поставщик",
    ),
    "contract": ("договор и шаблон", r"договор"),
}


def text_key(text):
    return text.casefold().replace("ё", "е")


@lru_cache(maxsize=16384)
def task_matches(text):
    text = text_key(text)
    return frozenset(key for key, (_, pattern) in TASKS.items() if re.search(pattern, text))


def query_tasks(text):
    found = set(task_matches(text))
    # Specific operations override ambiguous words from their context.
    if found - {"contract"}:
        found.discard("contract")
    if found - {"launch"}:
        found.discard("launch")
    if found - {"sales_growth"}:
        found.discard("sales_growth")
    if found - {"promotion"}:
        found.discard("promotion")
    if "referrals" in found:
        found -= {"organic", "acquisition"}
    if "payments" in found:
        found.discard("self_employed")
    if "demand_forecast" in found:
        found.discard("demand")
    if "trademark" in found:
        found.discard("registration")
    if found & {"claim", "counterparty"}:
        found.discard("supply_contract")
    if "tax_debt" in found:
        found.discard("receivables")
    if "tax_overdue" in found:
        found.discard("tax_reporting")
    if "delegation" in found:
        found.discard("recruitment")
    if "closing" in found:
        found.discard("registration")
    if found & {"conversion", "retention", "audience", "ad_metrics", "seasonal", "organic", "channels"}:
        found.discard("acquisition")
    return frozenset(found)


def task_shortlist(candidates, relative_floor):
    """Keep strong evidence per requested operation, not only the dominant clause."""
    peaks = {}
    for candidate in candidates:
        for key in candidate.signals:
            if key.startswith("task_"):
                peaks[key] = max(peaks.get(key, 0), candidate.score)
    return [
        candidate
        for candidate in candidates
        if any(
            key.startswith("task_") and candidate.score >= peaks[key] * relative_floor
            for key in candidate.signals
        )
    ]


def material_tasks(material):
    text = text_key(material.title + " " + material.description)
    found = set(task_matches(text))
    if not re.search(r"сотруд|команд|персонал|руковод|труд", text):
        found -= {"motivation", "feedback", "conflict", "onboarding"}
    title = text_key(material.title)
    if not re.search(r"сотруд|команд|персонал", text) or re.search(r"суд|доверенност|контрагент", title):
        found.discard("conflict")
    if re.search(r"клиент|продукт|услуг|покупател|отзыв", title) and not re.search(
        r"сотруд|команд|персонал", title
    ):
        found -= {"feedback", "motivation", "onboarding"}
    if re.search(r"(?:в системе|профил|меркурий|на авито|товарн\w* знак)", title):
        found.discard("registration")
    if re.search(r"госзакуп|государственн\w* закуп|участ.{0,20}закуп", text):
        found.discard("procurement")
    return frozenset(found)


def task_evidence(material, requested):
    return requested & material_tasks(material)
