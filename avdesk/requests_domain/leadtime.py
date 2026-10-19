"""Lead-time rules: how much notice a request gives and whether it is rush.

Strategy: LeadTimePolicy is the family of interchangeable rules. Most
requests use StandardLeadTime; content that needs C-Level approval also needs
an approval round, so CLevelApprovalLeadTime both demands more notice and
pulls the team's working deadline earlier. Callers only see assess(), so adding a policy
never touches them (OCP).

Every calendar day counts, weekends included, because BRASA's AV team works
weekends too; holidays are not modelled either, for the same reason.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta


def days_between(start: date, end: date) -> int:
    """Days available after start, up to and including end; never negative."""
    return max((end - start).days, 0)


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
            available_days=days_between(today, needed_by),
            required_days=self.min_days,
            earliest_date=today + timedelta(days=self.min_days),
            work_deadline=needed_by,
        )


class CLevelApprovalLeadTime(LeadTimePolicy):
    def __init__(self, min_days: int, approval_buffer_days: int):
        self.min_days = min_days
        self.approval_buffer_days = approval_buffer_days

    def assess(self, today: date, needed_by: date) -> LeadTimeAssessment:
        required = self.min_days + self.approval_buffer_days
        return LeadTimeAssessment(
            available_days=days_between(today, needed_by),
            required_days=required,
            earliest_date=today + timedelta(days=required),
            work_deadline=needed_by - timedelta(days=self.approval_buffer_days),
        )


def lead_time_policy_for(min_days: int, needs_c_level_approval: bool, approval_buffer_days: int) -> LeadTimePolicy:
    if needs_c_level_approval:
        return CLevelApprovalLeadTime(min_days, approval_buffer_days)
    return StandardLeadTime(min_days)
