from datetime import date, datetime, timezone

import pytest

from avdesk.composition import build_feedback_domain
from avdesk.feedback_domain.events import FeedbackObserver
from avdesk.feedback_domain.facade import Recipient
from avdesk.feedback_domain.models import DeliveredWork, InviteState, Outcome

WORK = DeliveredWork(42, "AV-2026-0042", "Teaser", "Teaser", "Conferências", "https://drive.google.com/x",
                     date(2026, 10, 20), datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc))
FORM = {"rating_tone": "5", "rating_quality": "4", "rating_process": "4", "rating_usefulness": "5",
        "outcome": "major_changes", "comment": ""}


@pytest.fixture
def domain(migrated_db, clock, tokens):
    return build_feedback_domain(migrated_db, clock, tokens, ttl_days=30)


@pytest.fixture
def facade(domain):
    return domain[0]


@pytest.fixture
def invites(facade):
    return facade.create_invites(WORK, [Recipient("Ana", True), Recipient("Bruno", False)])


def test_each_recipient_gets_an_own_token(invites):
    assert [i.token for i in invites] == ["token-1", "token-2"]


def test_invite_keeps_a_snapshot_of_the_delivered_work(facade, invites):
    invite, state = facade.open_invite("token-1")

    assert (invite.work, state) == (WORK, InviteState.OPEN)


def test_unknown_token_is_not_found(facade):
    assert facade.open_invite("nope") == (None, InviteState.NOT_FOUND)


def test_valid_response_is_stored_and_uses_the_invite(facade, invites):
    result = facade.submit("token-1", FORM)

    assert (result.response.answer.outcome, facade.open_invite("token-1")[1]) == \
           (Outcome.MAJOR_CHANGES, InviteState.USED)


def test_second_submission_with_the_same_token_is_rejected(facade, invites):
    facade.submit("token-1", FORM)

    result = facade.submit("token-1", FORM)

    assert (result.state, result.response) == (InviteState.USED, None)


def test_invalid_form_keeps_the_invite_open(facade, invites):
    result = facade.submit("token-1", {**FORM, "rating_tone": "9"})

    assert ("rating_tone" in result.errors, facade.open_invite("token-1")[1]) == (True, InviteState.OPEN)


def test_expired_invite_cannot_be_answered(facade, invites, clock):
    clock.advance(days=31)

    result = facade.submit("token-1", FORM)

    assert (result.state, facade.all_responses()) == (InviteState.EXPIRED, [])


def test_observers_learn_the_outcome_and_who_answered(domain, invites, mocker):
    facade, events = domain
    observer = mocker.Mock(spec=FeedbackObserver)
    events.attach(observer)

    facade.submit("token-2", FORM)

    event = observer.on_response.call_args.args[0]
    assert (event.request_id, event.outcome, event.is_requester) == (42, Outcome.MAJOR_CHANGES, False)


def test_responses_are_listed_with_their_request(facade, invites):
    facade.submit("token-1", FORM)

    assert [(r.request_id, r.is_requester) for r in facade.all_responses()] == [(42, True)]
