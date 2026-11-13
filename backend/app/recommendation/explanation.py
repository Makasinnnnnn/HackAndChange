"""Output actions use material type; explanations originate in actual ranking evidence."""

from ..models import Recommendation


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
