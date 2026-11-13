"""Output actions use material type; explanations originate in actual ranking evidence."""

from ..models import Recommendation
from .intent import profit_mechanisms
from .tasks import TASKS, task_matches


def task_reasons(material, matched):
    in_title = matched & task_matches(material.title)
    reasons = []
    if in_title:
        reasons.append("В названии: " + "; ".join(TASKS[key][0] for key in sorted(in_title)))
    if matched - in_title:
        reasons.append("В описании: " + "; ".join(TASKS[key][0] for key in sorted(matched - in_title)))
    return reasons


def constraint_evidence(material):
    labels = {
        "retention": "повторные продажи и удержание клиентов",
        "conversion": "конверсия или средний чек",
        "margin": "маржинальность и ценообразование",
        "costs": "расходы и себестоимость",
        "ad_efficiency": "эффективность рекламы и стоимость привлечения",
        "organic": "продвижение без рекламного бюджета",
    }
    mechanisms = profit_mechanisms(material)
    return (
        {"constraint_" + key: 1.0 for key in sorted(mechanisms)},
        [
            "В названии или описании: " + "; ".join(labels[key] for key in sorted(mechanisms)),
            "Учитываем ограничение: не увеличивать рекламный бюджет",
        ],
    )


def recommendation(chosen):
    material = chosen.material
    action = {
        "document": "Заполните шаблон на примере одной реальной задачи вашего бизнеса.",
        "calculator": "Подставьте свои данные и проверьте, как меняется результат.",
        "course": "Посмотрите программу и сопоставьте её с пробелами в своих знаниях.",
        "glossary": "Проверьте, как этот термин применяется в вашей задаче.",
        "podcast": "Запишите одну идею, которую можно проверить на практике.",
        "webinar": "Составьте список вопросов по своей бизнес-задаче.",
    }.get(material.source_type, "Выберите одно действие из материала и проверьте его на своём бизнесе.")
    task_actions = {
        "demand": "Запишите гипотезу спроса и три вопроса для интервью с потенциальными покупателями.",
        "business_plan": "Составьте черновик плана: спрос, запуск, основные расходы и источники выручки.",
        "registration": "Составьте список документов и шагов регистрации для выбранной формы бизнеса.",
        "launch": "Запишите бизнес-гипотезу, предполагаемых покупателей и первый проверочный шаг.",
        "franchise": "Составьте список вопросов франчайзеру и отдельно отметьте неподтверждённые обещания.",
        "cash_flow": "Сопоставьте даты поступлений и платежей на ближайший месяц и отметьте возможный дефицит денег.",
        "costing": "Выпишите составляющие себестоимости одного товара или услуги и сравните с ценой продажи.",
        "cost_reduction": "Выпишите статьи расходов и выберите одну для проверки экономии без потери качества.",
        "profitability": "Рассчитайте прибыль и маржу одного направления на собственных исходных данных.",
        "tax_regime": "Сравните подходящие налоговые режимы на своих исходных данных; условия проверьте по актуальному источнику.",
        "tax_reporting": "Составьте календарь применимой отчётности с учётом формы бизнеса и наличия сотрудников.",
        "tax_payment": "Составьте календарь своих налоговых платежей и взносов и проверьте применимость каждого пункта.",
        "recruitment": "Опишите задачи роли и критерии кандидата до публикации вакансии.",
        "delegation": "Выберите одну повторяющуюся задачу, определите результат, ответственного и точку проверки.",
        "attrition": "Соберите причины последних увольнений и проверьте одну гипотезу об удержании сотрудников.",
        "task_management": "Перепишите одну задачу команде: результат, срок, ответственный и критерий готовности.",
        "motivation": "Обсудите с командой препятствия в работе и выберите одно улучшение в пределах текущего бюджета.",
        "onboarding": "Составьте план первой недели сотрудника с задачами и ответственным за помощь.",
        "audience": "Опишите один сегмент покупателей, его задачу и критерий выбора вашего продукта.",
        "ad_metrics": "Сравните расходы, обращения и покупки по одному рекламному каналу.",
        "organic": "Выберите один способ продвижения и оцените затраты времени и доступные ресурсы.",
        "retention": "Посчитайте повторные покупки и выберите одну гипотезу возвращения клиентов.",
        "conversion": "Измерьте путь от посещения до покупки и найдите этап с наибольшими потерями.",
        "funnel": "Нарисуйте этапы своей воронки и укажите число клиентов на каждом переходе.",
        "objections": "Запишите частое возражение и подготовьте ответ через потребность и ценность для клиента.",
        "crm": "Опишите процесс продаж и составьте список требований к CRM перед выбором сервиса.",
        "personal_data": "Составьте перечень собираемых данных и проверьте применимость предложенных документов.",
        "counterparty": "Составьте список проверок контрагента и отметьте сведения, которые ещё нужно подтвердить.",
        "closing": "Составьте план прекращения деятельности с учётом формы бизнеса, долгов и обязательств.",
        "procurement": "Опишите потребность в закупке, критерии поставщика и допустимый запас.",
    }
    if material.source_type != "glossary":
        matched = {key.removeprefix("task_") for key in chosen.signals if key.startswith("task_")}
        priority = sorted(matched, key=lambda key: (key not in task_matches(material.title), key))
        for key in priority:
            if key in task_actions:
                action = task_actions[key]
                break
    constraint_actions = {
        "retention": "Посчитайте долю повторных покупок и выберите способ вернуть действующих клиентов в пределах текущего бюджета.",
        "conversion": "Измерьте конверсию и средний чек; выберите один показатель для проверки без увеличения рекламного бюджета.",
        "margin": "Рассчитайте маржу одного товара или услуги и проверьте влияние цены и себестоимости на прибыль.",
        "costs": "Выпишите основные расходы и оцените, какую статью можно сократить без потери качества.",
        "ad_efficiency": "Сравните стоимость привлечения и прибыль по рекламным каналам перед перераспределением текущего бюджета.",
        "organic": "Выберите один способ продвижения и оцените необходимые время и ресурсы в пределах текущего бюджета.",
    }
    if material.source_type != "glossary":
        for key, proposed_action in constraint_actions.items():
            if chosen.signals.get("constraint_" + key):
                action = proposed_action
                break
    phase = (
        "Применить"
        if material.source_type in {"document", "calculator"}
        else "Углубиться"
        if material.source_type in {"course", "webinar"}
        else "Разобраться"
    )
    return Recommendation(
        material=material,
        reasons=chosen.reasons,
        next_action=action,
        phase=phase,
        score=round(chosen.score, 6),
        rank_score=round(chosen.rank_score, 6),
        signals={
            **chosen.signals,
            **({"coverage_priority": 1.0} if chosen.coverage_priority else {}),
            "diversity_penalty": round(chosen.diversity_penalty, 6),
            **({"coverage_bonus": round(chosen.coverage_bonus, 6)} if chosen.coverage_bonus else {}),
        },
    )
