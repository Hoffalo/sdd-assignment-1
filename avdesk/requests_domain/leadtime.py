"""Lead-time rules: how much notice a request gives and whether it is rush.

Strategy: LeadTimePolicy is the family of interchangeable rules. Most
requests use StandardLeadTime; conference content also needs a COO review
round, so ConferenceLeadTime both demands more notice and pulls the team's
working deadline earlier. Callers only see assess(), so adding a policy
never touches them (OCP).

Holidays are ignored on purpose (ADR-5 candidate): weekends are the only
non-working days, which keeps the rule explainable to requesters.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta

SATURDAY = 5


def _is_business_day(day: date) -> bool:
    return day.weekday() < SATURDAY


def business_days_between(start: date, end: date) -> int:
    """Working days available after start, up to and including end."""
    count, day = 0, start
    while day < end:
        day += timedelta(days=1)
        count += _is_business_day(day)
    return count


def add_business_days(start: date, days: int) -> date:
    day = start
    while days > 0:
        day += timedelta(days=1)
        days -= _is_business_day(day)
    return day


def subtract_business_days(end: date, days: int) -> date:
    day = end
    while days > 0:
        day -= timedelta(days=1)
        days -= _is_business_day(day)
    return day


@dataclass(frozen=True)
class LeadTimeAssessment:
    available_days: int
    required_days: int
    earliest_date: date
    work_deadline: date

    @property
    def rush(self) -> bool:
        return self.available_days < self.required_days


class LeadTimePolicy(ABC):
    @abstractmethod
    def assess(self, today: date, needed_by: date) -> LeadTimeAssessment: ...


class StandardLeadTime(LeadTimePolicy):
    def __init__(self, min_days: int):
        self.min_days = min_days

    def assess(self, today: date, needed_by: date) -> LeadTimeAssessment:
        return LeadTimeAssessment(
            available_days=business_days_between(today, needed_by),
            required_days=self.min_days,
            earliest_date=add_business_days(today, self.min_days),
            work_deadline=needed_by,
        )


class ConferenceLeadTime(LeadTimePolicy):
    def __init__(self, min_days: int, coo_buffer_days: int):
        self.min_days = min_days
        self.coo_buffer_days = coo_buffer_days

    def assess(self, today: date, needed_by: date) -> LeadTimeAssessment:
        required = self.min_days + self.coo_buffer_days
        return LeadTimeAssessment(
            available_days=business_days_between(today, needed_by),
            required_days=required,
            earliest_date=add_business_days(today, required),
            work_deadline=subtract_business_days(needed_by, self.coo_buffer_days),
        )


def lead_time_policy_for(min_days: int, for_conference: bool, coo_buffer_days: int) -> LeadTimePolicy:
    if for_conference:
        return ConferenceLeadTime(min_days, coo_buffer_days)
    return StandardLeadTime(min_days)
