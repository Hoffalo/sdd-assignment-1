from datetime import date, datetime, timezone

import pytest

from avdesk.requests_domain.briefing import BriefingBuilder, BriefingDirector
from avdesk.requests_domain.lifecycle import (
    ACTIONS,
    TRANSITIONS,
    Lifecycle,
    MissingInput,
    NotUndoable,
    StatusCommandFactory,
    TransitionNotAllowed,
)
from avdesk.requests_domain.models import Request, Status
from tests.doubles import FixedClock

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)

ALLOWED = [
    (Status.SUBMITTED, Status.NEEDS_INFO), (Status.SUBMITTED, Status.ACCEPTED),
    (Status.SUBMITTED, Status.DECLINED), (Status.SUBMITTED, Status.CANCELLED),
    (Status.NEEDS_INFO, Status.SUBMITTED), (Status.NEEDS_INFO, Status.DECLINED),
    (Status.NEEDS_INFO, Status.CANCELLED),
    (Status.ACCEPTED, Status.IN_PRODUCTION), (Status.ACCEPTED, Status.CANCELLED),
    (Status.IN_PRODUCTION, Status.IN_REVIEW), (Status.IN_PRODUCTION, Status.DELIVERED),
    (Status.IN_PRODUCTION, Status.CANCELLED),
    (Status.IN_REVIEW, Status.IN_PRODUCTION), (Status.IN_REVIEW, Status.DELIVERED),
    (Status.DELIVERED, Status.CLOSED), (Status.DELIVERED, Status.IN_PRODUCTION),
]


def make_request(status: Status) -> Request:
    briefing = BriefingDirector(BriefingBuilder()).teaser(needed_by=date(2026, 12, 1))
    return Request(id=7, public_code="AV-2026-0007", tracking_token="t", briefing=briefing, status=status,
                   rush=False, briefing_score=80, created_at=NOW, updated_at=NOW)


@pytest.fixture
def receiver(mocker):
    return mocker.Mock()


@pytest.fixture
def factory(receiver):
    return StatusCommandFactory(receiver, FixedClock(NOW))


# The transition table

def test_transition_table_matches_the_agreed_lifecycle():
    pairs = {(source, target) for source, targets in TRANSITIONS.items() for target in targets}

    assert pairs == set(ALLOWED)


@pytest.mark.parametrize("status", [Status.CLOSED, Status.DECLINED, Status.CANCELLED])
def test_terminal_statuses_have_no_way_out(status):
    assert not TRANSITIONS.get(status)


def test_every_action_name_is_unique():
    names = [action.name for action in ACTIONS]

    assert len(names) == len(set(names))


# Factory Method

def test_factory_offers_only_actions_allowed_from_the_current_status(factory):
    names = {action.name for action in factory.available_actions(Status.ACCEPTED)}

    assert names == {"start_production", "cancel"}


def test_factory_hides_requester_actions_from_the_admin_list(factory):
    names = {action.name for action in factory.available_actions(Status.NEEDS_INFO)}

    assert "resubmit" not in names


def test_factory_rejects_unknown_actions(factory):
    with pytest.raises(TransitionNotAllowed):
        factory.create("teleport", make_request(Status.SUBMITTED), actor="admin")


def test_factory_rejects_action_from_wrong_status(factory):
    with pytest.raises(TransitionNotAllowed):
        factory.create("deliver", make_request(Status.SUBMITTED), actor="admin", delivery_url="https://drive.google.com/x")


# Commands

def test_execute_asks_the_receiver_to_apply_the_transition(factory, receiver):
    command = factory.create("start_production", make_request(Status.ACCEPTED), actor="admin")

    command.execute()

    receiver.apply_transition.assert_called_once_with(
        7, Status.ACCEPTED, Status.IN_PRODUCTION, {}, "", "admin", NOW)


@pytest.mark.parametrize("action, status", [("decline", Status.SUBMITTED), ("request_info", Status.SUBMITTED)])
def test_decline_and_request_info_require_a_note(factory, receiver, action, status):
    command = factory.create(action, make_request(status), actor="admin", note="  ")

    with pytest.raises(MissingInput):
        command.execute()


def test_accept_requires_an_analyst(factory):
    command = factory.create("accept", make_request(Status.SUBMITTED), actor="admin")

    with pytest.raises(MissingInput):
        command.execute()


def test_accept_records_analyst_and_acceptance_time(factory, receiver):
    factory.create("accept", make_request(Status.SUBMITTED), actor="admin", analyst_id=2).execute()

    fields = receiver.apply_transition.call_args.args[3]
    assert fields == {"analyst_id": 2, "accepted_at": NOW}


@pytest.mark.parametrize("url", ["", "drive.google.com/x", "ftp://x.org/a"])
def test_deliver_requires_an_http_link(factory, url):
    command = factory.create("deliver", make_request(Status.IN_PRODUCTION), actor="admin", delivery_url=url)

    with pytest.raises(MissingInput):
        command.execute()


def test_deliver_records_link_and_delivery_time(factory, receiver):
    url = "https://drive.google.com/x"
    factory.create("deliver", make_request(Status.IN_REVIEW), actor="admin", delivery_url=url).execute()

    assert receiver.apply_transition.call_args.args[3] == {"delivery_url": url, "delivered_at": NOW}


def test_undo_restores_the_previous_status(factory, receiver):
    command = factory.create("request_info", make_request(Status.SUBMITTED), actor="admin", note="Falta o roteiro")
    command.execute()

    command.undo()

    assert receiver.apply_transition.call_args.args[1:3] == (Status.NEEDS_INFO, Status.SUBMITTED)


@pytest.mark.parametrize("action, status, inputs", [
    ("accept", Status.SUBMITTED, {"analyst_id": 1}),
    ("deliver", Status.IN_REVIEW, {"delivery_url": "https://drive.google.com/x"}),
    ("close", Status.DELIVERED, {}),
    ("reopen", Status.DELIVERED, {}),
])
def test_commands_with_effects_outside_the_domain_cannot_be_undone(factory, action, status, inputs):
    command = factory.create(action, make_request(status), actor="admin", **inputs)

    assert not command.undoable


# Invoker

def test_lifecycle_undoes_the_last_command_only(factory, receiver):
    lifecycle = Lifecycle()
    first = factory.create("request_info", make_request(Status.SUBMITTED), actor="admin", note="Falta roteiro")
    lifecycle.run(first)

    lifecycle.undo_last(7)

    assert not lifecycle.can_undo(7)


def test_lifecycle_refuses_to_undo_irreversible_commands(factory):
    lifecycle = Lifecycle()
    lifecycle.run(factory.create("accept", make_request(Status.SUBMITTED), actor="admin", analyst_id=1))

    with pytest.raises(NotUndoable):
        lifecycle.undo_last(7)


def test_lifecycle_with_empty_history_cannot_undo():
    with pytest.raises(NotUndoable):
        Lifecycle().undo_last(99)
