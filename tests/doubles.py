"""Hand-written test doubles shared across the suite."""
from datetime import datetime, timedelta, timezone

from avdesk.clock import Clock
from avdesk.tokens import TokenGenerator


class FixedClock(Clock):
    def __init__(self, at: datetime = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)):
        self._now = at

    def now(self) -> datetime:
        return self._now

    def advance(self, **delta) -> None:
        self._now += timedelta(**delta)


class SequentialTokens(TokenGenerator):
    def __init__(self, prefix: str = "token"):
        self._prefix = prefix
        self._count = 0

    def new_token(self) -> str:
        self._count += 1
        return f"{self._prefix}-{self._count}"
