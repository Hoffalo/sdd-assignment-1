"""Plain-text renderings of a request: the Markdown briefing export and the Slack message.

The same Markdown feeds the ClickUp task description and the admin's copy
button, so the briefing reads the same wherever the team picks it up.
"""
from avdesk.requests_domain.models import Catalog, Request
from avdesk.requests_domain.validators import is_blank


def _format_answer(value) -> str:
    if isinstance(value, tuple):
        return ", ".join(value)
    return {"sim": "Sim", "nao": "Não"}.get(value, value)


def briefing_markdown(request: Request, catalog: Catalog) -> str:
    briefing = request.briefing
    request_type = catalog.type(briefing.type_code)
    diretoria = catalog.diretoria(briefing.diretoria_id)
    type_label = request_type.label if request_type else briefing.type_code
    if briefing.type_detail:
        type_label = f"{type_label} ({briefing.type_detail})"

    lines = [
        f"# {request.public_code} · {briefing.title}",
        "",
        f"- **Tipo:** {type_label}",
        f"- **Solicitante:** {briefing.requester_name} <{briefing.requester_email}>"
        f" · {diretoria.name if diretoria else '—'}",
        f"- **Campanha:** {briefing.campaign or '—'}",
        f"- **Prazo:** {briefing.needed_by:%d/%m/%Y} ({briefing.needed_by_reason})",
        f"- **Conteúdo de conferência:** {'Sim' if briefing.for_conference else 'Não'}",
        f"- **Briefing completo:** {request.briefing_score}%",
    ]
    if request.rush:
        lines.append(f"- **Prazo curto:** {briefing.rush_reason}")

    section = None
    for question in catalog.questions_for(briefing.type_code):
        value = briefing.answers.get(question.key)
        if is_blank(value):
            continue
        if question.section != section:
            section = question.section
            lines += ["", f"## {section}"]
        lines.append(f"- **{question.label}** {_format_answer(value)}")
    return "\n".join(lines)


def slack_message(request: Request, catalog: Catalog) -> str:
    briefing = request.briefing
    request_type = catalog.type(briefing.type_code)
    rush = " :rotating_light: prazo curto" if request.rush else ""
    return (f"novo pedido de av: *{request.public_code}* · {briefing.title} "
            f"({request_type.label if request_type else briefing.type_code}) · "
            f"pra {briefing.needed_by:%d/%m} · status: {request.status.label.lower()}{rush}")
