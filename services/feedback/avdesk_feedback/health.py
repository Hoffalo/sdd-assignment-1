"""Whether this service can use its own database, for GET /health.

Health reports only this service's own state: a feedback outage must not make
the feedback service look broken, or the platform would restart a healthy
container. The probe is an interface so the web layer can be tested without
a database.
"""
import logging
from abc import ABC, abstractmethod

from avdesk_feedback.database import Database

log = logging.getLogger(__name__)


class HealthProbe(ABC):
    @abstractmethod
    def database_is_healthy(self) -> bool: ...


class DatabaseHealthProbe(HealthProbe):
    """Writes and reads back the single health_probe row (migration 002).

    Give it a Database with a single-attempt retry policy: a health check must
    answer within seconds, and the caller (the deploy check, the UI) decides
    whether to ask again while a paused database resumes.
    """

    def __init__(self, database: Database):
        self._db = database

    def database_is_healthy(self) -> bool:
        try:
            with self._db.connect() as session:
                updated = session.execute("UPDATE health_probe SET checked_at = SYSUTCDATETIME() WHERE id = 1")
                if updated.rowcount != 1:
                    return False
                return session.execute("SELECT checked_at FROM health_probe WHERE id = 1").fetchone() is not None
        except Exception:
            # Any failure is an unhealthy answer, never a crash of /health;
            # the log keeps the reason.
            log.exception("Health probe could not use the database")
            return False
