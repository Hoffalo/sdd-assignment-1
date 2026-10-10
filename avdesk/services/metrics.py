"""Operational metrics for the AV manager, combining both domains.

The calculations are plain functions over lists so they can be tested with a
handful of hand-made rows. MetricsService is the only reader of both facades
for reporting (ADR-2, third crossing of the seam); it only reads.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean, median
from typing import Callable, Iterable

from avdesk.feedback_domain.facade import FeedbackFacade
from avdesk.feedback_domain.models import RATING_DIMENSIONS, FeedbackInvite, FeedbackResponse, Outcome
from avdesk.requests_domain.facade import RequestsFacade
from avdesk.requests_domain.models import Request, Status

DELIVERED_STATUSES = frozenset({Status.DELIVERED, Status.CLOSED})


def share(part: int, total: int) -> float | None:
    return part / total if total else None


def rush_share(requests: list[Request]) -> float | None:
    return share(sum(r.rush for r in requests), len(requests))


def turnaround_days(request: Request) -> float | None:
    if request.accepted_at is None or request.delivered_at is None:
        return None
    return (request.delivered_at - request.accepted_at).total_seconds() / 86400


def median_turnaround_by(requests: list[Request], key: Callable[[Request], str]) -> dict[str, float]:
    groups: dict[str, list[float]] = defaultdict(list)
    for request in requests:
        days = turnaround_days(request)
        if days is not None:
            groups[key(request)].append(days)
    return {group: median(values) for group, values in sorted(groups.items())}


def on_time_rate(requests: list[Request]) -> float | None:
    delivered = [r for r in requests if r.delivered_at is not None]
    on_time = sum(r.delivered_at.date() <= r.briefing.needed_by for r in delivered)
    return share(on_time, len(delivered))


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


def average_score_by_outcome(requests_by_id: dict[int, Request],
                             responses: list[FeedbackResponse]) -> dict[Outcome, float]:
    groups: dict[Outcome, list[int]] = defaultdict(list)
    for response in responses:
        request = requests_by_id.get(response.request_id)
        if request and response.is_requester:
            groups[response.answer.outcome].append(request.briefing_score)
    return {outcome: mean(scores) for outcome, scores in groups.items()}


@dataclass(frozen=True)
class Dashboard:
    total_requests: int
    open_by_status: dict[Status, int]
    rush_share: float | None
    median_turnaround_by_type: dict[str, float]
    on_time_rate: float | None
    ratings_by_type: dict[str, dict[str, float]]
    ratings_by_diretoria: dict[str, dict[str, float]]
    outcome_counts: dict[Outcome, int]
    response_rate: float | None
    average_score: float | None
    average_score_by_outcome: dict[Outcome, float]


class MetricsService:
    def __init__(self, requests: RequestsFacade, feedback: FeedbackFacade):
        self._requests = requests
        self._feedback = feedback

    def dashboard(self) -> Dashboard:
        catalog = self._requests.catalog()
        requests = self._requests.all_requests()
        requests_by_id = {r.id: r for r in requests}
        responses = self._feedback.all_responses()

        def type_label(request: Request) -> str:
            request_type = catalog.type(request.briefing.type_code)
            return request_type.label if request_type else request.briefing.type_code

        def diretoria_name(request: Request) -> str:
            diretoria = catalog.diretoria(request.briefing.diretoria_id)
            return diretoria.name if diretoria else "—"

        def via_request(label: Callable[[Request], str]) -> Callable[[FeedbackResponse], str | None]:
            return lambda response: (label(requests_by_id[response.request_id])
                                     if response.request_id in requests_by_id else None)

        status_counts = Counter(r.status for r in requests)
        return Dashboard(
            total_requests=len(requests),
            open_by_status={s: status_counts[s] for s in Status if status_counts[s]},
            rush_share=rush_share(requests),
            median_turnaround_by_type=median_turnaround_by(requests, type_label),
            on_time_rate=on_time_rate([r for r in requests if r.status in DELIVERED_STATUSES]),
            ratings_by_type=average_ratings_by(responses, via_request(type_label)),
            ratings_by_diretoria=average_ratings_by(responses, via_request(diretoria_name)),
            outcome_counts=dict(Counter(r.answer.outcome for r in responses if r.is_requester)),
            response_rate=response_rate(self._feedback.all_invites()),
            average_score=mean(r.briefing_score for r in requests) if requests else None,
            average_score_by_outcome=average_score_by_outcome(requests_by_id, responses),
        )
