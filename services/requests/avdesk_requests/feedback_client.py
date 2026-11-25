"""Requests -> Feedback over the network: the invites a delivery creates.

Adapter: HttpFeedbackInvites turns our RequestSnapshot into the feedback
service's POST /invites (services/feedback/openapi.yaml). The translation
happens here, so the feedback service never learns this domain's words:
reviewers become recipients and the request becomes delivered work.

The app must run with no feedback service configured, so without
FEEDBACK_URL the composition root uses DisabledFeedbackInvites, which
reports every call as unavailable and leaves the request flagged.
"""
import json
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Callable

from avdesk_requests.domain.events import RequestSnapshot

# The manager's delivery click waits for this call. Container Apps scales
# the feedback service to zero and a cold start takes a few seconds, so 10 s
# covers waking it without freezing the page for long; anything slower
# counts as a failure and leaves a retry button.
TIMEOUT_SECONDS = 10


class FeedbackUnavailable(Exception):
    pass


class FeedbackInvites(ABC):
    @abstractmethod
    def create_invites(self, snapshot: RequestSnapshot) -> None:
        """Asks for one invite per person; raises FeedbackUnavailable when the feedback service cannot answer."""


class DisabledFeedbackInvites(FeedbackInvites):
    def create_invites(self, snapshot: RequestSnapshot) -> None:
        raise FeedbackUnavailable("FEEDBACK_URL is not set")


def invites_body(snapshot: RequestSnapshot) -> dict[str, Any]:
    recipients = [{"label": snapshot.requester_name, "is_requester": True}]
    recipients += [{"label": name, "is_requester": False} for name in snapshot.reviewers]
    return {
        "work": {"request_id": snapshot.request_id, "public_code": snapshot.public_code, "title": snapshot.title,
                 "type_label": snapshot.type_label, "diretoria": snapshot.diretoria,
                 "delivery_url": snapshot.delivery_url, "needed_by": snapshot.needed_by.isoformat(),
                 "delivered_at": snapshot.delivered_at.isoformat()},
        "recipients": recipients,
    }


Opener = Callable[..., Any]


class HttpFeedbackInvites(FeedbackInvites):
    def __init__(self, base_url: str, service_token: Callable[[], str], opener: Opener = urllib.request.urlopen):
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._open = opener

    def create_invites(self, snapshot: RequestSnapshot) -> None:
        request = urllib.request.Request(
            f"{self._base_url}/invites",
            data=json.dumps(invites_body(snapshot)).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._service_token()}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            # By keyword: urlopen's second positional parameter is the body.
            with self._open(request, timeout=TIMEOUT_SECONDS):
                return
        # URLError (refused, DNS, any 4xx/5xx as HTTPError) and timeouts are all OSError.
        except OSError as error:
            raise FeedbackUnavailable(f"POST /invites failed: {error}") from error
