"""Application settings, read once from environment variables.

Singleton: the whole process shares one Config so every component sees the
same settings. The slides' caveat applies here because waitress serves
requests on several threads, so creation is guarded by a lock. Tests call
reset_config() to undo the global state between cases.
"""
import hashlib
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

log = logging.getLogger(__name__)

DATABASE_FILENAME = "avdesk.sqlite3"
INSECURE_DEFAULT_PASSWORD = "avdesk-dev"


@dataclass(frozen=True)
class Config:
    port: int
    data_dir: Path
    admin_password: str
    secret_key: str
    feedback_ttl_days: int
    workload_warn_threshold: int
    approval_buffer_days: int
    clickup_api_token: str
    clickup_list_id: str
    admin_password_is_default: bool

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        password = env.get("ADMIN_PASSWORD", "")
        # Deriving the key keeps sessions working with one variable set, at the
        # cost of every session being invalidated when the password changes.
        secret_key = env.get("SECRET_KEY") or hashlib.sha256(
            f"avdesk-session:{password or INSECURE_DEFAULT_PASSWORD}".encode()
        ).hexdigest()
        return cls(
            port=int(env.get("PORT", "8000")),
            data_dir=Path(env.get("DATA_DIR", "data")),
            admin_password=password or INSECURE_DEFAULT_PASSWORD,
            secret_key=secret_key,
            feedback_ttl_days=int(env.get("FEEDBACK_TTL_DAYS", "30")),
            workload_warn_threshold=int(env.get("WORKLOAD_WARN_THRESHOLD", "3")),
            approval_buffer_days=int(env.get("C_LEVEL_APPROVAL_BUFFER_DAYS", "3")),
            clickup_api_token=env.get("CLICKUP_API_TOKEN", ""),
            clickup_list_id=env.get("CLICKUP_LIST_ID", ""),
            admin_password_is_default=not password,
        )

    @property
    def database_path(self) -> Path:
        return self.data_dir / DATABASE_FILENAME

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
                if _instance.admin_password_is_default:
                    log.warning("ADMIN_PASSWORD is not set; using the insecure default %r.",
                                INSECURE_DEFAULT_PASSWORD)
    return _instance


def reset_config() -> None:
    global _instance
    with _lock:
        _instance = None
