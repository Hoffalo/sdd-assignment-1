"""Settings of the feedback service, read once from environment variables.

Singleton guarded by a lock, as in the requests service: waitress serves
requests on several threads. Tests call reset_config() between cases.
Every variable read here is listed, with its default, in system.yaml.
"""
import os
import threading
from dataclasses import dataclass
from typing import Mapping

from avdesk_feedback.database import DatabaseUrl

UNKNOWN_VERSION = "dev"


class MissingSetting(Exception):
    """A setting with no safe default was not provided."""


@dataclass(frozen=True)
class Config:
    port: int
    database_url: DatabaseUrl
    version: str
    feedback_ttl_days: int

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        # A secret with no default: running against some other database would
        # be worse than refusing to start.
        if not env.get("DATABASE_URL"):
            raise MissingSetting("DATABASE_URL is not set")
        return cls(
            port=int(env.get("PORT", "8000")),
            database_url=DatabaseUrl.parse(env["DATABASE_URL"]),
            version=env.get("GIT_SHA") or UNKNOWN_VERSION,
            feedback_ttl_days=int(env.get("FEEDBACK_TTL_DAYS", "30")),
        )


_instance: Config | None = None
_lock = threading.Lock()


def get_config() -> Config:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = Config.from_env(os.environ)
    return _instance


def reset_config() -> None:
    global _instance
    with _lock:
        _instance = None
