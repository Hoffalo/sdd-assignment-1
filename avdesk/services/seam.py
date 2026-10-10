"""Everything that crosses the seam between the two domains, in one file.

These two observers are the only code that knows both facades. Each
translates one domain's event into the other domain's vocabulary, so neither
domain imports the other (ADR-2). In Assignment 2 each becomes a subscriber
to a Pub/Sub topic and its facade call becomes an HTTP call.
"""
from avdesk.feedback_domain.events import FeedbackObserver
from avdesk.feedback_domain.facade import FeedbackFacade, Recipient
from avdesk.feedback_domain.models import DeliveredWork, Outcome, ResponseReceived
from avdesk.requests_domain.events import RequestObserver, StatusChanged
from avdesk.requests_domain.facade import RequestsFacade
from avdesk.requests_domain.models import Status

FEEDBACK_ACTOR = "avaliação"


class FeedbackInviteObserver(RequestObserver):
    """Requests -> Feedback: a delivered request gets feedback invites."""

    def __init__(self, feedback: FeedbackFacade):
        self._feedback = feedback

    def on_status_changed(self, event: StatusChanged) -> None:
        if event.to_status != Status.DELIVERED:
            return
        snapshot = event.snapshot
        work = DeliveredWork(snapshot.request_id, snapshot.public_code, snapshot.title, snapshot.type_label,
                             snapshot.diretoria, snapshot.delivery_url, snapshot.needed_by, snapshot.delivered_at)
        recipients = [Recipient(snapshot.requester_name, is_requester=True)]
        recipients += [Recipient(name, is_requester=False) for name in snapshot.reviewers]
        self._feedback.create_invites(work, recipients)


class FeedbackOutcomeApplier(FeedbackObserver):
    """Feedback -> Requests: only the requester's verdict closes or reopens the request."""

    def __init__(self, requests: RequestsFacade):
        self._requests = requests

    def on_response(self, event: ResponseReceived) -> None:
        if not event.is_requester:
            return
        # The admin may already have closed or reopened it by hand.
        if self._requests.get(event.request_id).status != Status.DELIVERED:
            return
        if event.outcome == Outcome.MAJOR_CHANGES:
            self._requests.perform(event.request_id, "reopen", actor=FEEDBACK_ACTOR,
                                   note="A avaliação pediu mudanças grandes.")
        else:
            self._requests.perform(event.request_id, "close", actor=FEEDBACK_ACTOR,
                                   note=f"Avaliação: {event.outcome.label.lower()}.")
