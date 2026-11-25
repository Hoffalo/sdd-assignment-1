"""The requests side of the seam: invites on delivery, and what a requester's verdict does."""
import contextlib
import io
import json
import urllib.error
from datetime import date, datetime, timezone

import pytest

from avdesk_requests.domain.events import RequestSnapshot, StatusChanged
from avdesk_requests.domain.models import Status
from avdesk_requests.domain.verdict import Verdict, action_for_verdict
from avdesk_requests.feedback_client import (
    TIMEOUT_SECONDS, DisabledFeedbackInvites, FeedbackUnavailable, HttpFeedbackInvites,
)
from avdesk_requests.invite_observer import FeedbackInviteObserver
from avdesk_requests.task_tracker import ClickUpTaskTracker, TaskDraft

DELIVERED_AT = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


class RecordingOpener:
    """Stands in for urllib's urlopen; timeout is keyword-only, as urlopen's second positional is data."""

    def __init__(self, error: Exception | None = None, body: bytes = b"{}"):
        self.calls = []
        self._error = error
        self._body = body

    def __call__(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self._error:
            raise self._error
        return contextlib.nullcontext(io.BytesIO(self._body))


class StubFeedback:
    def __init__(self, error: Exception | None = None):
        self.snapshots = []
        self._error = error

    def create_invites(self, snapshot):
        self.snapshots.append(snapshot)
        if self._error:
            raise self._error


def make_snapshot(reviewers=("Bruno",)) -> RequestSnapshot:
    return RequestSnapshot(
        request_id=3, public_code="AV-2026-0003", title="Teaser", type_code="teaser", type_label="Teaser",
        diretoria="Conferências", campaign="", requester_name="Ana", requester_email="ana@gobrasa.org",
        reviewers=reviewers, needed_by=date(2026, 10, 20), needs_c_level_approval=False, rush=True,
        summary_markdown="# AV-2026-0003", delivery_url="https://drive.google.com/x", delivered_at=DELIVERED_AT)


def sent_body(opener: RecordingOpener) -> dict:
    return json.loads(opener.calls[0][0].data)


# HTTP adapter

def test_invites_request_names_the_requester_and_every_reviewer():
    opener = RecordingOpener()

    HttpFeedbackInvites("http://feedback", lambda: "svc", opener).create_invites(make_snapshot(("Bruno", "Carla")))

    assert sent_body(opener)["recipients"] == [{"label": "Ana", "is_requester": True},
                                               {"label": "Bruno", "is_requester": False},
                                               {"label": "Carla", "is_requester": False}]


def test_invites_request_carries_a_copy_of_the_delivered_work():
    opener = RecordingOpener()

    HttpFeedbackInvites("http://feedback", lambda: "svc", opener).create_invites(make_snapshot())

    assert sent_body(opener)["work"] == {
        "request_id": 3, "public_code": "AV-2026-0003", "title": "Teaser", "type_label": "Teaser",
        "diretoria": "Conferências", "delivery_url": "https://drive.google.com/x", "needed_by": "2026-10-20",
        "delivered_at": "2026-10-09T12:00:00+00:00"}


def test_invites_request_posts_to_the_feedback_service_with_a_service_token():
    opener = RecordingOpener()

    HttpFeedbackInvites("http://feedback:8000", lambda: "svc-token", opener).create_invites(make_snapshot())

    request = opener.calls[0][0]
    assert (request.method, request.full_url, request.get_header("Authorization")) == (
        "POST", "http://feedback:8000/invites", "Bearer svc-token")


def test_invites_request_has_a_timeout():
    opener = RecordingOpener()

    HttpFeedbackInvites("http://feedback", lambda: "svc", opener).create_invites(make_snapshot())

    assert opener.calls[0][1] == TIMEOUT_SECONDS


@pytest.mark.parametrize("error", [urllib.error.URLError("refused"), TimeoutError("slow"),
                                   urllib.error.HTTPError("http://feedback/invites", 503, "down", {}, None)])
def test_an_unreachable_or_failing_feedback_service_is_reported_as_unavailable(error):
    client = HttpFeedbackInvites("http://feedback", lambda: "svc", RecordingOpener(error))

    with pytest.raises(FeedbackUnavailable):
        client.create_invites(make_snapshot())


def test_without_a_feedback_url_invites_are_unavailable():
    with pytest.raises(FeedbackUnavailable):
        DisabledFeedbackInvites().create_invites(make_snapshot())


# Observer

def test_delivery_asks_the_feedback_service_for_invites(mocker):
    feedback = StubFeedback()

    FeedbackInviteObserver(feedback, mocker.Mock()).on_status_changed(
        StatusChanged(make_snapshot(), Status.IN_REVIEW, Status.DELIVERED))

    assert [s.request_id for s in feedback.snapshots] == [3]


def test_other_status_changes_ask_for_no_invites(mocker):
    feedback = StubFeedback()

    FeedbackInviteObserver(feedback, mocker.Mock()).on_status_changed(
        StatusChanged(make_snapshot(), Status.ACCEPTED, Status.IN_PRODUCTION))

    assert feedback.snapshots == []


def test_failed_invites_flag_the_request_so_the_manager_can_retry(mocker):
    requests = mocker.Mock()

    sent = FeedbackInviteObserver(StubFeedback(FeedbackUnavailable("down")), requests).send(make_snapshot())

    assert (sent, requests.mark_invites_pending.call_args.args) == (False, (3, True))


def test_created_invites_clear_the_flag(mocker):
    requests = mocker.Mock()

    sent = FeedbackInviteObserver(StubFeedback(), requests).send(make_snapshot())

    assert (sent, requests.mark_invites_pending.call_args.args) == (True, (3, False))


# Verdict rule

@pytest.mark.parametrize("verdict, action", [(Verdict.APPROVED, "close"), (Verdict.MINOR_TWEAKS, "close"),
                                             (Verdict.MAJOR_CHANGES, "reopen")])
def test_a_verdict_on_a_delivered_request_closes_or_reopens_it(verdict, action):
    assert action_for_verdict(Status.DELIVERED, verdict).action == action


@pytest.mark.parametrize("status", [Status.CLOSED, Status.IN_PRODUCTION])
def test_a_verdict_after_the_manager_moved_the_request_changes_nothing(status):
    assert action_for_verdict(status, Verdict.APPROVED) is None


# ClickUp shares the urllib calling convention

def test_clickup_call_passes_its_timeout_by_keyword():
    opener = RecordingOpener(body=b'{"url": "https://app.clickup.com/t/1"}')
    draft = TaskDraft("[AV-2026-0003] Teaser", "# AV", date(2026, 10, 20), urgent=False)

    url = ClickUpTaskTracker("token", "list", opener).create_task(draft)

    assert (url, opener.calls[0][1]) == ("https://app.clickup.com/t/1", 5)
