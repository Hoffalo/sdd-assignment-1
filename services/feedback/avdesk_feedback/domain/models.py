"""Value objects of the feedback domain. No Flask, no SQL, nothing from requests_domain."""
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class Outcome(StrEnum):
    APPROVED = "approved"
    MINOR_TWEAKS = "minor_tweaks"
    MAJOR_CHANGES = "major_changes"

    @property
    def label(self) -> str:
        return OUTCOME_LABELS[self]


OUTCOME_LABELS = {
    Outcome.APPROVED: "Aprovado",
    Outcome.MINOR_TWEAKS: "Aprovado com pequenos ajustes",
    Outcome.MAJOR_CHANGES: "Precisa de mudanças grandes",
}

RATING_DIMENSIONS = {
    "rating_tone": "Tom e alinhamento com a marca",
    "rating_quality": "Qualidade do resultado final",
    "rating_process": "Processo e comunicação",
    "rating_usefulness": "Utilidade para o objetivo",
}


class InviteState(StrEnum):
    OPEN = "open"
    USED = "used"
    EXPIRED = "expired"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class DeliveredWork:
    """This domain's own copy of the delivered request (ADR-3): never a live reference."""
    request_id: int
    public_code: str
    title: str
    type_label: str
    diretoria: str
    delivery_url: str
    needed_by: date
    delivered_at: datetime


@dataclass(frozen=True)
class FeedbackInvite:
    id: int
    token: str
    work: DeliveredWork
    recipient_label: str
    is_requester: bool
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class FeedbackAnswer:
    ratings: dict[str, int]
    outcome: Outcome
    comment: str


@dataclass(frozen=True)
class FeedbackResponse:
    invite_id: int
    request_id: int
    is_requester: bool
    answer: FeedbackAnswer
    created_at: datetime


@dataclass(frozen=True)
class ResponseReceived:
    """Event published after a response is stored; what the requests side may learn."""
    request_id: int
    public_code: str
    outcome: Outcome
    is_requester: bool
