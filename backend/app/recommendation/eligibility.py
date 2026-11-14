"""Hard constraints are applied before confidence thresholds and personalization."""

import re
from datetime import date

from .intent import (
    TAX_SUBJECTS,
    informative_words,
    material_topics,
    platforms_for,
    profit_mechanisms,
    sector_compatibility,
    sectors_for,
    topics_for,
)
from .tasks import material_tasks, task_evidence, task_matches, text_key


def exclusion_reason(material, intent, feedback, baseline=False):
    if not material.published or not material.title.strip():
        return "unpublished"
    if not sector_compatibility(material, intent.sectors):
        return "sector"
    title = text_key(material.title)
    text = text_key(material.title + " " + material.description)
    if "business_plan" in intent.tasks:
        subject = re.search(r"магазин\w*\s+(одежд|обув|цвет|продукт)", title)
        if subject and subject.group(1) not in text_key(intent.query):
            return "unrequested_retail_niche"
    if "financial_calculation" in intent.constraints and not (
        "profitability" in task_matches(material.title)
        or re.search(r"экономик|финансов|показател", title)
        or re.search(r"(?:рассчит|посчит|расчет|формул)\w*.{0,20}(?:марж|рентабельност)", text)
    ):
        return "incidental_profitability_mention"
    if "lease" in intent.tasks and intent.requested_format == "document":
        for subtype in ("субаренд", "гарантийн"):
            if subtype in title and subtype not in text_key(intent.query):
                return "different_lease_document"
        if "помещени" in text_key(intent.query) and "помещени" not in title:
            return "different_lease_object"
        if "договор" in text_key(intent.query) and re.search(
            r"уведомлен|письм|расторжен|акт\b|дополнительн\w* соглашен", title
        ):
            return "different_lease_action"
    if (
        intent.tasks
        and material.source_type == "document"
        and not intent.requested_format
        and not (intent.tasks & material_tasks(material) & task_matches(material.title))
    ):
        return "incidental_document_mention"
    if (
        "delegation" in intent.tasks
        and "recruitment" not in intent.tasks
        and re.search(r"найм|первый сотрудник", title)
    ):
        return "hiring_instead_of_delegation"
    if (
        "delegation" in intent.tasks
        and not re.search(r"нейросет|\bии\b|аутсорс|подрядчик", text_key(intent.query))
        and not re.search(r"сотрудник|команд|руковод", text)
    ):
        return "delegation_without_team_context"
    if (
        "profitability" in intent.tasks
        and not intent.tasks & {"tax_payment", "tax_regime"}
        and re.search(r"налог\w* на прибыл|декларац|курсов\w* разниц|нераспределенн\w* прибыл", title)
    ):
        return "profit_distribution_instead_of_profitability"
    if (
        "demand" in intent.tasks
        and re.search(r"(?:китай|китае|китайск|экспорт|импорт|тамож)", text)
        and not re.search(r"(?:китай|китае|китайск|экспорт|импорт|тамож)", text_key(intent.query))
    ):
        return "foreign_trade_instead_of_validation"
    if "profit_diagnosis" in intent.constraints and (
        material_tasks(material) & {"launch", "franchise", "cash_flow"}
        or re.search(
            r"(?:где|как)\s+(?:взять|найти|привлечь).{0,25}(?:деньги|денег|инвестиц)|стартов\w* капитал",
            title,
        )
        or re.search(r"налог\w* на прибыл|декларац|курсов\w* разниц|нераспределенн\w* прибыл", title)
    ):
        return "different_financial_goal"
    if (
        intent.tasks
        and re.search(r"самозанят|\bнпд\b", title)
        and "самозанят" not in intent.query.casefold()
        and "нпд" not in intent.query.casefold()
    ):
        return "unrequested_taxpayer_status"
    if "closing" in intent.tasks and re.search(r"\bусн\b", title) and "усн" not in text_key(intent.query):
        return "unrequested_tax_regime_closing"
    if intent.tasks & {"tax_reporting", "tax_overdue", "tax_payment", "vat", "tax_regime"}:
        years = {int(year) for year in re.findall(r"\b20\d{2}\b", title)}
        requested_years = {int(year) for year in re.findall(r"\b20\d{2}\b", intent.query)}
        if years and max(years) < date.today().year and not years & requested_years:
            return "past_year_tax_instruction"
    if not intent.tasks and not intent.topics and not intent.sectors and not intent.constraints:
        words = informative_words(intent.search)
        if not words or len(words & informative_words(material.title)) / len(words) < 0.67:
            return "no_informative_anchor"
    material_platforms = platforms_for(text)
    if intent.platforms and material_platforms and not intent.platforms & material_platforms:
        return "platform_conflict"
    if (
        "commissions" in intent.tasks
        and len(intent.platforms) > 1
        and not intent.platforms <= material_platforms
    ):
        return "incomplete_platform_comparison"
    if len(intent.comparison_terms) > 1 and not all(
        re.search(TAX_SUBJECTS[key], text) for key in intent.comparison_terms
    ):
        return "incomplete_tax_comparison"
    if len(intent.comparison_terms) > 1 and material.source_type == "document":
        return "form_instead_of_comparison"
    if material.source_type in intent.excluded_formats:
        return "excluded_format"
    if intent.requested_format and material.source_type != intent.requested_format:
        return "requested_format"
    if (
        intent.requested_format
        and not intent.tasks
        and intent.topics
        and not (intent.topics & (material_topics(material) | set(topics_for(material.title))))
    ):
        return "format_without_task"
    if "launch" in intent.tasks and not intent.platforms and material_platforms:
        return "unrequested_platform_launch"
    if (
        "launch" in intent.tasks
        and not intent.sectors
        and re.search(r"бизнес (?:на|по|в сфере|в области)\s", title)
        and not re.search(r"бизнес (?:на|по|в сфере|в области)\s", intent.query.casefold())
    ):
        return "unrequested_business_niche"
    if "registration" in intent.tasks and "отказ" in title and "отказ" not in intent.query.casefold():
        return "unrequested_registration_failure"
    if (
        "demand" in intent.tasks
        and "demand_forecast" not in intent.tasks
        and "demand_forecast" in material_tasks(material)
    ):
        return "forecast_instead_of_validation"
    if "no_franchise" in intent.constraints and "franchise" in material_tasks(material):
        return "excluded_franchise"
    if "no_employees" in intent.constraints and any(
        term in text
        for term in (
            "работодател",
            "найме сотруд",
            "оформить сотруд",
            "сведения о физлиц",
            "отпуск",
            "страховые взносы ооо",
        )
    ):
        return "requires_employees"
    if "no_discounts" in intent.constraints and "скид" in title and "без скид" not in text:
        return "discounts"
    if "target_usn" in intent.constraints and not re.search(r"\bусн\b", text):
        return "tax_target"
    if "no_hiring" in intent.constraints and "recruitment" in material_tasks(material):
        return "excluded_hiring"
    if (
        "preserve_staff" in intent.constraints
        and re.search(r"увольн|сокращени\w* штат|расход\w* на персонал", title)
        and not re.search(r"без увольн|сохран.{0,15}(?:сотруд|команд|персонал)", text)
    ):
        return "staff_preservation_unconfirmed"
    if (
        intent.entity
        and ("ооо" if intent.entity == "ип" else "ип") in title.split()
        and intent.entity not in title.split()
    ):
        return "entity_conflict"
    if intent.tasks and not task_evidence(material, intent.tasks):
        return "unsupported_task"
    if "claim" in intent.tasks and "поставщик" in intent.query.casefold() and "ответ на претензи" in title:
        return "opposite_claim_direction"
    if "returns" in intent.tasks and "поставщик" not in intent.query.casefold() and "поставщик" in title:
        return "opposite_return_direction"
    if intent.tasks and not intent.definition and material.source_type == "glossary":
        return "definition_instead_of_action"
    if intent.tasks and not intent.definition and not intent.sectors and sectors_for(material.title):
        return "unrequested_specialization"
    if (
        intent.tasks
        and not re.search(r"бизнес[ -]иде[ияйюь].{0,10}\bв\b", intent.query.casefold())
        and re.search(r"бизнес[ -]иде[ияйюь].{0,10}\bв\b", title)
    ):
        return "unrequested_regional_ideas"
    if "seasonal" not in intent.tasks and "seasonal" in material_tasks(material):
        return "unrequested_season"
    if "fixed_ad_spend" in intent.constraints and not profit_mechanisms(material):
        return "unsupported_constraint"
    if "fixed_ad_spend" in intent.constraints:
        if material.source_type == "glossary" and not any(
            term in intent.query.casefold() for term in ("что такое", "термин", "определение")
        ):
            return "definition_instead_of_action"
        if not intent.sectors and sectors_for(material.title):
            return "unrequested_specialization"
    if intent.closing and "closing" not in material_tasks(material):
        return "opposite_action"
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
