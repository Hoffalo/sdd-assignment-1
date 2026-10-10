"""Protection Proxy for everything only the AV manager may see or do.

Admin routes receive AdminOnly(facade) instead of the facade itself. The
proxy has the same methods as the object it wraps but checks the session
before forwarding any call, so the rule lives in one place and a new admin
route cannot forget it.
"""
from typing import Callable


class AdminRequired(Exception):
    pass


class AdminOnly:
    def __init__(self, target: object, is_admin: Callable[[], bool]):
        self._target = target
        self._is_admin = is_admin

    def __getattr__(self, name: str):
        if not self._is_admin():
            raise AdminRequired()
        return getattr(self._target, name)
