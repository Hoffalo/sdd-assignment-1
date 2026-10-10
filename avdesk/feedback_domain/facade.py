"""FeedbackFacade: the one public entry point of the feedback domain (Facade)."""
from dataclasses import dataclass
from typing import Mapping

from avdesk.clock import Clock
from avdesk.feedback_domain.events import FeedbackEventSubject
from avdesk.feedback_domain.models import (
    DeliveredWork, FeedbackInvite, FeedbackResponse, InviteState, ResponseReceived,
)
from avdesk.feedback_domain.repository import FeedbackReader, FeedbackWriter, InviteAlreadyUsed, NewInvite
from avdesk.feedback_domain.rules import invite_expiry, invite_state, parse_answer
from avdesk.tokens import TokenGenerator


@dataclass(frozen=True)
class Recipient:
    label: str
    is_requester: bool


@dataclass(frozen=True)
class SubmissionOutcome:
    state: InviteState
    errors: dict[str, str]
    response: FeedbackResponse | None = None


class FeedbackFacade:
    def __init__(self, reader: FeedbackReader, writer: FeedbackWriter, events: FeedbackEventSubject,
                 tokens: TokenGenerator, clock: Clock, ttl_days: int):
        self._reader = reader
        self._writer = writer
        self._events = events
        self._tokens = tokens
        self._clock = clock
        self._ttl_days = ttl_days

    def create_invites(self, work: DeliveredWork, recipients: list[Recipient]) -> list[FeedbackInvite]:
        now = self._clock.now()
        expires_at = invite_expiry(now, self._ttl_days)
        new_invites = [NewInvite(self._tokens.new_token(), r.label, r.is_requester, expires_at) for r in recipients]
        return self._writer.add_invites(work, new_invites, now)

    def open_invite(self, token: str) -> tuple[FeedbackInvite | None, InviteState]:
        invite = self._reader.invite_by_token(token)
        return invite, invite_state(invite, self._clock.now())

    def submit(self, token: str, form: Mapping[str, str]) -> SubmissionOutcome:
        invite, state = self.open_invite(token)
        if state != InviteState.OPEN:
            return SubmissionOutcome(state, {})
        answer, errors = parse_answer(form)
        if errors:
            return SubmissionOutcome(state, errors)
        try:
            response = self._writer.record_response(invite, answer, self._clock.now())
        except InviteAlreadyUsed:
            return SubmissionOutcome(InviteState.USED, {})
        self._events.notify(ResponseReceived(invite.work.request_id, invite.work.public_code, answer.outcome,
                                             invite.is_requester))
        return SubmissionOutcome(InviteState.USED, {}, response)

    def invites_for_request(self, request_id: int) -> list[FeedbackInvite]:
        return self._reader.invites_for_request(request_id)

    def all_invites(self) -> list[FeedbackInvite]:
        return self._reader.all_invites()

    def all_responses(self) -> list[FeedbackResponse]:
        return self._reader.all_responses()
