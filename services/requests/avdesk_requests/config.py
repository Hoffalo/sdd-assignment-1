"""Settings of the requests service, read once from environment variables.

Singleton: the whole process shares one Config so every component sees the
same settings. The slides' caveat applies here because waitress serves
requests on several threads, so creation is guarded by a lock. Tests call
reset_config() to undo the global state between cases.

Every variable read here is listed, with its default, in system.yaml.
"""
import os
import threading
from dataclasses import dataclass
from typing import Mapping

from avdesk_requests.database import DatabaseUrl

UNKNOWN_VERSION = "dev"
# Where `docker compose` serves the UI; the deployed UI origin is set by the pipeline.
LOCAL_UI_ORIGIN = "http://localhost:8080"
# A working day of admin access per login; a stolen token stops working by the next day.
DEFAULT_TOKEN_TTL_S = 12 * 60 * 60
SECRETS = ("DATABASE_URL", "ADMIN_PASSWORD", "ADMIN_TOKEN_SECRET")


class MissingSetting(Exception):
    """A setting with no safe default was not provided."""


@dataclass(frozen=True)
class Config:
    port: int
    database_url: DatabaseUrl
    version: str
    admin_password: str
    admin_token_secret: str
    admin_token_ttl_s: int
    cors_origin: str
    workload_warn_threshold: int
    approval_buffer_days: int
    clickup_api_token: str
    clickup_list_id: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        # Secrets have no default: a service that silently ran with a known
        # password or against some other database would be worse than one
        # that refuses to start.
        missing = [name for name in SECRETS if not env.get(name)]
        if missing:
            raise MissingSetting(f"Not set: {', '.join(missing)}")
        return cls(
            port=int(env.get("PORT", "8000")),
            database_url=DatabaseUrl.parse(env["DATABASE_URL"]),
            version=env.get("GIT_SHA") or UNKNOWN_VERSION,
            admin_password=env["ADMIN_PASSWORD"],
            admin_token_secret=env["ADMIN_TOKEN_SECRET"],
            admin_token_ttl_s=int(env.get("ADMIN_TOKEN_TTL_S", str(DEFAULT_TOKEN_TTL_S))),
            cors_origin=env.get("CORS_ORIGIN", LOCAL_UI_ORIGIN),
            workload_warn_threshold=int(env.get("WORKLOAD_WARN_THRESHOLD", "3")),
            approval_buffer_days=int(env.get("C_LEVEL_APPROVAL_BUFFER_DAYS", "3")),
            clickup_api_token=env.get("CLICKUP_API_TOKEN", ""),
            clickup_list_id=env.get("CLICKUP_LIST_ID", ""),
        )

    @property
    def clickup_enabled(self) -> bool:
        return bool(self.clickup_api_token and self.clickup_list_id)


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
