from datetime import date

import pytest

from avdesk.requests_domain.events import RequestEventSubject, RequestObserver, RequestSnapshot, StatusChanged
from avdesk.requests_domain.models import Status


def make_event(to_status=Status.DELIVERED) -> StatusChanged:
    snapshot = RequestSnapshot(
        request_id=1, public_code="AV-2026-0001", title="Teaser", type_code="teaser", type_label="Teaser",
        diretoria="Conferências", campaign="", requester_name="Ana", requester_email="ana@gobrasa.org",
        reviewers=(), needed_by=date(2026, 12, 1), needs_c_level_approval=False, rush=False, summary_markdown="#")
    return StatusChanged(snapshot, Status.IN_REVIEW, to_status)


class Exploding(RequestObserver):
    def on_status_changed(self, event):
        raise RuntimeError("boom")


@pytest.fixture
def subject():
    return RequestEventSubject()


def test_every_attached_observer_is_notified(subject, mocker):
    first, second = mocker.Mock(spec=RequestObserver), mocker.Mock(spec=RequestObserver)
    subject.attach(first)
    subject.attach(second)
    event = make_event()

    subject.notify(event)

    first.on_status_changed.assert_called_once_with(event)
    second.on_status_changed.assert_called_once_with(event)


def test_detached_observer_is_no_longer_notified(subject, mocker):
    observer = mocker.Mock(spec=RequestObserver)
    subject.attach(observer)
    subject.detach(observer)

    subject.notify(make_event())

    observer.on_status_changed.assert_not_called()


def test_a_failing_observer_does_not_stop_the_others(subject, mocker):
    survivor = mocker.Mock(spec=RequestObserver)
    subject.attach(Exploding())
    subject.attach(survivor)

    subject.notify(make_event())

    survivor.on_status_changed.assert_called_once()
