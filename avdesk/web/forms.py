"""Translates between HTML forms and domain objects, using the Builder."""
from dataclasses import dataclass
from datetime import date

from werkzeug.datastructures import MultiDict

from avdesk.requests_domain.briefing import Briefing, BriefingBuilder
from avdesk.requests_domain.models import Catalog, Question

ANSWER_PREFIX = "q_"


@dataclass(frozen=True)
class QuestionSection:
    type_code: str | None
    title: str
    questions: tuple[Question, ...]


def question_sections(catalog: Catalog) -> list[QuestionSection]:
    """Groups questions by section in seed order: common sections first, then one block per type."""
    sections: list[QuestionSection] = []
    for type_code in (None, *(t.code for t in catalog.types)):
        titles: dict[str, list[Question]] = {}
        for question in sorted(catalog.questions, key=lambda q: q.position):
            if question.type_code == type_code:
                titles.setdefault(question.section, []).append(question)
        sections += [QuestionSection(type_code, title, tuple(qs)) for title, qs in titles.items()]
    return sections


def parse_date(raw: str | None) -> date | None:
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


def parse_int(raw: str | None) -> int | None:
    raw = (raw or "").strip()
    return int(raw) if raw.isdigit() else None


def briefing_from_form(form: MultiDict, catalog: Catalog) -> Briefing:
    builder = (BriefingBuilder()
               .requester(form.get("requester_name", ""), form.get("requester_email", ""),
                          parse_int(form.get("diretoria_id")))
               .request_type(form.get("type_code", ""), form.get("type_detail", ""))
               .title(form.get("title", ""))
               .campaign(form.get("campaign", ""))
               .needs_c_level_approval(form.get("needs_c_level_approval") == "sim")
               .deadline(parse_date(form.get("needed_by")), form.get("needed_by_reason", ""))
               .rush_reason(form.get("rush_reason", "")))
    for question in catalog.questions:
        field = ANSWER_PREFIX + question.key
        if question.kind == "multichoice":
            builder.answer(question.key, tuple(form.getlist(field)))
        else:
            builder.answer(question.key, form.get(field, "").strip())
    return builder.build()
