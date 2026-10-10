from datetime import date, timezone

from avdesk.clock import SystemClock
from avdesk.tokens import SecureTokenGenerator
from tests.doubles import FixedClock


def test_system_clock_reports_utc():
    assert SystemClock().now().tzinfo == timezone.utc


def test_today_is_derived_from_now():
    assert FixedClock().today() == date(2026, 10, 9)


def test_fixed_clock_only_moves_when_advanced():
    clock = FixedClock()

    clock.advance(days=2)

    assert clock.today() == date(2026, 10, 11)


def test_secure_tokens_are_long_and_unique():
    generator = SecureTokenGenerator()

    tokens = {generator.new_token() for _ in range(100)}

    assert len(tokens) == 100 and all(len(t) >= 40 for t in tokens)
