"""Requester's answer -> requests service, attached to the feedback domain's Observer.

The answer is already stored when this runs. If the requests service cannot
take the verdict, the response is flagged verdict_pending: the admin page
says so and offers a resend, and the requester still sees "thank you"
(ADR-8). Reviewers' answers are only for metrics and never leave this service.
"""
import logging

from avdesk_feedback.domain.events import FeedbackObserver
from avdesk_feedback.domain.facade import FeedbackFacade
from avdesk_feedback.domain.models import ResponseReceived
from avdesk_feedback.requests_client import RequestsUnavailable, RequestVerdicts

log = logging.getLogger(__name__)


class RequesterVerdictObserver(FeedbackObserver):
    def __init__(self, verdicts: RequestVerdicts, feedback: FeedbackFacade):
        self._verdicts = verdicts
        self._feedback = feedback

    def on_response(self, event: ResponseReceived) -> None:
        if not event.is_requester:
            return
        self.send(event)

    def send(self, event: ResponseReceived) -> bool:
        try:
            self._verdicts.send_verdict(event.request_id, event.outcome)
        except RequestsUnavailable as error:
            log.warning("Verdict for %s is pending: %s", event.public_code, error)
            self._feedback.mark_verdict_pending(event.invite_id, True)
            return False
        self._feedback.mark_verdict_pending(event.invite_id, False)
        return True
