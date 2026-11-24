"""Feedback-side metrics for the AV manager: response rate, outcomes and ratings.

Ratings are grouped by the type and diretoria stored in each invite's
snapshot of the delivered request (ADR-3), so this service answers them on
its own data, without asking the requests service. The snapshot records
what was delivered, which is the grouping the AV manager wants anyway.
requester_outcomes is published so the metrics page can join it with the
briefing scores the requests service reports (ADR-6).
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Callable, Iterable

from avdesk_feedback.domain.models import RATING_DIMENSIONS, FeedbackInvite, FeedbackResponse, Outcome


def share(part: int, total: int) -> float | None:
    return part / total if total else None


def response_rate(invites: list[FeedbackInvite]) -> float | None:
    return share(sum(i.used_at is not None for i in invites), len(invites))


def average_ratings_by(responses: Iterable[FeedbackResponse],
                       key: Callable[[FeedbackResponse], str | None]) -> dict[str, dict[str, float]]:
    groups: dict[str, list[FeedbackResponse]] = defaultdict(list)
    for response in responses:
        group = key(response)
        if group is not None:
            groups[group].append(response)
    return {group: {d: mean(r.answer.ratings[d] for r in rows) for d in RATING_DIMENSIONS}
            for group, rows in sorted(groups.items())}


@dataclass(frozen=True)
class FeedbackMetrics:
    response_rate: float | None
    outcome_counts: dict[Outcome, int]
    ratings_by_type: dict[str, dict[str, float]]
    ratings_by_diretoria: dict[str, dict[str, float]]
    requester_outcomes: dict[int, Outcome]


def feedback_metrics(invites: list[FeedbackInvite], responses: list[FeedbackResponse]) -> FeedbackMetrics:
    invites_by_id = {i.id: i for i in invites}

    def from_snapshot(field: str) -> Callable[[FeedbackResponse], str | None]:
        def group(response: FeedbackResponse) -> str | None:
            invite = invites_by_id.get(response.invite_id)
            return getattr(invite.work, field) if invite else None
        return group

    requester_responses = [r for r in responses if r.is_requester]
    return FeedbackMetrics(
        response_rate=response_rate(invites),
        outcome_counts=dict(Counter(r.answer.outcome for r in requester_responses)),
        ratings_by_type=average_ratings_by(responses, from_snapshot("type_label")),
        ratings_by_diretoria=average_ratings_by(responses, from_snapshot("diretoria")),
        requester_outcomes={r.request_id: r.answer.outcome for r in requester_responses},
    )
