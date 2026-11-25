"""Persistence contracts of the feedback domain and their SQL Server adapter (ISP + Adapter)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from avdesk_feedback.database import Database, from_db_time, to_db_time
from avdesk_feedback.domain.models import (
    RATING_DIMENSIONS, DeliveredWork, FeedbackAnswer, FeedbackInvite, FeedbackResponse, Outcome, ResponseReceived,
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
    def invites_for_delivery(self, request_id: int, delivered_at: datetime) -> list[FeedbackInvite]: ...

    @abstractmethod
    def pending_verdict(self, request_id: int) -> ResponseReceived | None:
        """The requester's stored answer whose verdict has not reached the requests service yet."""

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

    @abstractmethod
    def set_verdict_pending(self, invite_id: int, pending: bool) -> None: ...


def _to_invite(row) -> FeedbackInvite:
    work = DeliveredWork(row["request_id"], row["public_code"], row["request_title"], row["type_label"],
                         row["diretoria"], row["delivery_url"], row["needed_by"], from_db_time(row["delivered_at"]))
    return FeedbackInvite(row["id"], row["token"], work, row["recipient_label"], row["is_requester"],
                          from_db_time(row["expires_at"]), from_db_time(row["used_at"]),
                          from_db_time(row["created_at"]), bool(row.get("verdict_pending")))


class SqlServerFeedbackRepository(FeedbackReader, FeedbackWriter):
    def __init__(self, database: Database):
        self._db = database

    def invite_by_token(self, token: str) -> FeedbackInvite | None:
        with self._db.connect() as session:
            row = session.execute("SELECT * FROM feedback_invites WHERE token = %s", (token,)).fetchone()
        return _to_invite(row) if row else None

    def invites_for_request(self, request_id: int) -> list[FeedbackInvite]:
        with self._db.connect() as session:
            rows = session.execute(
                "SELECT i.*, r.verdict_pending FROM feedback_invites i "
                "LEFT JOIN feedback_responses r ON r.invite_id = i.id WHERE i.request_id = %s ORDER BY i.id",
                (request_id,)).fetchall()
        return [_to_invite(r) for r in rows]

    def invites_for_delivery(self, request_id: int, delivered_at: datetime) -> list[FeedbackInvite]:
        with self._db.connect() as session:
            rows = session.execute(
                "SELECT * FROM feedback_invites WHERE request_id = %s AND delivered_at = %s ORDER BY id",
                (request_id, to_db_time(delivered_at))).fetchall()
        return [_to_invite(r) for r in rows]

    def pending_verdict(self, request_id: int) -> ResponseReceived | None:
        with self._db.connect() as session:
            row = session.execute(
                "SELECT TOP 1 i.id, i.public_code, r.outcome FROM feedback_responses r "
                "JOIN feedback_invites i ON i.id = r.invite_id "
                "WHERE i.request_id = %s AND i.is_requester = 1 AND r.verdict_pending = 1 ORDER BY r.id DESC",
                (request_id,)).fetchone()
        if row is None:
            return None
        return ResponseReceived(row["id"], request_id, row["public_code"], Outcome(row["outcome"]), True)

    def all_invites(self) -> list[FeedbackInvite]:
        with self._db.connect() as session:
            rows = session.execute("SELECT * FROM feedback_invites ORDER BY id").fetchall()
        return [_to_invite(r) for r in rows]

    def all_responses(self) -> list[FeedbackResponse]:
        with self._db.connect() as session:
            rows = session.execute(
                "SELECT r.*, i.request_id, i.is_requester FROM feedback_responses r "
                "JOIN feedback_invites i ON i.id = r.invite_id ORDER BY r.id").fetchall()
        return [FeedbackResponse(r["invite_id"], r["request_id"], r["is_requester"],
                                 FeedbackAnswer({d: r[d] for d in RATING_DIMENSIONS}, Outcome(r["outcome"]),
                                                r["comment"]),
                                 from_db_time(r["created_at"]))
                for r in rows]

    def add_invites(self, work: DeliveredWork, invites: list[NewInvite], at: datetime) -> list[FeedbackInvite]:
        with self._db.connect() as session:
            for invite in invites:
                session.execute(
                    "INSERT INTO feedback_invites (token, request_id, public_code, request_title, type_label, "
                    "diretoria, delivery_url, needed_by, delivered_at, recipient_label, is_requester, expires_at, "
                    "created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (invite.token, work.request_id, work.public_code, work.title, work.type_label, work.diretoria,
                     work.delivery_url, work.needed_by, to_db_time(work.delivered_at),
                     invite.recipient_label, invite.is_requester, to_db_time(invite.expires_at),
                     to_db_time(at)))
        return [self.invite_by_token(invite.token) for invite in invites]

    def record_response(self, invite: FeedbackInvite, answer: FeedbackAnswer, at: datetime) -> FeedbackResponse:
        with self._db.connect() as session:
            # Same guard as request transitions: a double submit matches zero rows.
            cursor = session.execute("UPDATE feedback_invites SET used_at = %s WHERE id = %s AND used_at IS NULL",
                                     (to_db_time(at), invite.id))
            if cursor.rowcount != 1:
                raise InviteAlreadyUsed()
            session.execute(
                "INSERT INTO feedback_responses (invite_id, rating_tone, rating_quality, rating_process, "
                "rating_usefulness, outcome, comment, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (invite.id, *(answer.ratings[d] for d in RATING_DIMENSIONS), str(answer.outcome), answer.comment,
                 to_db_time(at)))
        return FeedbackResponse(invite.id, invite.work.request_id, invite.is_requester, answer, at)

    def set_verdict_pending(self, invite_id: int, pending: bool) -> None:
        with self._db.connect() as session:
            session.execute("UPDATE feedback_responses SET verdict_pending = %s WHERE invite_id = %s",
                            (pending, invite_id))
