from datetime import date

import pytest

from avdesk.requests_domain.leadtime import (
    CLevelApprovalLeadTime,
    StandardLeadTime,
    days_between,
    lead_time_policy_for,
)

FRIDAY = date(2026, 10, 9)
SATURDAY = date(2026, 10, 10)
MONDAY = date(2026, 10, 12)


@pytest.mark.parametrize("start, end, expected", [
    (FRIDAY, FRIDAY, 0),
    (FRIDAY, MONDAY, 3),
    (FRIDAY, date(2026, 10, 16), 7),
    (SATURDAY, MONDAY, 2),
    (MONDAY, FRIDAY, 0),
])
def test_days_between_counts_every_calendar_day_including_weekends(start, end, expected):
    assert days_between(start, end) == expected


def test_standard_policy_flags_rush_when_fewer_days_than_required():
    assessment = StandardLeadTime(min_days=10).assess(FRIDAY, date(2026, 10, 16))

    assert assessment.rush


def test_standard_policy_suggests_the_earliest_realistic_date():
    assessment = StandardLeadTime(min_days=10).assess(FRIDAY, date(2026, 10, 16))

    assert assessment.earliest_date == date(2026, 10, 19)


def test_standard_policy_accepts_exactly_the_minimum():
    assessment = StandardLeadTime(min_days=10).assess(FRIDAY, date(2026, 10, 19))

    assert not assessment.rush


def test_standard_policy_works_until_the_needed_by_date():
    assessment = StandardLeadTime(min_days=10).assess(FRIDAY, date(2026, 11, 6))

    assert assessment.work_deadline == date(2026, 11, 6)


def test_c_level_policy_requires_extra_days_for_the_approval_round():
    assessment = CLevelApprovalLeadTime(min_days=10, approval_buffer_days=3).assess(FRIDAY, date(2026, 10, 19))

    assert (assessment.rush, assessment.earliest_date) == (True, date(2026, 10, 22))


def test_c_level_policy_moves_the_work_deadline_before_the_approval_round():
    assessment = CLevelApprovalLeadTime(min_days=10, approval_buffer_days=3).assess(FRIDAY, date(2026, 11, 8))

    assert assessment.work_deadline == date(2026, 11, 5)


@pytest.mark.parametrize("needs_c_level_approval, expected", [(False, StandardLeadTime), (True, CLevelApprovalLeadTime)])
def test_policy_is_chosen_by_c_level_approval_flag(needs_c_level_approval, expected):
    policy = lead_time_policy_for(min_days=10, needs_c_level_approval=needs_c_level_approval, approval_buffer_days=3)

    assert isinstance(policy, expected)
