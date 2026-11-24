from datetime import date, datetime, timedelta, timezone

from avdesk_requests.domain.briefing import Briefing
from avdesk_requests.domain.metrics import (
    median_turnaround_by, on_time_rate, request_metrics, rush_share, turnaround_days,
)
from avdesk_requests.domain.models import Request, Status
from tests.factories import make_catalog

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def make_request(id=1, type_code="teaser", needed_by=date(2026, 10, 10), accepted_days=None, delivered_days=None,
                 rush=False, score=50, status=Status.DELIVERED) -> Request:
    return Request(
        id=id, public_code=f"AV-{id}", tracking_token=f"t{id}",
        briefing=Briefing(type_code=type_code, needed_by=needed_by), status=status, rush=rush,
        briefing_score=score, created_at=T0, updated_at=T0,
        accepted_at=T0 + timedelta(days=accepted_days) if accepted_days is not None else None,
        delivered_at=T0 + timedelta(days=delivered_days) if delivered_days is not None else None)


def test_turnaround_runs_from_acceptance_to_delivery():
    assert turnaround_days(make_request(accepted_days=1, delivered_days=6)) == 5


def test_turnaround_is_unknown_until_delivered():
    assert turnaround_days(make_request(accepted_days=1)) is None


def test_median_turnaround_is_grouped_by_the_given_key():
    requests = [make_request(1, accepted_days=0, delivered_days=d) for d in (2, 4, 9)]

    assert median_turnaround_by(requests, lambda r: r.briefing.type_code) == {"teaser": 4}


def test_on_time_rate_compares_delivery_with_needed_by():
    requests = [make_request(1, delivered_days=5), make_request(2, delivered_days=20)]

    assert on_time_rate(requests) == 0.5


def test_rates_are_none_when_there_is_nothing_to_measure():
    assert (on_time_rate([]), rush_share([])) == (None, None)


def test_rush_share_counts_flagged_requests():
    assert rush_share([make_request(1, rush=True), make_request(2), make_request(3), make_request(4)]) == 0.25


def test_turnaround_is_grouped_by_the_type_label_from_the_catalog():
    metrics = request_metrics([make_request(1, accepted_days=0, delivered_days=3)], make_catalog())

    assert metrics.median_turnaround_by_type == {"Teaser": 3}


def test_only_statuses_that_occur_are_counted():
    metrics = request_metrics([make_request(1, status=Status.SUBMITTED), make_request(2, status=Status.SUBMITTED)],
                              make_catalog())

    assert metrics.by_status == {Status.SUBMITTED: 2}


def test_briefing_scores_are_published_per_request_for_the_outcome_join():
    metrics = request_metrics([make_request(1, score=90), make_request(2, score=30)], make_catalog())

    assert (metrics.briefing_scores, metrics.average_score) == ({1: 90, 2: 30}, 60)


def test_no_requests_means_no_average_score():
    assert request_metrics([], make_catalog()).average_score is None
