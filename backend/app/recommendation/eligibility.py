"""Hard constraints are applied before confidence thresholds and personalization."""

from .intent import profit_mechanisms, sector_compatibility, sectors_for


def exclusion_reason(material, intent, feedback, baseline=False):
    if not material.published or not material.title.strip():
        return "unpublished"
    if not sector_compatibility(material, intent.sectors):
        return "sector"
    if "fixed_ad_spend" in intent.constraints and not profit_mechanisms(material):
        return "unsupported_constraint"
    if "fixed_ad_spend" in intent.constraints:
        if material.source_type == "glossary" and not any(
            term in intent.query.casefold() for term in ("что такое", "термин", "определение")
        ):
            return "definition_instead_of_action"
        if not intent.sectors and sectors_for(material.title):
            return "unrequested_specialization"
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
