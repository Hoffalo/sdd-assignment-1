"""Domain objects as JSON, in the shapes documented in openapi.yaml.

Two views of a request on purpose: the public one (tracking page, reached by
a secret link) never carries the requester's e-mail or the internal actor
names; the admin one carries everything the AV manager works with.
Dates are ISO strings so the UI formats them in the reader's locale.
"""
from datetime import date, datetime
from typing import Any

from avdesk_requests.domain.briefing import Briefing
from avdesk_requests.domain.leadtime import LeadTimeAssessment
from avdesk_requests.domain.lifecycle import Action
from avdesk_requests.domain.metrics import RequestMetrics
from avdesk_requests.domain.models import Catalog, Question, Request, RequestEvent, Status


def iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value else None


def question_json(question: Question) -> dict[str, Any]:
    return {"key": question.key, "type_code": question.type_code, "section": question.section,
            "label": question.label, "help": question.help, "kind": question.kind,
            "options": list(question.options), "required": question.required, "position": question.position,
            "depends_on": question.depends_on, "depends_value": question.depends_value}


def catalog_json(catalog: Catalog) -> dict[str, Any]:
    return {
        "types": [{"code": t.code, "label": t.label, "min_lead_days": t.min_lead_days, "detail_label": t.detail_label}
                  for t in catalog.types],
        "questions": [question_json(q) for q in sorted(catalog.questions, key=lambda q: q.position)],
        "diretorias": [{"id": d.id, "name": d.name} for d in catalog.diretorias],
        "analysts": [{"id": a.id, "name": a.name} for a in catalog.analysts],
        "statuses": [{"value": str(s), "label": s.label} for s in Status],
    }


def assessment_json(assessment: LeadTimeAssessment) -> dict[str, Any]:
    return {"rush": assessment.rush, "available_days": assessment.available_days,
            "required_days": assessment.required_days, "earliest_date": iso(assessment.earliest_date),
            "work_deadline": iso(assessment.work_deadline)}


def briefing_json(briefing: Briefing) -> dict[str, Any]:
    return {
        "requester_name": briefing.requester_name, "requester_email": briefing.requester_email,
        "diretoria_id": briefing.diretoria_id, "type_code": briefing.type_code, "type_detail": briefing.type_detail,
        "title": briefing.title, "campaign": briefing.campaign,
        "needs_c_level_approval": briefing.needs_c_level_approval, "needed_by": iso(briefing.needed_by),
        "needed_by_reason": briefing.needed_by_reason, "rush_reason": briefing.rush_reason,
        "answers": {k: list(v) if isinstance(v, tuple) else v for k, v in briefing.answers.items()},
    }


def _event_json(event: RequestEvent, with_actor: bool) -> dict[str, Any]:
    view = {"to_status": str(event.to_status), "to_status_label": event.to_status.label, "note": event.note,
            "created_at": iso(event.created_at)}
    if with_actor:
        view["actor"] = event.actor
    return view


def _status_fields(request: Request) -> dict[str, Any]:
    return {"public_code": request.public_code, "status": str(request.status), "status_label": request.status.label,
            "rush": request.rush, "analyst_id": request.analyst_id, "review_url": request.review_url,
            "delivery_url": request.delivery_url}


def tracking_json(request: Request, timeline: list[RequestEvent], editable: bool) -> dict[str, Any]:
    briefing = briefing_json(request.briefing)
    del briefing["requester_email"]
    return {**_status_fields(request), "briefing": briefing, "editable": editable,
            "timeline": [_event_json(e, with_actor=False) for e in timeline]}


def summary_json(request: Request) -> dict[str, Any]:
    """One inbox row."""
    briefing = request.briefing
    return {"id": request.id, **_status_fields(request), "title": briefing.title, "type_code": briefing.type_code,
            "diretoria_id": briefing.diretoria_id, "needed_by": iso(briefing.needed_by),
            "briefing_score": request.briefing_score}


def detail_json(request: Request, timeline: list[RequestEvent], actions: list[Action], can_undo: bool,
                markdown: str, slack: str) -> dict[str, Any]:
    return {
        "id": request.id, **_status_fields(request), "tracking_token": request.tracking_token,
        "briefing_score": request.briefing_score, "task_url": request.task_url,
        "accepted_at": iso(request.accepted_at), "delivered_at": iso(request.delivered_at),
        "created_at": iso(request.created_at), "briefing": briefing_json(request.briefing),
        "actions": [{"name": a.name, "label": a.label} for a in actions], "can_undo": can_undo,
        "briefing_markdown": markdown, "slack_message": slack,
        "timeline": [_event_json(e, with_actor=True) for e in timeline],
    }


def metrics_json(metrics: RequestMetrics) -> dict[str, Any]:
    return {
        "total_requests": metrics.total_requests,
        "by_status": [{"status": str(s), "label": s.label, "count": n} for s, n in metrics.by_status.items()],
        "rush_share": metrics.rush_share, "on_time_rate": metrics.on_time_rate,
        "median_turnaround_by_type": metrics.median_turnaround_by_type, "average_score": metrics.average_score,
        "briefing_scores": {str(k): v for k, v in metrics.briefing_scores.items()},
    }
