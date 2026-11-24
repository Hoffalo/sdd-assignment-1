"""Translates the JSON body the UI sends into a Briefing, using the Builder.

This is the boundary: types are coerced and unknown keys ignored here, then
the domain's BriefingValidator decides what is missing or wrong, so the
rules live in one place and the UI cannot bypass them.
"""
from datetime import date
from typing import Any, Mapping

from avdesk_requests.domain.briefing import Answer, Briefing, BriefingBuilder
from avdesk_requests.domain.models import Catalog


def parse_date(raw: Any) -> date | None:
    try:
        return date.fromisoformat(str(raw or "").strip())
    except ValueError:
        return None


def parse_int(raw: Any) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    text = str(raw or "").strip()
    return int(text) if text.isdigit() else None


def _text(body: Mapping[str, Any], key: str) -> str:
    value = body.get(key)
    return value.strip() if isinstance(value, str) else ""


def _answer(raw: Any, multiple: bool) -> Answer:
    if multiple:
        return tuple(str(v) for v in raw) if isinstance(raw, list) else ()
    return raw.strip() if isinstance(raw, str) else ""


def briefing_from_json(body: Mapping[str, Any], catalog: Catalog) -> Briefing:
    answers = body.get("answers") if isinstance(body.get("answers"), dict) else {}
    builder = (BriefingBuilder()
               .requester(_text(body, "requester_name"), _text(body, "requester_email"),
                          parse_int(body.get("diretoria_id")))
               .request_type(_text(body, "type_code"), _text(body, "type_detail"))
               .title(_text(body, "title"))
               .campaign(_text(body, "campaign"))
               .needs_c_level_approval(body.get("needs_c_level_approval") is True)
               .deadline(parse_date(body.get("needed_by")), _text(body, "needed_by_reason"))
               .rush_reason(_text(body, "rush_reason")))
    # Only questions in the catalog are read, so a client cannot store arbitrary keys.
    for question in catalog.questions:
        builder.answer(question.key, _answer(answers.get(question.key), question.kind == "multichoice"))
    return builder.build()
