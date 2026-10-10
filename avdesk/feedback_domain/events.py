"""Observer for responses leaving the feedback domain.

Mirrors requests_domain.events on purpose instead of sharing a module: each
domain owns its events so either can be lifted out without the other.
"""
import logging
from abc import ABC, abstractmethod

from avdesk.feedback_domain.models import ResponseReceived

log = logging.getLogger(__name__)


class FeedbackObserver(ABC):
    @abstractmethod
    def on_response(self, event: ResponseReceived) -> None: ...


class FeedbackEventSubject:
    def __init__(self):
        self._observers: list[FeedbackObserver] = []

    def attach(self, observer: FeedbackObserver) -> None:
        self._observers.append(observer)

    def detach(self, observer: FeedbackObserver) -> None:
        self._observers.remove(observer)

    def notify(self, event: ResponseReceived) -> None:
        for observer in list(self._observers):
            # The response is already stored; a failing listener is logged so
            # the admin can apply the outcome by hand instead of losing it.
            try:
                observer.on_response(event)
            except Exception:
                log.exception("Observer %s failed for %s", type(observer).__name__, event.public_code)
