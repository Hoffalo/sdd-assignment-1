from datetime import date, datetime, timedelta, timezone

import pytest

from avdesk.feedback_domain.models import FeedbackAnswer, FeedbackResponse, Outcome
from avdesk.requests_domain.briefing import Briefing
from avdesk.requests_domain.models import Request, Status
from avdesk.services.metrics import (
    average_ratings_by, average_score_by_outcome, median_turnaround_by, on_time_rate, response_rate, rush_share,
    turnaround_days,
)

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def make_request(id=1, type_code="teaser", needed_by=date(2026, 10, 10), accepted_days=None, delivered_days=None,
                 rush=False, score=50) -> Request:
    return Request(
        id=id, public_code=f"AV-{id}", tracking_token=f"t{id}",
        briefing=Briefing(type_code=type_code, needed_by=needed_by), status=Status.DELIVERED, rush=rush,
        briefing_score=score, created_at=T0, updated_at=T0,
        accepted_at=T0 + timedelta(days=accepted_days) if accepted_days is not None else None,
        delivered_at=T0 + timedelta(days=delivered_days) if delivered_days is not None else None)


def make_response(request_id=1, tone=5, outcome=Outcome.APPROVED, is_requester=True) -> FeedbackResponse:
    ratings = {"rating_tone": tone, "rating_quality": 4, "rating_process": 3, "rating_usefulness": 5}
    return FeedbackResponse(request_id, request_id, is_requester, FeedbackAnswer(ratings, outcome, ""), T0)


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
    assert (on_time_rate([]), rush_share([]), response_rate([])) == (None, None, None)


def test_rush_share_counts_flagged_requests():
    assert rush_share([make_request(1, rush=True), make_request(2), make_request(3), make_request(4)]) == 0.25


def test_ratings_are_averaged_per_dimension_and_group():
    responses = [make_response(1, tone=5), make_response(2, tone=3)]

    averages = average_ratings_by(responses, lambda r: "Teaser")

    assert averages["Teaser"]["rating_tone"] == 4


def test_responses_without_a_group_are_skipped():
    assert average_ratings_by([make_response()], lambda r: None) == {}


def test_briefing_score_is_compared_by_requester_outcome():
    requests = {1: make_request(1, score=90), 2: make_request(2, score=30)}
    responses = [make_response(1, outcome=Outcome.APPROVED),
                 make_response(2, outcome=Outcome.MAJOR_CHANGES),
                 make_response(2, outcome=Outcome.APPROVED, is_requester=False)]

    assert average_score_by_outcome(requests, responses) == pytest.approx(
        {Outcome.APPROVED: 90, Outcome.MAJOR_CHANGES: 30})
