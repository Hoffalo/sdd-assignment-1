"""Briefing validation, with messages written for requesters in pt-BR.

Which answers are required comes from the question data, not from code, so a
new request type or question never needs an if/elif here (OCP). Checks that
depend on the kind of answer live in one table, ANSWER_CHECKS.
"""
from datetime import date
from typing import Callable
from urllib.parse import urlparse

from avdesk.requests_domain.briefing import Answer, Briefing
from avdesk.requests_domain.leadtime import LeadTimeAssessment
from avdesk.requests_domain.models import Catalog, Question

EMAIL_DOMAIN = "gobrasa.org"
SHORT_TEXT_MAX = 200
LONG_TEXT_MAX = 3000

REQUIRED = "Campo obrigatório."


def is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _check_url(value: Answer, question: Question) -> str | None:
    return None if is_http_url(str(value)) else "Use um link completo, começando com http:// ou https://."


def _check_date(value: Answer, question: Question) -> str | None:
    try:
        date.fromisoformat(str(value))
    except ValueError:
        return "Informe uma data válida."
    return None


def _check_choice(value: Answer, question: Question) -> str | None:
    return None if value in question.options else "Escolha uma das opções."


def _check_multichoice(value: Answer, question: Question) -> str | None:
    values = (value,) if isinstance(value, str) else value
    return None if set(values) <= set(question.options) else "Escolha apenas entre as opções."


def _check_text_length(value: Answer, question: Question) -> str | None:
    limit = LONG_TEXT_MAX if question.kind == "textarea" else SHORT_TEXT_MAX
    return None if len(str(value)) <= limit else f"Use no máximo {limit} caracteres."


ANSWER_CHECKS: dict[str, Callable[[Answer, Question], str | None]] = {
    "url": _check_url,
    "date": _check_date,
    "choice": _check_choice,
    "multichoice": _check_multichoice,
    "text": _check_text_length,
    "textarea": _check_text_length,
    "yesno": lambda value, _: None if value in ("sim", "nao") else "Responda sim ou não.",
}


def is_blank(value: Answer | None) -> bool:
    if isinstance(value, tuple):
        return not any(v.strip() for v in value)
    return not (value or "").strip()


class BriefingValidator:
    def validate(self, briefing: Briefing, catalog: Catalog, today: date,
                 assessment: LeadTimeAssessment | None) -> dict[str, str]:
        """Returns field name -> message; an empty dict means the briefing can be submitted."""
        errors: dict[str, str] = {}
        self._check_requester(briefing, catalog, errors)
        self._check_type(briefing, catalog, errors)
        self._check_core_text(briefing, errors)
        self._check_deadline(briefing, today, assessment, errors)
        self._check_answers(briefing, catalog, errors)
        return errors

    @staticmethod
    def _check_requester(briefing: Briefing, catalog: Catalog, errors: dict[str, str]) -> None:
        if is_blank(briefing.requester_name):
            errors["requester_name"] = REQUIRED
        local, _, domain = briefing.requester_email.strip().lower().partition("@")
        if not local or domain != EMAIL_DOMAIN:
            errors["requester_email"] = f"Use o seu e-mail @{EMAIL_DOMAIN}."
        if catalog.diretoria(briefing.diretoria_id) is None:
            errors["diretoria_id"] = "Escolha a sua diretoria."

    @staticmethod
    def _check_type(briefing: Briefing, catalog: Catalog, errors: dict[str, str]) -> None:
        request_type = catalog.type(briefing.type_code)
        if request_type is None:
            errors["type_code"] = "Escolha o tipo de vídeo."
        elif request_type.requires_detail and is_blank(briefing.type_detail):
            errors["type_detail"] = REQUIRED

    @staticmethod
    def _check_core_text(briefing: Briefing, errors: dict[str, str]) -> None:
        if is_blank(briefing.title):
            errors["title"] = REQUIRED
        for name in ("title", "campaign", "type_detail", "requester_name"):
            if len(getattr(briefing, name)) > SHORT_TEXT_MAX:
                errors[name] = f"Use no máximo {SHORT_TEXT_MAX} caracteres."
        for name in ("needed_by_reason", "rush_reason"):
            if len(getattr(briefing, name)) > LONG_TEXT_MAX:
                errors[name] = f"Use no máximo {LONG_TEXT_MAX} caracteres."

    @staticmethod
    def _check_deadline(briefing: Briefing, today: date, assessment: LeadTimeAssessment | None,
                        errors: dict[str, str]) -> None:
        if briefing.needed_by is None:
            errors["needed_by"] = "Informe uma data válida."
        elif briefing.needed_by <= today:
            errors["needed_by"] = "A data precisa ser no futuro."
        if is_blank(briefing.needed_by_reason):
            errors["needed_by_reason"] = "Conte por que o vídeo precisa estar pronto nessa data."
        if assessment and assessment.rush and is_blank(briefing.rush_reason):
            errors["rush_reason"] = "O prazo é menor que o recomendado. Conte por que ele não pode mudar."

    @staticmethod
    def _check_answers(briefing: Briefing, catalog: Catalog, errors: dict[str, str]) -> None:
        for question in catalog.questions_for(briefing.type_code):
            value = briefing.answers.get(question.key)
            if is_blank(value):
                if question.required:
                    errors[question.key] = REQUIRED
                continue
            message = ANSWER_CHECKS[question.kind](value, question)
            if message:
                errors[question.key] = message
