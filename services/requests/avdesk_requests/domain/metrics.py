"""Request-side metrics for the AV manager: volume, lead time and delivery.

Each service reports the metrics its own data can answer; the feedback
service reports ratings and outcomes, and the metrics page puts the two side
by side (ADR-6). briefing_scores is published so the page can do the one
join that needs both sides: average briefing score per feedback outcome.

The calculations are plain functions over lists so they can be tested with a
handful of hand-made rows.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean, median
from typing import Callable

from avdesk_requests.domain.models import Catalog, Request, Status

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


@dataclass(frozen=True)
class RequestMetrics:
    total_requests: int
    by_status: dict[Status, int]
    rush_share: float | None
    median_turnaround_by_type: dict[str, float]
    on_time_rate: float | None
    average_score: float | None
    briefing_scores: dict[int, int]


def request_metrics(requests: list[Request], catalog: Catalog) -> RequestMetrics:
    def type_label(request: Request) -> str:
        request_type = catalog.type(request.briefing.type_code)
        return request_type.label if request_type else request.briefing.type_code

    status_counts = Counter(r.status for r in requests)
    return RequestMetrics(
        total_requests=len(requests),
        by_status={s: status_counts[s] for s in Status if status_counts[s]},
        rush_share=rush_share(requests),
        median_turnaround_by_type=median_turnaround_by(requests, type_label),
        on_time_rate=on_time_rate([r for r in requests if r.status in DELIVERED_STATUSES]),
        average_score=mean(r.briefing_score for r in requests) if requests else None,
        briefing_scores={r.id: r.briefing_score for r in requests},
    )
