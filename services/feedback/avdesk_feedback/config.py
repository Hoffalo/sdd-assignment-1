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
# Where `docker compose` serves the UI; the deployed UI origin is set by the pipeline.
LOCAL_UI_ORIGIN = "http://localhost:8080"
SECRETS = ("DATABASE_URL", "ADMIN_TOKEN_SECRET")


class MissingSetting(Exception):
    """A setting with no safe default was not provided."""


@dataclass(frozen=True)
class Config:
    port: int
    database_url: DatabaseUrl
    version: str
    feedback_ttl_days: int
    admin_token_secret: str
    cors_origin: str
    requests_url: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        # Secrets have no default: running against some other database, or
        # accepting tokens signed with a known key, is worse than not starting.
        missing = [name for name in SECRETS if not env.get(name)]
        if missing:
            raise MissingSetting(f"Not set: {', '.join(missing)}")
        return cls(
            port=int(env.get("PORT", "8000")),
            database_url=DatabaseUrl.parse(env["DATABASE_URL"]),
            version=env.get("GIT_SHA") or UNKNOWN_VERSION,
            feedback_ttl_days=int(env.get("FEEDBACK_TTL_DAYS", "30")),
            admin_token_secret=env["ADMIN_TOKEN_SECRET"],
            cors_origin=env.get("CORS_ORIGIN", LOCAL_UI_ORIGIN),
            requests_url=env.get("REQUESTS_URL", ""),
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
