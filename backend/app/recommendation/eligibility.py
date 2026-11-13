"""Hard constraints are applied before confidence thresholds and personalization."""

from .intent import sector_compatibility


def exclusion_reason(material, intent, feedback, baseline=False):
    if not material.published or not material.title.strip():
        return "unpublished"
    if not sector_compatibility(material, intent.sectors):
        return "sector"
    title = material.title.casefold()
    if (
        intent.opening
        and not intent.closing
        and any(term in title for term in ("закрыть", "ликвидац", "прекращение деятельности"))
        and not any(term in title for term in ("открыть", "открытие", "запуск"))
    ):
        return "opposite_action"
    if not baseline and feedback.get(material.id) in {"completed", "known", "not_relevant"}:
        return "feedback"
    return None
