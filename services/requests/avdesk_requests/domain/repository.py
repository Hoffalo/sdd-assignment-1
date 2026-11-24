"""Persistence contracts of the requests domain and their SQL Server adapter.

Interface Segregation: readers and writers are separate contracts, so code
that only needs to read (metrics, tracking pages) cannot change data by
accident. The SqlServer classes are Adapters from pymssql to these contracts;
nothing else in the domain knows SQL exists (DIP).
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from avdesk_requests.database import Database, from_db_time, to_db_time
from avdesk_requests.domain.briefing import Briefing
from avdesk_requests.domain.models import (
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


def _decode_answers(raw: str) -> dict:
    return {k: tuple(v) if isinstance(v, list) else v for k, v in json.loads(raw).items()}


_BRIEFING_COLUMNS = ("requester_name", "requester_email", "diretoria_id", "type_code", "type_detail", "title",
                     "campaign", "needs_c_level_approval", "needed_by", "needed_by_reason", "rush_reason", "answers_json")


def _briefing_values(briefing: Briefing) -> list[Any]:
    return [briefing.requester_name.strip(), briefing.requester_email.strip().lower(), briefing.diretoria_id,
            briefing.type_code, briefing.type_detail.strip(), briefing.title.strip(), briefing.campaign.strip(),
            briefing.needs_c_level_approval, briefing.needed_by, briefing.needed_by_reason.strip(),
            briefing.rush_reason.strip(), json.dumps(dict(briefing.answers), ensure_ascii=False)]


def _to_request(row) -> Request:
    briefing = Briefing(
        requester_name=row["requester_name"], requester_email=row["requester_email"],
        diretoria_id=row["diretoria_id"], type_code=row["type_code"], type_detail=row["type_detail"],
        title=row["title"], campaign=row["campaign"], needs_c_level_approval=row["needs_c_level_approval"],
        needed_by=row["needed_by"], needed_by_reason=row["needed_by_reason"],
        rush_reason=row["rush_reason"], answers=_decode_answers(row["answers_json"]),
    )
    return Request(
        id=row["id"], public_code=row["public_code"], tracking_token=row["tracking_token"], briefing=briefing,
        status=Status(row["status"]), rush=row["rush"], briefing_score=row["briefing_score"],
        created_at=from_db_time(row["created_at"]), updated_at=from_db_time(row["updated_at"]),
        analyst_id=row["analyst_id"], accepted_at=from_db_time(row["accepted_at"]), review_url=row["review_url"],
        delivery_url=row["delivery_url"], delivered_at=from_db_time(row["delivered_at"]), task_url=row["task_url"],
    )


class SqlServerCatalogReader(CatalogReader):
    def __init__(self, database: Database):
        self._db = database

    def load(self) -> Catalog:
        with self._db.connect() as session:
            types = tuple(RequestType(r["code"], r["label"], r["min_lead_days"], r["detail_label"])
                          for r in session.execute("SELECT * FROM request_types ORDER BY position").fetchall())
            questions = tuple(
                Question(r["key"], r["type_code"], r["section"], r["label"], r["kind"],
                         tuple(json.loads(r["options_json"])), r["required"], r["help"], r["position"],
                         r["depends_on"], r["depends_value"])
                for r in session.execute("SELECT * FROM briefing_questions ORDER BY position, id").fetchall())
            diretorias = tuple(Diretoria(r["id"], r["name"])
                               for r in session.execute("SELECT * FROM diretorias ORDER BY id").fetchall())
            analysts = tuple(Analyst(r["id"], r["name"])
                             for r in session.execute("SELECT * FROM analysts ORDER BY id").fetchall())
        return Catalog(types, questions, diretorias, analysts)


class SqlServerRequestRepository(RequestReader, RequestWriter):
    def __init__(self, database: Database):
        self._db = database

    def get(self, request_id: int) -> Request | None:
        with self._db.connect() as session:
            row = session.execute("SELECT * FROM requests WHERE id = %s", (request_id,)).fetchone()
        return _to_request(row) if row else None

    def get_by_token(self, tracking_token: str) -> Request | None:
        with self._db.connect() as session:
            row = session.execute("SELECT * FROM requests WHERE tracking_token = %s", (tracking_token,)).fetchone()
        return _to_request(row) if row else None

    def find(self, request_filter: RequestFilter) -> list[Request]:
        clauses, params = [], []
        for column, value in (("status", request_filter.status), ("type_code", request_filter.type_code),
                              ("diretoria_id", request_filter.diretoria_id),
                              ("analyst_id", request_filter.analyst_id)):
            if value is not None:
                clauses.append(f"{column} = %s")
                params.append(str(value) if isinstance(value, Status) else value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._db.connect() as session:
            rows = session.execute(f"SELECT * FROM requests {where} ORDER BY needed_by, id", params).fetchall()
        return [_to_request(r) for r in rows]

    def events(self, request_id: int) -> list[RequestEvent]:
        with self._db.connect() as session:
            rows = session.execute("SELECT * FROM request_events WHERE request_id = %s ORDER BY id",
                                   (request_id,)).fetchall()
        return [RequestEvent(r["request_id"], Status(r["from_status"]) if r["from_status"] else None,
                             Status(r["to_status"]), r["note"], r["actor"], from_db_time(r["created_at"]))
                for r in rows]

    def add(self, briefing: Briefing, tracking_token: str, rush: bool, score: int, at: datetime) -> Request:
        columns = ", ".join(_BRIEFING_COLUMNS)
        placeholders = ", ".join("%s" for _ in _BRIEFING_COLUMNS)
        stored_at = to_db_time(at)
        with self._db.connect() as session:
            request_id = session.execute(
                f"INSERT INTO requests ({columns}, tracking_token, rush, briefing_score, status, created_at, "
                f"updated_at) OUTPUT INSERTED.id VALUES ({placeholders}, %s, %s, %s, %s, %s, %s)",
                [*_briefing_values(briefing), tracking_token, rush, score, str(Status.SUBMITTED), stored_at,
                 stored_at]).fetchone()["id"]
            # Derived from the row id so codes stay unique without a counter table.
            session.execute("UPDATE requests SET public_code = %s WHERE id = %s",
                            (f"AV-{at.year}-{request_id:04d}", request_id))
            session.execute("INSERT INTO request_events (request_id, from_status, to_status, note, actor, created_at) "
                            "VALUES (%s, NULL, %s, N'', N'solicitante', %s)",
                            (request_id, str(Status.SUBMITTED), stored_at))
        return self.get(request_id)

    def replace_briefing(self, request_id: int, briefing: Briefing, rush: bool, score: int, at: datetime) -> None:
        assignments = ", ".join(f"{c} = %s" for c in _BRIEFING_COLUMNS)
        with self._db.connect() as session:
            session.execute(
                f"UPDATE requests SET {assignments}, rush = %s, briefing_score = %s, updated_at = %s WHERE id = %s",
                [*_briefing_values(briefing), rush, score, to_db_time(at), request_id])

    _TRANSITION_FIELDS = frozenset({"analyst_id", "accepted_at", "review_url", "delivery_url", "delivered_at"})

    def apply_transition(self, request_id: int, expected_from: Status, to_status: Status, fields: dict,
                         note: str, actor: str, at: datetime) -> None:
        unknown = set(fields) - self._TRANSITION_FIELDS
        if unknown:
            raise ValueError(f"Cannot set {unknown} through a transition")
        values = {k: to_db_time(v) if isinstance(v, datetime) else v for k, v in fields.items()}
        assignments = "".join(f", {column} = %s" for column in values)
        with self._db.connect() as session:
            # The status guard in WHERE makes concurrent clicks safe: only the
            # first one matches, the second sees zero rows and is rejected.
            cursor = session.execute(
                f"UPDATE requests SET status = %s, updated_at = %s{assignments} WHERE id = %s AND status = %s",
                [str(to_status), to_db_time(at), *values.values(), request_id, str(expected_from)])
            if cursor.rowcount != 1:
                raise StaleTransition(f"Request {request_id} is no longer {expected_from}")
            session.execute(
                "INSERT INTO request_events (request_id, from_status, to_status, note, actor, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (request_id, str(expected_from), str(to_status), note, actor, to_db_time(at)))

    def set_task_url(self, request_id: int, url: str) -> None:
        with self._db.connect() as session:
            session.execute("UPDATE requests SET task_url = %s WHERE id = %s", (url, request_id))
