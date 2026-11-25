"""Who is the AV manager: checks the bearer token the requests service signed.

The requests service checks the password and issues the token; this service
only verifies it, with the same ADMIN_TOKEN_SECRET, so admin pages can read
feedback data without a call across the seam. Admin routes receive
AdminOnly(facade), a Protection Proxy that checks the token before
forwarding any call, so a new admin route cannot forget it.

The same signed-token scheme authenticates the two services to each other,
with a different claim: an admin token cannot call a service endpoint and a
service token cannot open admin pages, so a leak of one never grants both.
"""
from typing import Callable

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

TOKEN_SALT = "avdesk-admin"
ADMIN_CLAIM = {"role": "av_manager"}
SERVICE_CLAIM = {"role": "avdesk_service"}


class AdminRequired(Exception):
    pass


class AdminTokens:
    def __init__(self, secret: str, ttl_seconds: int, claim: dict = ADMIN_CLAIM):
        self._serializer = URLSafeTimedSerializer(secret, salt=TOKEN_SALT)
        self.ttl_seconds = ttl_seconds
        self._claim = claim

    def issue(self) -> str:
        return self._serializer.dumps(self._claim)

    def is_valid(self, token: str | None) -> bool:
        if not token:
            return False
        try:
            return self._serializer.loads(token, max_age=self.ttl_seconds) == self._claim
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
