"""Persistence contracts of the requests domain and their SQLite adapter.

Interface Segregation: readers and writers are separate contracts, so code
that only needs to read (metrics, tracking pages) cannot change data by
accident. The SQLite classes are Adapters from sqlite3 to these contracts;
nothing else in the domain knows SQL exists (DIP).
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from avdesk.db import Database
from avdesk.requests_domain.briefing import Briefing
from avdesk.requests_domain.models import (
    Analyst, Catalog, Diretoria, Question, Request, RequestEvent, RequestType, Status,
)


class StaleTransition(Exception):
    """The request changed status since the caller loaded it."""


@dataclass(frozen=True)
class RequestFilter:
    status: Status | None = None
    type_code: str | None = None
    diretoria_id: int | None = None
    analyst_id: int | None = None


class CatalogReader(ABC):
    @abstractmethod
    def load(self) -> Catalog: ...


class RequestReader(ABC):
    @abstractmethod
    def get(self, request_id: int) -> Request | None: ...

    @abstractmethod
    def get_by_token(self, tracking_token: str) -> Request | None: ...

    @abstractmethod
    def find(self, request_filter: RequestFilter) -> list[Request]: ...

    @abstractmethod
    def events(self, request_id: int) -> list[RequestEvent]: ...


class RequestWriter(ABC):
    @abstractmethod
    def add(self, briefing: Briefing, tracking_token: str, rush: bool, score: int, at: datetime) -> Request:
        """Stores a new request as submitted and logs the first timeline event."""

    @abstractmethod
    def replace_briefing(self, request_id: int, briefing: Briefing, rush: bool, score: int, at: datetime) -> None: ...

    @abstractmethod
    def apply_transition(self, request_id: int, expected_from: Status, to_status: Status, fields: dict,
                         note: str, actor: str, at: datetime) -> None:
        """Changes status and logs the event atomically; raises StaleTransition on a concurrent change."""

    @abstractmethod
    def set_task_url(self, request_id: int, url: str) -> None: ...


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value else None


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _decode_answers(raw: str) -> dict:
    return {k: tuple(v) if isinstance(v, list) else v for k, v in json.loads(raw).items()}


_BRIEFING_COLUMNS = ("requester_name", "requester_email", "diretoria_id", "type_code", "type_detail", "title",
                     "campaign", "for_conference", "needed_by", "needed_by_reason", "rush_reason", "answers_json")


def _briefing_values(briefing: Briefing) -> list[Any]:
    return [briefing.requester_name.strip(), briefing.requester_email.strip().lower(), briefing.diretoria_id,
            briefing.type_code, briefing.type_detail.strip(), briefing.title.strip(), briefing.campaign.strip(),
            int(briefing.for_conference), _iso(briefing.needed_by), briefing.needed_by_reason.strip(),
            briefing.rush_reason.strip(), json.dumps(dict(briefing.answers), ensure_ascii=False)]


def _to_request(row) -> Request:
    briefing = Briefing(
        requester_name=row["requester_name"], requester_email=row["requester_email"],
        diretoria_id=row["diretoria_id"], type_code=row["type_code"], type_detail=row["type_detail"],
        title=row["title"], campaign=row["campaign"], for_conference=bool(row["for_conference"]),
        needed_by=date.fromisoformat(row["needed_by"]), needed_by_reason=row["needed_by_reason"],
        rush_reason=row["rush_reason"], answers=_decode_answers(row["answers_json"]),
    )
    return Request(
        id=row["id"], public_code=row["public_code"], tracking_token=row["tracking_token"], briefing=briefing,
        status=Status(row["status"]), rush=bool(row["rush"]), briefing_score=row["briefing_score"],
        created_at=_datetime(row["created_at"]), updated_at=_datetime(row["updated_at"]),
        analyst_id=row["analyst_id"], accepted_at=_datetime(row["accepted_at"]),
        delivery_url=row["delivery_url"], delivered_at=_datetime(row["delivered_at"]), task_url=row["task_url"],
    )


class SqliteCatalogReader(CatalogReader):
    def __init__(self, database: Database):
        self._db = database

    def load(self) -> Catalog:
        with self._db.connect() as conn:
            types = tuple(RequestType(r["code"], r["label"], r["min_lead_business_days"], r["detail_label"])
                          for r in conn.execute("SELECT * FROM request_types ORDER BY position"))
            questions = tuple(
                Question(r["key"], r["type_code"], r["section"], r["label"], r["kind"],
                         tuple(json.loads(r["options_json"])), bool(r["required"]), r["help"], r["position"])
                for r in conn.execute("SELECT * FROM briefing_questions ORDER BY position, rowid"))
            diretorias = tuple(Diretoria(r["id"], r["name"]) for r in conn.execute("SELECT * FROM diretorias ORDER BY id"))
            analysts = tuple(Analyst(r["id"], r["name"]) for r in conn.execute("SELECT * FROM analysts ORDER BY id"))
        return Catalog(types, questions, diretorias, analysts)


class SqliteRequestRepository(RequestReader, RequestWriter):
    def __init__(self, database: Database):
        self._db = database

    def get(self, request_id: int) -> Request | None:
        with self._db.connect() as conn:
            row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
        return _to_request(row) if row else None

    def get_by_token(self, tracking_token: str) -> Request | None:
        with self._db.connect() as conn:
            row = conn.execute("SELECT * FROM requests WHERE tracking_token = ?", (tracking_token,)).fetchone()
        return _to_request(row) if row else None

    def find(self, request_filter: RequestFilter) -> list[Request]:
        clauses, params = [], []
        for column, value in (("status", request_filter.status), ("type_code", request_filter.type_code),
                              ("diretoria_id", request_filter.diretoria_id),
                              ("analyst_id", request_filter.analyst_id)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(str(value) if isinstance(value, Status) else value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._db.connect() as conn:
            rows = conn.execute(f"SELECT * FROM requests {where} ORDER BY needed_by, id", params).fetchall()
        return [_to_request(r) for r in rows]

    def events(self, request_id: int) -> list[RequestEvent]:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT * FROM request_events WHERE request_id = ? ORDER BY id",
                                (request_id,)).fetchall()
        return [RequestEvent(r["request_id"], Status(r["from_status"]) if r["from_status"] else None,
                             Status(r["to_status"]), r["note"], r["actor"], _datetime(r["created_at"]))
                for r in rows]

    def add(self, briefing: Briefing, tracking_token: str, rush: bool, score: int, at: datetime) -> Request:
        columns = ", ".join(_BRIEFING_COLUMNS)
        placeholders = ", ".join("?" for _ in _BRIEFING_COLUMNS)
        with self._db.connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO requests ({columns}, tracking_token, rush, briefing_score, status, created_at, "
                f"updated_at) VALUES ({placeholders}, ?, ?, ?, ?, ?, ?)",
                [*_briefing_values(briefing), tracking_token, int(rush), score, Status.SUBMITTED, _iso(at), _iso(at)])
            request_id = cursor.lastrowid
            # Derived from the row id so codes stay unique without a counter table.
            conn.execute("UPDATE requests SET public_code = ? WHERE id = ?",
                         (f"AV-{at.year}-{request_id:04d}", request_id))
            conn.execute("INSERT INTO request_events (request_id, from_status, to_status, note, actor, created_at) "
                         "VALUES (?, NULL, ?, '', 'solicitante', ?)", (request_id, Status.SUBMITTED, _iso(at)))
        return self.get(request_id)

    def replace_briefing(self, request_id: int, briefing: Briefing, rush: bool, score: int, at: datetime) -> None:
        assignments = ", ".join(f"{c} = ?" for c in _BRIEFING_COLUMNS)
        with self._db.connect() as conn:
            conn.execute(f"UPDATE requests SET {assignments}, rush = ?, briefing_score = ?, updated_at = ? WHERE id = ?",
                         [*_briefing_values(briefing), int(rush), score, _iso(at), request_id])

    _TRANSITION_FIELDS = frozenset({"analyst_id", "accepted_at", "delivery_url", "delivered_at"})

    def apply_transition(self, request_id: int, expected_from: Status, to_status: Status, fields: dict,
                         note: str, actor: str, at: datetime) -> None:
        unknown = set(fields) - self._TRANSITION_FIELDS
        if unknown:
            raise ValueError(f"Cannot set {unknown} through a transition")
        values = {k: _iso(v) if isinstance(v, datetime) else v for k, v in fields.items()}
        assignments = "".join(f", {column} = ?" for column in values)
        with self._db.connect() as conn:
            # The status guard in WHERE makes concurrent clicks safe: only the
            # first one matches, the second sees zero rows and is rejected.
            cursor = conn.execute(
                f"UPDATE requests SET status = ?, updated_at = ?{assignments} WHERE id = ? AND status = ?",
                [to_status, _iso(at), *values.values(), request_id, expected_from])
            if cursor.rowcount != 1:
                raise StaleTransition(f"Request {request_id} is no longer {expected_from}")
            conn.execute("INSERT INTO request_events (request_id, from_status, to_status, note, actor, created_at) "
                         "VALUES (?, ?, ?, ?, ?, ?)", (request_id, expected_from, to_status, note, actor, _iso(at)))

    def set_task_url(self, request_id: int, url: str) -> None:
        with self._db.connect() as conn:
            conn.execute("UPDATE requests SET task_url = ? WHERE id = ?", (url, request_id))
