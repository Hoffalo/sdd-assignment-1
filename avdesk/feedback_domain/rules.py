"""Feedback rules: what a valid response is and when an invite link still works."""
from datetime import datetime, timedelta
from typing import Mapping

from avdesk.feedback_domain.models import RATING_DIMENSIONS, FeedbackAnswer, FeedbackInvite, InviteState, Outcome

RATING_RANGE = range(1, 6)
COMMENT_MAX = 3000


def invite_expiry(created_at: datetime, ttl_days: int) -> datetime:
    return created_at + timedelta(days=ttl_days)


def invite_state(invite: FeedbackInvite | None, now: datetime) -> InviteState:
    if invite is None:
        return InviteState.NOT_FOUND
    # Checked before expiry so a reviewer who answered in time is told so,
    # not that their link expired.
    if invite.used_at is not None:
        return InviteState.USED
    if now >= invite.expires_at:
        return InviteState.EXPIRED
    return InviteState.OPEN


def parse_answer(form: Mapping[str, str]) -> tuple[FeedbackAnswer | None, dict[str, str]]:
    errors: dict[str, str] = {}
    ratings: dict[str, int] = {}
    for dimension in RATING_DIMENSIONS:
        raw = (form.get(dimension) or "").strip()
        if not raw.isdigit() or int(raw) not in RATING_RANGE:
            errors[dimension] = "Dê uma nota de 1 a 5."
        else:
            ratings[dimension] = int(raw)

    outcome = form.get("outcome", "")
    if outcome not in {o.value for o in Outcome}:
        errors["outcome"] = "Escolha uma das opções."

    comment = (form.get("comment") or "").strip()
    if len(comment) > COMMENT_MAX:
        errors["comment"] = f"Use no máximo {COMMENT_MAX} caracteres."

    if errors:
        return None, errors
    return FeedbackAnswer(ratings, Outcome(outcome), comment), {}
