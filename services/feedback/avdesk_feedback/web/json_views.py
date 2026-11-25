"""Feedback objects as JSON, in the shapes documented in openapi.yaml.

The public invite view is what a reviewer's link reveals: the delivered
video and their own label, never other reviewers or the request id.
"""
from datetime import datetime
from typing import Any

from avdesk_feedback.domain.metrics import FeedbackMetrics
from avdesk_feedback.domain.models import OUTCOME_LABELS, RATING_DIMENSIONS, FeedbackInvite, InviteState


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def form_choices() -> dict[str, Any]:
    return {"dimensions": [{"key": k, "label": v} for k, v in RATING_DIMENSIONS.items()],
            "outcomes": [{"value": str(k), "label": v} for k, v in OUTCOME_LABELS.items()]}


def public_invite_json(invite: FeedbackInvite | None, state: InviteState) -> dict[str, Any]:
    if state != InviteState.OPEN:
        return {"state": str(state)}
    work = invite.work
    return {"state": str(state), **form_choices(),
            "invite": {"public_code": work.public_code, "title": work.title, "type_label": work.type_label,
                       "delivery_url": work.delivery_url, "recipient_label": invite.recipient_label,
                       "expires_at": iso(invite.expires_at)}}


def admin_invite_json(invite: FeedbackInvite) -> dict[str, Any]:
    return {"token": invite.token, "recipient_label": invite.recipient_label, "is_requester": invite.is_requester,
            "expires_at": iso(invite.expires_at), "used_at": iso(invite.used_at),
            "verdict_pending": invite.verdict_pending}


def metrics_json(metrics: FeedbackMetrics) -> dict[str, Any]:
    return {
        "response_rate": metrics.response_rate,
        "outcome_counts": [{"outcome": str(o), "label": label, "count": metrics.outcome_counts.get(o, 0)}
                           for o, label in OUTCOME_LABELS.items()],
        "dimensions": form_choices()["dimensions"],
        "ratings_by_type": metrics.ratings_by_type,
        "ratings_by_diretoria": metrics.ratings_by_diretoria,
        "requester_outcomes": {str(k): str(v) for k, v in metrics.requester_outcomes.items()},
    }
