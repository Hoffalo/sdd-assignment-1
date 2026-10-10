"""Status-change notifications leaving the requests domain.

Observer: the requests domain announces "request X moved to status Y" without
knowing who listens. The composition root attaches the listeners (feedback
invites on delivery, a ClickUp task on acceptance). This is the in-process,
direct-reference version from class; in Assignment 2 the same event becomes
a message on a Pub/Sub broker so the listeners can live in other services.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from avdesk.requests_domain.models import Status

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestSnapshot:
    """What other domains may know about a request: a copy, never a live reference."""
    request_id: int
    public_code: str
    title: str
    type_code: str
    type_label: str
    diretoria: str
    campaign: str
    requester_name: str
    requester_email: str
    reviewers: tuple[str, ...]
    needed_by: date
    for_conference: bool
    rush: bool
    summary_markdown: str
    delivery_url: str | None = None
    delivered_at: datetime | None = None


@dataclass(frozen=True)
class StatusChanged:
    snapshot: RequestSnapshot
    from_status: Status
    to_status: Status


class RequestObserver(ABC):
    @abstractmethod
    def on_status_changed(self, event: StatusChanged) -> None: ...


class RequestEventSubject:
    def __init__(self):
        self._observers: list[RequestObserver] = []

    def attach(self, observer: RequestObserver) -> None:
        self._observers.append(observer)

    def detach(self, observer: RequestObserver) -> None:
        self._observers.remove(observer)

    def notify(self, event: StatusChanged) -> None:
        for observer in list(self._observers):
            # The status change is already committed when observers run, so one
            # failing listener must not undo it or starve the others; the
            # failure is logged for the admin to follow up.
            try:
                observer.on_status_changed(event)
            except Exception:
                log.exception("Observer %s failed for %s", type(observer).__name__, event.snapshot.public_code)
