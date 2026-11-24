"""SQL Server access for the requests service: connection string, retries, units of work.

Adapter over pymssql, chosen because it installs from a wheel with no system
ODBC driver, which keeps the image slim (ADR-7). Nothing outside the
repositories, the migration runner and seeding touches SQL.
"""
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Sequence
from urllib.parse import unquote, urlsplit

import pymssql

log = logging.getLogger(__name__)

URL_SCHEME = "mssql"
SQL_SERVER_PORT = 1433
# A login that cannot complete in 10 s will not complete at all; failing fast
# lets the retry policy decide whether to try again.
LOGIN_TIMEOUT_S = 10
QUERY_TIMEOUT_S = 30
# pymssql reports a paused serverless database (40613), a refused socket and a
# login timeout all as OperationalError, so these are the errors worth waiting out.
TRANSIENT_ERRORS = (pymssql.OperationalError, pymssql.InterfaceError)


class DatabaseUnavailable(Exception):
    """The database did not accept a connection within the retry budget."""


@dataclass(frozen=True)
class DatabaseUrl:
    """DATABASE_URL as a value: mssql://user:password@host:port/database."""

    host: str
    port: int
    user: str
    password: str
    database: str

    @classmethod
    def parse(cls, raw: str) -> "DatabaseUrl":
        parts = urlsplit(raw)
        name = parts.path.lstrip("/")
        if parts.scheme != URL_SCHEME or not (parts.hostname and parts.username and parts.password and name):
            raise ValueError("DATABASE_URL must look like mssql://user:password@host:port/database")
        return cls(parts.hostname, parts.port or SQL_SERVER_PORT, unquote(parts.username),
                   unquote(parts.password), unquote(name))

    def with_database(self, name: str) -> "DatabaseUrl":
        return replace(self, database=name)

    def __repr__(self) -> str:
        # Connection strings end up in logs and tracebacks; the password must not.
        return f"DatabaseUrl({self.user}@{self.host}:{self.port}/{self.database})"


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff, capped. The defaults wait about 70 s in total,
    longer than the minute a paused Azure SQL serverless database needs to resume."""

    attempts: int = 8
    first_delay_s: float = 1
    max_delay_s: float = 15

    def delays(self) -> list[float]:
        return [min(self.first_delay_s * 2 ** i, self.max_delay_s) for i in range(self.attempts - 1)]


class Session:
    """One open connection inside a unit of work, returning rows as dicts."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql: str, params: Sequence[Any] = ()):
        cursor = self._connection.cursor(as_dict=True)
        # None, not an empty tuple: pymssql only expands %s placeholders when
        # parameters are given, so a literal % in parameterless SQL stays literal.
        cursor.execute(sql, tuple(params) if params else None)
        return cursor


class Database:
    """Hands out one connection per unit of work.

    Deliberately not a Singleton: waitress serves requests on several threads
    and a pymssql connection must not be shared between them.
    """

    def __init__(self, url: DatabaseUrl, connect: Callable[..., Any] = pymssql.connect,
                 retry: RetryPolicy = RetryPolicy(), sleep: Callable[[float], None] = time.sleep,
                 autocommit: bool = False):
        self.url = url
        self._connect = connect
        self._retry = retry
        self._sleep = sleep
        self._autocommit = autocommit

    def with_retry(self, retry: RetryPolicy) -> "Database":
        return Database(self.url, self._connect, retry, self._sleep, self._autocommit)

    def _open(self):
        delays = self._retry.delays()
        for attempt in range(self._retry.attempts):
            try:
                return self._connect(server=self.url.host, port=self.url.port, user=self.url.user,
                                     password=self.url.password, database=self.url.database,
                                     login_timeout=LOGIN_TIMEOUT_S, timeout=QUERY_TIMEOUT_S,
                                     autocommit=self._autocommit)
            except TRANSIENT_ERRORS as error:
                if attempt == len(delays):
                    raise DatabaseUnavailable(f"{self.url!r} did not answer after {self._retry.attempts} attempts") \
                        from error
                log.warning("Database %r not reachable (attempt %d/%d), retrying in %ss: %s",
                            self.url, attempt + 1, self._retry.attempts, delays[attempt], error)
                self._sleep(delays[attempt])
        raise DatabaseUnavailable(f"{self.url!r}: retry policy allows no attempts")

    @contextmanager
    def connect(self) -> Iterator[Session]:
        connection = self._open()
        try:
            yield Session(connection)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()


# Every timestamp is stored as UTC in a DATETIME2 column, which has no offset,
# so the offset is dropped on the way in and restored on the way out. One
# rule in one place keeps every timestamp comparable whatever zone wrote it.

def to_db_time(value: datetime | None) -> datetime | None:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value else None


def from_db_time(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value else None
