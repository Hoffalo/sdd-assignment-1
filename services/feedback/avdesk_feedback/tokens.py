"""Unguessable link tokens as an injected dependency.

Adapter over the secrets module: a link token is the only thing that
authorises a requester or a feedback reviewer, so it must be
cryptographically random in production and predictable in tests.
"""
import secrets
from abc import ABC, abstractmethod

TOKEN_BYTES = 32


class TokenGenerator(ABC):
    @abstractmethod
    def new_token(self) -> str: ...


class SecureTokenGenerator(TokenGenerator):
    def new_token(self) -> str:
        return secrets.token_urlsafe(TOKEN_BYTES)
