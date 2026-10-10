"""Briefing completeness score, shown live to the requester and kept for metrics.

Kept apart from validation (SRP): validation decides whether a briefing may be
submitted, the score measures how much context it carries beyond the minimum,
so metrics can later test whether fuller briefings get better outcomes.
"""
from avdesk.requests_domain.briefing import Briefing
from avdesk.requests_domain.models import Catalog
from avdesk.requests_domain.validators import is_blank


class BriefingScorer:
    def score(self, briefing: Briefing, catalog: Catalog) -> int:
        questions = catalog.questions_for(briefing.type_code)
        if not questions:
            return 0
        answered = sum(not is_blank(briefing.answers.get(q.key)) for q in questions)
        return round(100 * answered / len(questions))
