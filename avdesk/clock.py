"""Time as an injected dependency.

Adapter: business rules ask our Clock for "now" instead of calling datetime
directly, so tests can freeze time and stay repeatable (FIRST).
"""
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...

    def today(self) -> date:
        return self.now().date()


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
