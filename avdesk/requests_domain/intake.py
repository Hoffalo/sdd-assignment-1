"""Turns a raw briefing into a checked one: cleaned answers, lead time, errors, score.

Pulled out of the facade (SRP) so submission and resubmission share one path
and the facade only coordinates.
"""
from dataclasses import dataclass, replace
from datetime import date

from avdesk.clock import Clock
from avdesk.requests_domain.briefing import Briefing
from avdesk.requests_domain.leadtime import LeadTimeAssessment, lead_time_policy_for
from avdesk.requests_domain.models import Catalog
from avdesk.requests_domain.validators import BriefingValidator, is_blank


class BriefingScorer:
    """Completeness score, shown live to the requester and kept for metrics.

    Separate from validation (SRP): validation decides whether a briefing may
    be submitted, the score measures how much context it carries beyond the
    minimum, so metrics can test whether fuller briefings get better outcomes.
    """

    def score(self, briefing: Briefing, catalog: Catalog) -> int:
        questions = catalog.questions_for(briefing.type_code, briefing.answers)
        if not questions:
            return 0
        answered = sum(not is_blank(briefing.answers.get(q.key)) for q in questions)
        return round(100 * answered / len(questions))


@dataclass(frozen=True)
class CheckedBriefing:
    briefing: Briefing
    errors: dict[str, str]
    assessment: LeadTimeAssessment | None
    score: int

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def rush(self) -> bool:
        return bool(self.assessment and self.assessment.rush)


class BriefingIntake:
    def __init__(self, validator: BriefingValidator, scorer: BriefingScorer, clock: Clock, approval_buffer_days: int):
        self._validator = validator
        self._scorer = scorer
        self._clock = clock
        self._approval_buffer_days = approval_buffer_days

    def assess(self, catalog: Catalog, type_code: str, needed_by: date | None,
               needs_c_level_approval: bool) -> LeadTimeAssessment | None:
        request_type = catalog.type(type_code)
        today = self._clock.today()
        if request_type is None or needed_by is None or needed_by <= today:
            return None
        policy = lead_time_policy_for(request_type.min_lead_days, needs_c_level_approval, self._approval_buffer_days)
        return policy.assess(today, needed_by)

    def check(self, briefing: Briefing, catalog: Catalog) -> CheckedBriefing:
        shown = {q.key for q in catalog.questions_for(briefing.type_code, briefing.answers)}
        briefing = briefing.keep_answers(shown)
        assessment = self.assess(catalog, briefing.type_code, briefing.needed_by, briefing.needs_c_level_approval)
        if not (assessment and assessment.rush):
            # The reason box is only shown for a short deadline; a leftover
            # answer would mislabel a normal request in the briefing and ClickUp.
            briefing = replace(briefing, rush_reason="")
        errors = self._validator.validate(briefing, catalog, self._clock.today(), assessment)
        return CheckedBriefing(briefing, errors, assessment, self._scorer.score(briefing, catalog))
