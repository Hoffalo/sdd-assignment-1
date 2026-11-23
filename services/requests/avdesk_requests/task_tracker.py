"""Where accepted requests become tasks for the AV team.

Adapter: ClickUpTaskTracker translates our TaskTracker contract into
ClickUp's REST API using only the standard library. The app must run with no
external service configured (assignment §7.6), so without credentials the
composition root uses DisabledTaskTracker, which does nothing.

The ClickUp field mapping (priority, tags, assignee) is a first draft
[A CONFIRMAR] until the real list is set up.
"""
import json
import logging
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Callable

log = logging.getLogger(__name__)

CLICKUP_API = "https://api.clickup.com/api/v2"
# No background workers are allowed (§1c), so the call happens inside the
# admin's request; a short timeout keeps a slow ClickUp from freezing the page.
TIMEOUT_SECONDS = 5
PRIORITY_HIGH, PRIORITY_NORMAL = 2, 3


class TaskTrackerError(Exception):
    pass


@dataclass(frozen=True)
class TaskDraft:
    name: str
    markdown: str
    due_date: date
    urgent: bool


class TaskTracker(ABC):
    @abstractmethod
    def create_task(self, draft: TaskDraft) -> str | None:
        """Creates the task and returns its URL, or None when no tracker is configured."""


class DisabledTaskTracker(TaskTracker):
    def create_task(self, draft: TaskDraft) -> str | None:
        log.info("ClickUp is not configured; no task created for %r.", draft.name)
        return None


Opener = Callable[[urllib.request.Request, float], object]


class ClickUpTaskTracker(TaskTracker):
    def __init__(self, api_token: str, list_id: str, opener: Opener = urllib.request.urlopen):
        self._api_token = api_token
        self._list_id = list_id
        self._open = opener

    def create_task(self, draft: TaskDraft) -> str | None:
        due = datetime.combine(draft.due_date, time(12, 0), tzinfo=timezone.utc)
        body = {
            "name": draft.name,
            "markdown_content": draft.markdown,
            "due_date": int(due.timestamp() * 1000),
            "priority": PRIORITY_HIGH if draft.urgent else PRIORITY_NORMAL,
        }
        request = urllib.request.Request(
            f"{CLICKUP_API}/list/{self._list_id}/task",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": self._api_token, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._open(request, TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise TaskTrackerError(f"ClickUp task creation failed: {error}") from error
        return payload.get("url")
