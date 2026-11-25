"""The feedback side of the seam: the requester's verdict travelling back to the requests service."""
import contextlib
import io
import json
import urllib.error

import pytest

from avdesk_feedback.domain.models import Outcome, ResponseReceived
from avdesk_feedback.requests_client import (
    TIMEOUT_SECONDS, DisabledRequestVerdicts, HttpRequestVerdicts, RequestsUnavailable,
)
from avdesk_feedback.verdict_observer import RequesterVerdictObserver


class RecordingOpener:
    """Stands in for urllib's urlopen; timeout is keyword-only, as urlopen's second positional is data."""

    def __init__(self, error: Exception | None = None):
        self.calls = []
        self._error = error

    def __call__(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self._error:
            raise self._error
        return contextlib.nullcontext(io.BytesIO(b'{"status": "closed"}'))


class StubVerdicts:
    def __init__(self, error: Exception | None = None):
        self.sent = []
        self._error = error

    def send_verdict(self, request_id, outcome):
        self.sent.append((request_id, outcome))
        if self._error:
            raise self._error


def response(is_requester=True, outcome=Outcome.APPROVED) -> ResponseReceived:
    return ResponseReceived(invite_id=7, request_id=42, public_code="AV-2026-0042", outcome=outcome,
                            is_requester=is_requester)


# HTTP adapter

def test_the_verdict_is_posted_to_the_request_with_a_service_token():
    opener = RecordingOpener()

    HttpRequestVerdicts("http://requests:8000", lambda: "svc-token", opener).send_verdict(42, Outcome.MAJOR_CHANGES)

    request = opener.calls[0][0]
    assert (request.method, request.full_url, request.get_header("Authorization"), json.loads(request.data)) == (
        "POST", "http://requests:8000/requests/42/verdict", "Bearer svc-token", {"verdict": "major_changes"})


def test_the_verdict_call_has_a_timeout():
    opener = RecordingOpener()

    HttpRequestVerdicts("http://requests", lambda: "svc", opener).send_verdict(42, Outcome.APPROVED)

    assert opener.calls[0][1] == TIMEOUT_SECONDS


@pytest.mark.parametrize("error", [urllib.error.URLError("refused"), TimeoutError("slow"),
                                   urllib.error.HTTPError("http://requests", 503, "down", {}, None)])
def test_an_unreachable_or_failing_requests_service_is_reported_as_unavailable(error):
    client = HttpRequestVerdicts("http://requests", lambda: "svc", RecordingOpener(error))

    with pytest.raises(RequestsUnavailable):
        client.send_verdict(42, Outcome.APPROVED)


def test_without_a_requests_url_verdicts_are_unavailable():
    with pytest.raises(RequestsUnavailable):
        DisabledRequestVerdicts().send_verdict(42, Outcome.APPROVED)


# Observer

def test_the_requesters_answer_is_sent_to_the_requests_service(mocker):
    verdicts = StubVerdicts()

    RequesterVerdictObserver(verdicts, mocker.Mock()).on_response(response(outcome=Outcome.MINOR_TWEAKS))

    assert verdicts.sent == [(42, Outcome.MINOR_TWEAKS)]


def test_a_reviewers_answer_stays_in_the_feedback_service(mocker):
    verdicts = StubVerdicts()

    RequesterVerdictObserver(verdicts, mocker.Mock()).on_response(response(is_requester=False))

    assert verdicts.sent == []


def test_a_verdict_that_cannot_be_delivered_is_kept_pending(mocker):
    feedback = mocker.Mock()

    sent = RequesterVerdictObserver(StubVerdicts(RequestsUnavailable("down")), feedback).send(response())

    assert (sent, feedback.mark_verdict_pending.call_args.args) == (False, (7, True))


def test_a_delivered_verdict_clears_the_pending_flag(mocker):
    feedback = mocker.Mock()

    sent = RequesterVerdictObserver(StubVerdicts(), feedback).send(response())

    assert (sent, feedback.mark_verdict_pending.call_args.args) == (True, (7, False))
