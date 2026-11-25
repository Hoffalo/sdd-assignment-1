"""Delivered request -> feedback invites, attached through the same Observer as the ClickUp task.

The delivery is already committed when this runs. If the feedback service
cannot answer, the request is flagged invites_pending: the admin page says
so and offers a retry, and nothing is lost (ADR-8). The feedback service
treats a repeated delivery as the same one, so a retry never duplicates.
"""
import logging

from avdesk_requests.domain.events import RequestObserver, RequestSnapshot, StatusChanged
from avdesk_requests.domain.facade import RequestsFacade
from avdesk_requests.domain.models import Status
from avdesk_requests.feedback_client import FeedbackInvites, FeedbackUnavailable

log = logging.getLogger(__name__)


class FeedbackInviteObserver(RequestObserver):
    def __init__(self, feedback: FeedbackInvites, requests: RequestsFacade):
        self._feedback = feedback
        self._requests = requests

    def on_status_changed(self, event: StatusChanged) -> None:
        if event.to_status != Status.DELIVERED:
            return
        self.send(event.snapshot)

    def send(self, snapshot: RequestSnapshot) -> bool:
        try:
            self._feedback.create_invites(snapshot)
        except FeedbackUnavailable as error:
            log.warning("Feedback invites for %s are pending: %s", snapshot.public_code, error)
            self._requests.mark_invites_pending(snapshot.request_id, True)
            return False
        self._requests.mark_invites_pending(snapshot.request_id, False)
        return True
