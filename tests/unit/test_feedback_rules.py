from datetime import date, datetime, timedelta, timezone

import pytest

from avdesk.feedback_domain.models import DeliveredWork, FeedbackInvite, InviteState, Outcome
from avdesk.feedback_domain.rules import invite_expiry, invite_state, parse_answer

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
VALID_FORM = {"rating_tone": "5", "rating_quality": "4", "rating_process": "3", "rating_usefulness": "5",
              "outcome": "approved", "comment": "Ficou ótimo"}


def make_invite(expires_at=NOW + timedelta(days=1), used_at=None) -> FeedbackInvite:
    work = DeliveredWork(1, "AV-2026-0001", "Teaser", "Teaser", "Conferências", "https://drive.google.com/x",
                         date(2026, 10, 20), NOW)
    return FeedbackInvite(id=1, token="t", work=work, recipient_label="Ana", is_requester=True,
                          expires_at=expires_at, used_at=used_at, created_at=NOW)


def test_complete_form_is_parsed_into_an_answer():
    answer, errors = parse_answer(VALID_FORM)

    assert (errors, answer.outcome, answer.ratings["rating_quality"]) == ({}, Outcome.APPROVED, 4)


@pytest.mark.parametrize("value", ["0", "6", "abc", "", "4.5"])
def test_rating_must_be_an_integer_from_one_to_five(value):
    _, errors = parse_answer({**VALID_FORM, "rating_tone": value})

    assert "rating_tone" in errors


def test_missing_rating_is_rejected():
    form = {k: v for k, v in VALID_FORM.items() if k != "rating_process"}

    _, errors = parse_answer(form)

    assert "rating_process" in errors


def test_outcome_must_be_one_of_the_three_options():
    _, errors = parse_answer({**VALID_FORM, "outcome": "perfect"})

    assert "outcome" in errors


def test_comment_is_optional():
    answer, errors = parse_answer({**VALID_FORM, "comment": ""})

    assert (errors, answer.comment) == ({}, "")


def test_overlong_comment_is_rejected():
    _, errors = parse_answer({**VALID_FORM, "comment": "x" * 3001})

    assert "comment" in errors


def test_invite_is_open_before_expiry():
    assert invite_state(make_invite(), NOW) == InviteState.OPEN


def test_invite_expires_exactly_at_its_expiry_time():
    assert invite_state(make_invite(expires_at=NOW), NOW) == InviteState.EXPIRED


def test_used_invite_stays_used_even_after_expiry():
    invite = make_invite(expires_at=NOW - timedelta(days=1), used_at=NOW - timedelta(days=2))

    assert invite_state(invite, NOW) == InviteState.USED


def test_missing_invite_is_reported_as_not_found():
    assert invite_state(None, NOW) == InviteState.NOT_FOUND


def test_expiry_is_ttl_days_after_creation():
    assert invite_expiry(NOW, ttl_days=30) == NOW + timedelta(days=30)
