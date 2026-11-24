"""Who is the AV manager: signed bearer tokens, and a Protection Proxy that checks them.

The UI is served from another origin, so a session cookie would need
cross-site cookie settings and CSRF protection. A bearer token sent in the
Authorization header avoids both: another site cannot make the browser
attach it. The token is signed (itsdangerous, already a Flask dependency)
with ADMIN_TOKEN_SECRET, which the feedback service shares so it can check
the same token without calling this service.

Admin routes receive AdminOnly(facade) instead of the facade itself. The
proxy has the same methods as the object it wraps but checks the token
before forwarding any call, so the rule lives in one place and a new admin
route cannot forget it.
"""
import hmac
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


def password_matches(given: str, expected: str) -> bool:
    # compare_digest takes the same time however many characters match, so
    # response timing reveals nothing about the password.
    return hmac.compare_digest(given.encode(), expected.encode())


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
