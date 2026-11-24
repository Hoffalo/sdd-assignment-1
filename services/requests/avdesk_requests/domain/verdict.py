"""What the requester's feedback verdict does to a delivered request.

The feedback service owns the verdict; this domain owns the lifecycle, so
the rule lives here and the feedback service only reports what was chosen.
Only a delivered request moves: if the AV manager already closed or
reopened it by hand, their decision wins and the verdict changes nothing.
"""
from dataclasses import dataclass
from enum import StrEnum

from avdesk_requests.domain.models import Status

FEEDBACK_ACTOR = "avaliação"


class Verdict(StrEnum):
    APPROVED = "approved"
    MINOR_TWEAKS = "minor_tweaks"
    MAJOR_CHANGES = "major_changes"


@dataclass(frozen=True)
class VerdictAction:
    action: str
    note: str


# A table, not an if-chain: a new verdict is one more row.
VERDICT_ACTIONS = {
    Verdict.APPROVED: VerdictAction("close", "Avaliação: aprovado."),
    Verdict.MINOR_TWEAKS: VerdictAction("close", "Avaliação: aprovado com pequenos ajustes."),
    Verdict.MAJOR_CHANGES: VerdictAction("reopen", "A avaliação pediu mudanças grandes."),
}


def action_for_verdict(status: Status, verdict: Verdict) -> VerdictAction | None:
    if status != Status.DELIVERED:
        return None
    return VERDICT_ACTIONS[verdict]
