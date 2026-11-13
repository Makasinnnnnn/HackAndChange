"""Output actions use material type; explanations originate in actual ranking evidence."""

from ..models import Recommendation
from .intent import profit_mechanisms


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
        signals={**chosen.signals, "diversity_penalty": round(chosen.diversity_penalty, 6)},
    )
