"""Turns a raw briefing into a checked one: cleaned answers, lead time, errors, score.

Pulled out of the facade (SRP) so submission and resubmission share one path
and the facade only coordinates.
"""
from dataclasses import dataclass
from datetime import date

from avdesk.clock import Clock
from avdesk.requests_domain.briefing import Briefing
from avdesk.requests_domain.leadtime import LeadTimeAssessment, lead_time_policy_for
from avdesk.requests_domain.models import Catalog
from avdesk.requests_domain.scoring import BriefingScorer
from avdesk.requests_domain.validators import BriefingValidator


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
    def __init__(self, validator: BriefingValidator, scorer: BriefingScorer, clock: Clock, coo_buffer_days: int):
        self._validator = validator
        self._scorer = scorer
        self._clock = clock
        self._coo_buffer_days = coo_buffer_days

    def assess(self, catalog: Catalog, type_code: str, needed_by: date | None,
               for_conference: bool) -> LeadTimeAssessment | None:
        request_type = catalog.type(type_code)
        today = self._clock.today()
        if request_type is None or needed_by is None or needed_by <= today:
            return None
        policy = lead_time_policy_for(request_type.min_lead_business_days, for_conference, self._coo_buffer_days)
        return policy.assess(today, needed_by)

    def check(self, briefing: Briefing, catalog: Catalog) -> CheckedBriefing:
        applicable = {q.key for q in catalog.questions_for(briefing.type_code)}
        briefing = briefing.keep_answers(applicable)
        assessment = self.assess(catalog, briefing.type_code, briefing.needed_by, briefing.for_conference)
        errors = self._validator.validate(briefing, catalog, self._clock.today(), assessment)
        return CheckedBriefing(briefing, errors, assessment, self._scorer.score(briefing, catalog))
