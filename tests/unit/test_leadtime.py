from datetime import date

import pytest

from avdesk.requests_domain.leadtime import (
    ConferenceLeadTime,
    StandardLeadTime,
    add_business_days,
    business_days_between,
    lead_time_policy_for,
    subtract_business_days,
)

FRIDAY = date(2026, 10, 9)
SATURDAY = date(2026, 10, 10)
MONDAY = date(2026, 10, 12)


@pytest.mark.parametrize("start, end, expected", [
    (FRIDAY, FRIDAY, 0),
    (FRIDAY, MONDAY, 1),
    (FRIDAY, date(2026, 10, 16), 5),
    (SATURDAY, MONDAY, 1),
    (MONDAY, FRIDAY, 0),
])
def test_business_days_between_counts_weekdays_after_start(start, end, expected):
    assert business_days_between(start, end) == expected


def test_adding_business_days_skips_the_weekend():
    assert add_business_days(FRIDAY, 1) == MONDAY


def test_adding_ten_business_days_lands_two_weeks_later():
    assert add_business_days(FRIDAY, 10) == date(2026, 10, 23)


def test_subtracting_business_days_skips_the_weekend():
    assert subtract_business_days(MONDAY, 1) == FRIDAY


def test_standard_policy_flags_rush_when_fewer_days_than_required():
    assessment = StandardLeadTime(min_days=10).assess(FRIDAY, date(2026, 10, 16))

    assert assessment.rush


def test_standard_policy_suggests_the_earliest_realistic_date():
    assessment = StandardLeadTime(min_days=10).assess(FRIDAY, date(2026, 10, 16))

    assert assessment.earliest_date == date(2026, 10, 23)


def test_standard_policy_accepts_exactly_the_minimum():
    assessment = StandardLeadTime(min_days=10).assess(FRIDAY, date(2026, 10, 23))

    assert not assessment.rush


def test_standard_policy_works_until_the_needed_by_date():
    assessment = StandardLeadTime(min_days=10).assess(FRIDAY, date(2026, 11, 6))

    assert assessment.work_deadline == date(2026, 11, 6)


def test_conference_policy_requires_extra_days_for_coo_review():
    assessment = ConferenceLeadTime(min_days=10, coo_buffer_days=3).assess(FRIDAY, date(2026, 10, 23))

    assert (assessment.rush, assessment.earliest_date) == (True, date(2026, 10, 28))


def test_conference_policy_moves_the_work_deadline_before_coo_review():
    assessment = ConferenceLeadTime(min_days=10, coo_buffer_days=3).assess(FRIDAY, date(2026, 11, 6))

    assert assessment.work_deadline == date(2026, 11, 3)


@pytest.mark.parametrize("for_conference, expected", [(False, StandardLeadTime), (True, ConferenceLeadTime)])
def test_policy_is_chosen_by_conference_flag(for_conference, expected):
    policy = lead_time_policy_for(min_days=10, for_conference=for_conference, coo_buffer_days=3)

    assert isinstance(policy, expected)
