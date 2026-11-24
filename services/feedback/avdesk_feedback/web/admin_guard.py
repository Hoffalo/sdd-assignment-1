"""Who is the AV manager: checks the bearer token the requests service signed.

The requests service checks the password and issues the token; this service
only verifies it, with the same ADMIN_TOKEN_SECRET, so admin pages can read
feedback data without a call across the seam. Admin routes receive
AdminOnly(facade), a Protection Proxy that checks the token before
forwarding any call, so a new admin route cannot forget it.
"""
from typing import Callable

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

TOKEN_SALT = "avdesk-admin"
ADMIN_CLAIM = {"role": "av_manager"}


class AdminRequired(Exception):
    pass


class AdminTokens:
    def __init__(self, secret: str, ttl_seconds: int):
        self._serializer = URLSafeTimedSerializer(secret, salt=TOKEN_SALT)
        self.ttl_seconds = ttl_seconds

    def issue(self) -> str:
        return self._serializer.dumps(ADMIN_CLAIM)

    def is_valid(self, token: str | None) -> bool:
        if not token:
            return False
        try:
            return self._serializer.loads(token, max_age=self.ttl_seconds) == ADMIN_CLAIM
        except (BadSignature, SignatureExpired):
            return False


def bearer_token(authorization_header: str | None) -> str | None:
    scheme, _, token = (authorization_header or "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


class AdminOnly:
    def __init__(self, target: object, is_admin: Callable[[], bool]):
        self._target = target
        self._is_admin = is_admin

    def __getattr__(self, name: str):
        if not self._is_admin():
            raise AdminRequired()
        return getattr(self._target, name)
