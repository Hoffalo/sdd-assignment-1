"""The requests service's delivery message, checked at the boundary and turned into domain objects.

Only the other service sends this, so a malformed body is a bug there:
it gets a plain 422 naming the problem, not a form-style error map.
"""
from datetime import date, datetime
from typing import Any

from avdesk_feedback.domain.facade import Recipient
from avdesk_feedback.domain.models import DeliveredWork

TEXT_FIELDS = ("public_code", "title", "type_label", "diretoria", "delivery_url")


class InvalidDelivery(Exception):
    pass


def delivery_from_json(body: Any) -> tuple[DeliveredWork, list[Recipient]]:
    if not isinstance(body, dict) or not isinstance(body.get("work"), dict):
        raise InvalidDelivery("work is required")
    work = body["work"]
    try:
        delivered = DeliveredWork(
            request_id=int(work["request_id"]),
            **{name: str(work[name]) for name in TEXT_FIELDS},
            needed_by=date.fromisoformat(work["needed_by"]),
            delivered_at=datetime.fromisoformat(work["delivered_at"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidDelivery(f"work is incomplete: {error}") from error
    recipients = body.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        raise InvalidDelivery("at least one recipient is required")
    try:
        return delivered, [Recipient(str(r["label"]), bool(r["is_requester"])) for r in recipients]
    except (KeyError, TypeError) as error:
        raise InvalidDelivery(f"recipient is incomplete: {error}") from error
