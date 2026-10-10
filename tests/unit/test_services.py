import io
import json
import urllib.error
from datetime import date, datetime, timezone

import pytest

from avdesk.feedback_domain.facade import Recipient
from avdesk.feedback_domain.models import Outcome, ResponseReceived
from avdesk.requests_domain.events import RequestSnapshot, StatusChanged
from avdesk.requests_domain.models import Status
from avdesk.services.admin_guard import AdminOnly, AdminRequired
from avdesk.services.seam import FeedbackInviteObserver, FeedbackOutcomeApplier
from avdesk.services.task_observer import TaskTrackerObserver
from avdesk.task_tracker import ClickUpTaskTracker, DisabledTaskTracker, TaskDraft, TaskTrackerError

DELIVERED_AT = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def make_event(to_status: Status, reviewers=("Bruno",)) -> StatusChanged:
    snapshot = RequestSnapshot(
        request_id=3, public_code="AV-2026-0003", title="Teaser", type_code="teaser", type_label="Teaser",
        diretoria="Conferências", campaign="", requester_name="Ana", requester_email="ana@gobrasa.org",
        reviewers=reviewers, needed_by=date(2026, 10, 20), for_conference=False, rush=True,
        summary_markdown="# AV-2026-0003", delivery_url="https://drive.google.com/x", delivered_at=DELIVERED_AT)
    return StatusChanged(snapshot, Status.IN_REVIEW, to_status)


# Requests -> Feedback

def test_delivery_creates_invites_for_requester_and_reviewers(mocker):
    feedback = mocker.Mock()

    FeedbackInviteObserver(feedback).on_status_changed(make_event(Status.DELIVERED))

    work, recipients = feedback.create_invites.call_args.args
    assert (work.request_id, recipients) == (3, [Recipient("Ana", True), Recipient("Bruno", False)])


def test_other_status_changes_create_no_invites(mocker):
    feedback = mocker.Mock()

    FeedbackInviteObserver(feedback).on_status_changed(make_event(Status.IN_PRODUCTION))

    feedback.create_invites.assert_not_called()


# Feedback -> Requests

@pytest.fixture
def requests_stub(mocker):
    stub = mocker.Mock()
    stub.get.return_value.status = Status.DELIVERED
    return stub


@pytest.mark.parametrize("outcome, action", [
    (Outcome.MAJOR_CHANGES, "reopen"), (Outcome.APPROVED, "close"), (Outcome.MINOR_TWEAKS, "close"),
])
def test_requester_outcome_closes_or_reopens(requests_stub, outcome, action):
    FeedbackOutcomeApplier(requests_stub).on_response(ResponseReceived(3, "AV-2026-0003", outcome, True))

    assert requests_stub.perform.call_args.args[:2] == (3, action)


def test_reviewer_outcome_never_changes_status(requests_stub):
    FeedbackOutcomeApplier(requests_stub).on_response(
        ResponseReceived(3, "AV-2026-0003", Outcome.MAJOR_CHANGES, False))

    requests_stub.perform.assert_not_called()


def test_outcome_is_ignored_when_request_was_already_moved(requests_stub):
    requests_stub.get.return_value.status = Status.CLOSED

    FeedbackOutcomeApplier(requests_stub).on_response(ResponseReceived(3, "AV-2026-0003", Outcome.APPROVED, True))

    requests_stub.perform.assert_not_called()


# Accepted -> ClickUp task

def test_acceptance_creates_a_task_and_stores_its_link(mocker):
    tracker, requests = mocker.Mock(), mocker.Mock()
    tracker.create_task.return_value = "https://app.clickup.com/t/abc"

    TaskTrackerObserver(tracker, requests).on_status_changed(make_event(Status.ACCEPTED))

    draft = tracker.create_task.call_args.args[0]
    assert (draft.name, draft.urgent) == ("[AV-2026-0003] Teaser", True)
    requests.attach_task_url.assert_called_once_with(3, "https://app.clickup.com/t/abc")


def test_no_link_is_stored_when_tracker_is_disabled(mocker):
    requests = mocker.Mock()

    TaskTrackerObserver(DisabledTaskTracker(), requests).on_status_changed(make_event(Status.ACCEPTED))

    requests.attach_task_url.assert_not_called()


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_clickup_adapter_posts_the_task_to_the_configured_list():
    sent = []

    def opener(request, timeout):
        sent.append(request)
        return FakeResponse(json.dumps({"id": "abc", "url": "https://app.clickup.com/t/abc"}).encode())

    url = ClickUpTaskTracker("pk_test", "901", opener).create_task(
        TaskDraft("Teaser", "# md", date(2026, 10, 20), urgent=True))

    body = json.loads(sent[0].data)
    assert (url, sent[0].full_url, sent[0].get_header("Authorization"), body["priority"]) == \
           ("https://app.clickup.com/t/abc", "https://api.clickup.com/api/v2/list/901/task", "pk_test", 2)


def test_clickup_network_failure_raises_a_tracker_error():
    def opener(request, timeout):
        raise urllib.error.URLError("offline")

    with pytest.raises(TaskTrackerError):
        ClickUpTaskTracker("pk_test", "901", opener).create_task(TaskDraft("x", "", date(2026, 10, 20), False))


# Protection Proxy

def test_proxy_forwards_calls_for_an_admin(mocker):
    target = mocker.Mock()

    AdminOnly(target, is_admin=lambda: True).inbox("filtro")

    target.inbox.assert_called_once_with("filtro")


def test_proxy_blocks_everyone_else_before_reaching_the_target(mocker):
    target = mocker.Mock()

    with pytest.raises(AdminRequired):
        AdminOnly(target, is_admin=lambda: False).perform(1, "accept")

    target.perform.assert_not_called()
