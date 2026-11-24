"""Feedback -> Requests over the network: the requester's verdict on the delivered video.

Adapter: HttpRequestVerdicts turns an outcome into the requests service's
POST /requests/{id}/verdict (services/requests/openapi.yaml). What the
verdict does to the request (close or reopen) is the requests service's
rule; this side only reports what the requester chose.

The app must run with no requests service configured, so without
REQUESTS_URL the composition root uses DisabledRequestVerdicts, which
reports every call as unavailable and leaves the verdict pending.
"""
import json
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Callable

from avdesk_feedback.domain.models import Outcome

# The requester's submit waits for this call. The requests service may be
# waking from zero replicas, so 10 s covers a cold start; anything slower
# counts as a failure and the verdict waits for a resend.
TIMEOUT_SECONDS = 10


class RequestsUnavailable(Exception):
    pass


class RequestVerdicts(ABC):
    @abstractmethod
    def send_verdict(self, request_id: int, outcome: Outcome) -> None:
        """Reports the requester's outcome; raises RequestsUnavailable when the requests service cannot answer."""


class DisabledRequestVerdicts(RequestVerdicts):
    def send_verdict(self, request_id: int, outcome: Outcome) -> None:
        raise RequestsUnavailable("REQUESTS_URL is not set")


Opener = Callable[..., Any]


class HttpRequestVerdicts(RequestVerdicts):
    def __init__(self, base_url: str, service_token: Callable[[], str], opener: Opener = urllib.request.urlopen):
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._open = opener

    def send_verdict(self, request_id: int, outcome: Outcome) -> None:
        request = urllib.request.Request(
            f"{self._base_url}/requests/{request_id}/verdict",
            data=json.dumps({"verdict": str(outcome)}).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._service_token()}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            # By keyword: urlopen's second positional parameter is the body.
            with self._open(request, timeout=TIMEOUT_SECONDS):
                return
        # URLError (refused, DNS, any 4xx/5xx as HTTPError) and timeouts are all OSError.
        except OSError as error:
            raise RequestsUnavailable(f"POST /requests/{request_id}/verdict failed: {error}") from error
