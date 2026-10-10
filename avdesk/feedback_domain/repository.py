"""Persistence contracts of the feedback domain and their SQLite adapter (ISP + Adapter)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from avdesk.db import Database
from avdesk.feedback_domain.models import (
    RATING_DIMENSIONS, DeliveredWork, FeedbackAnswer, FeedbackInvite, FeedbackResponse, Outcome,
)


class InviteAlreadyUsed(Exception):
    pass


@dataclass(frozen=True)
class NewInvite:
    token: str
    recipient_label: str
    is_requester: bool
    expires_at: datetime


class FeedbackReader(ABC):
    @abstractmethod
    def invite_by_token(self, token: str) -> FeedbackInvite | None: ...

    @abstractmethod
    def invites_for_request(self, request_id: int) -> list[FeedbackInvite]: ...

    @abstractmethod
    def all_invites(self) -> list[FeedbackInvite]: ...

    @abstractmethod
    def all_responses(self) -> list[FeedbackResponse]: ...


class FeedbackWriter(ABC):
    @abstractmethod
    def add_invites(self, work: DeliveredWork, invites: list[NewInvite], at: datetime) -> list[FeedbackInvite]: ...

    @abstractmethod
    def record_response(self, invite: FeedbackInvite, answer: FeedbackAnswer, at: datetime) -> FeedbackResponse:
        """Marks the invite used and stores the answer atomically; raises InviteAlreadyUsed on a second use."""


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _to_invite(row) -> FeedbackInvite:
    work = DeliveredWork(row["request_id"], row["public_code"], row["request_title"], row["type_label"],
                         row["diretoria"], row["delivery_url"], date.fromisoformat(row["needed_by"]),
                         _datetime(row["delivered_at"]))
    return FeedbackInvite(row["id"], row["token"], work, row["recipient_label"], bool(row["is_requester"]),
                          _datetime(row["expires_at"]), _datetime(row["used_at"]), _datetime(row["created_at"]))


class SqliteFeedbackRepository(FeedbackReader, FeedbackWriter):
    def __init__(self, database: Database):
        self._db = database

    def invite_by_token(self, token: str) -> FeedbackInvite | None:
        with self._db.connect() as conn:
            row = conn.execute("SELECT * FROM feedback_invites WHERE token = ?", (token,)).fetchone()
        return _to_invite(row) if row else None

    def invites_for_request(self, request_id: int) -> list[FeedbackInvite]:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT * FROM feedback_invites WHERE request_id = ? ORDER BY id",
                                (request_id,)).fetchall()
        return [_to_invite(r) for r in rows]

    def all_invites(self) -> list[FeedbackInvite]:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT * FROM feedback_invites ORDER BY id").fetchall()
        return [_to_invite(r) for r in rows]

    def all_responses(self) -> list[FeedbackResponse]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT r.*, i.request_id, i.is_requester FROM feedback_responses r "
                "JOIN feedback_invites i ON i.id = r.invite_id ORDER BY r.id").fetchall()
        return [FeedbackResponse(r["invite_id"], r["request_id"], bool(r["is_requester"]),
                                 FeedbackAnswer({d: r[d] for d in RATING_DIMENSIONS}, Outcome(r["outcome"]),
                                                r["comment"]),
                                 _datetime(r["created_at"]))
                for r in rows]

    def add_invites(self, work: DeliveredWork, invites: list[NewInvite], at: datetime) -> list[FeedbackInvite]:
        with self._db.connect() as conn:
            for invite in invites:
                conn.execute(
                    "INSERT INTO feedback_invites (token, request_id, public_code, request_title, type_label, "
                    "diretoria, delivery_url, needed_by, delivered_at, recipient_label, is_requester, expires_at, "
                    "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (invite.token, work.request_id, work.public_code, work.title, work.type_label, work.diretoria,
                     work.delivery_url, work.needed_by.isoformat(), work.delivered_at.isoformat(),
                     invite.recipient_label, int(invite.is_requester), invite.expires_at.isoformat(),
                     at.isoformat()))
        return [self.invite_by_token(invite.token) for invite in invites]

    def record_response(self, invite: FeedbackInvite, answer: FeedbackAnswer, at: datetime) -> FeedbackResponse:
        with self._db.connect() as conn:
            # Same guard as request transitions: a double submit matches zero rows.
            cursor = conn.execute("UPDATE feedback_invites SET used_at = ? WHERE id = ? AND used_at IS NULL",
                                  (at.isoformat(), invite.id))
            if cursor.rowcount != 1:
                raise InviteAlreadyUsed()
            conn.execute(
                "INSERT INTO feedback_responses (invite_id, rating_tone, rating_quality, rating_process, "
                "rating_usefulness, outcome, comment, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (invite.id, *(answer.ratings[d] for d in RATING_DIMENSIONS), answer.outcome, answer.comment,
                 at.isoformat()))
        return FeedbackResponse(invite.id, invite.work.request_id, invite.is_requester, answer, at)
