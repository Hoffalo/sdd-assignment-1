"""Value objects of the requests domain. No Flask, no SQL."""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Mapping

from avdesk.requests_domain.briefing import Answer, Briefing


class Status(StrEnum):
    SUBMITTED = "submitted"
    NEEDS_INFO = "needs_info"
    ACCEPTED = "accepted"
    IN_PRODUCTION = "in_production"
    IN_REVIEW = "in_review"
    DELIVERED = "delivered"
    CLOSED = "closed"
    DECLINED = "declined"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        return STATUS_LABELS[self]


STATUS_LABELS = {
    Status.SUBMITTED: "Recebido",
    Status.NEEDS_INFO: "Aguardando informações",
    Status.ACCEPTED: "Aceito",
    Status.IN_PRODUCTION: "Em produção",
    Status.IN_REVIEW: "Em revisão",
    Status.DELIVERED: "Entregue",
    Status.CLOSED: "Concluído",
    Status.DECLINED: "Recusado",
    Status.CANCELLED: "Cancelado",
}

WORKLOAD_STATUSES = frozenset({Status.ACCEPTED, Status.IN_PRODUCTION, Status.IN_REVIEW})


@dataclass(frozen=True)
class RequestType:
    code: str
    label: str
    min_lead_business_days: int
    detail_label: str | None

    @property
    def requires_detail(self) -> bool:
        return bool(self.detail_label)


@dataclass(frozen=True)
class Question:
    key: str
    type_code: str | None
    section: str
    label: str
    kind: str
    options: tuple[str, ...]
    required: bool
    help: str = ""
    position: int = 0
    depends_on: str | None = None
    depends_value: str | None = None

    def applies_to(self, type_code: str) -> bool:
        return self.type_code is None or self.type_code == type_code

    def is_shown(self, answers: Mapping[str, Answer]) -> bool:
        """Follow-up questions appear only for the answer that makes them relevant."""
        if self.depends_on is None:
            return True
        answer = answers.get(self.depends_on)
        if isinstance(answer, tuple):
            return self.depends_value in answer
        return answer == self.depends_value


@dataclass(frozen=True)
class Diretoria:
    id: int
    name: str


@dataclass(frozen=True)
class Analyst:
    id: int
    name: str


@dataclass(frozen=True)
class Catalog:
    """Reference data that shapes the briefing form, loaded from seed.json."""
    types: tuple[RequestType, ...]
    questions: tuple[Question, ...]
    diretorias: tuple[Diretoria, ...]
    analysts: tuple[Analyst, ...]

    def type(self, code: str) -> RequestType | None:
        return next((t for t in self.types if t.code == code), None)

    def questions_for(self, type_code: str, answers: Mapping[str, Answer] | None = None) -> tuple[Question, ...]:
        """Questions of a type; with answers given, only those currently shown to the requester."""
        return tuple(q for q in self.questions
                     if q.applies_to(type_code) and (answers is None or q.is_shown(answers)))

    def diretoria(self, diretoria_id: int | None) -> Diretoria | None:
        return next((d for d in self.diretorias if d.id == diretoria_id), None)

    def analyst(self, analyst_id: int | None) -> Analyst | None:
        return next((a for a in self.analysts if a.id == analyst_id), None)


@dataclass(frozen=True)
class Request:
    id: int
    public_code: str
    tracking_token: str
    briefing: Briefing
    status: Status
    rush: bool
    briefing_score: int
    created_at: datetime
    updated_at: datetime
    analyst_id: int | None = None
    accepted_at: datetime | None = None
    review_url: str | None = None
    delivery_url: str | None = None
    delivered_at: datetime | None = None
    task_url: str | None = None


@dataclass(frozen=True)
class RequestEvent:
    request_id: int
    from_status: Status | None
    to_status: Status
    note: str
    actor: str
    created_at: datetime
