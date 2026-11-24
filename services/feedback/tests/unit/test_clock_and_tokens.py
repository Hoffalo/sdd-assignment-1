from datetime import timezone

from avdesk_feedback.clock import SystemClock
from avdesk_feedback.tokens import SecureTokenGenerator


def test_system_clock_is_timezone_aware_utc():
    assert SystemClock().now().tzinfo == timezone.utc


def test_secure_tokens_are_long_and_unique():
    tokens = SecureTokenGenerator()

    first, second = tokens.new_token(), tokens.new_token()

    assert len(first) >= 40 and first != second
