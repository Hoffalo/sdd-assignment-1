"""RequestsFacade: the one public entry point of the requests domain.

Facade: web routes and cross-domain services call these methods instead of
knowing the intake, repository, lifecycle and event classes behind them.
In Assignment 2 each public method maps to an HTTP endpoint of the requests
service. It coordinates only; every rule lives in the classes it delegates to.
"""
from collections import Counter

from avdesk.clock import Clock
from avdesk.requests_domain.briefing import Briefing
from avdesk.requests_domain.events import RequestEventSubject, RequestSnapshot, StatusChanged
from avdesk.requests_domain.intake import BriefingIntake, CheckedBriefing
from avdesk.requests_domain.leadtime import LeadTimeAssessment
from avdesk.requests_domain.lifecycle import Action, Lifecycle, StatusCommandFactory, TransitionNotAllowed
from avdesk.requests_domain.models import WORKLOAD_STATUSES, Catalog, Request, RequestEvent, Status
from avdesk.requests_domain.repository import CatalogReader, RequestFilter, RequestReader, RequestWriter
from avdesk.requests_domain.summary import briefing_markdown, slack_message
from avdesk.tokens import TokenGenerator

REQUESTER = "solicitante"


class RequestNotFound(Exception):
    pass


class RequestsFacade:
    def __init__(self, catalog_reader: CatalogReader, reader: RequestReader, writer: RequestWriter,
                 intake: BriefingIntake, commands: StatusCommandFactory, lifecycle: Lifecycle,
                 events: RequestEventSubject, tokens: TokenGenerator, clock: Clock):
        self._catalog_reader = catalog_reader
        self._reader = reader
        self._writer = writer
        self._intake = intake
        self._commands = commands
        self._lifecycle = lifecycle
        self._events = events
        self._tokens = tokens
        self._clock = clock

    # Intake

    def catalog(self) -> Catalog:
        return self._catalog_reader.load()

    def assess_deadline(self, type_code: str, needed_by, for_conference: bool) -> LeadTimeAssessment | None:
        return self._intake.assess(self.catalog(), type_code, needed_by, for_conference)

    def submit(self, briefing: Briefing) -> tuple[CheckedBriefing, Request | None]:
        checked = self._intake.check(briefing, self.catalog())
        if not checked.is_valid:
            return checked, None
        request = self._writer.add(checked.briefing, self._tokens.new_token(), checked.rush, checked.score,
                                   self._clock.now())
        return checked, request

    def resubmit(self, tracking_token: str, briefing: Briefing) -> tuple[CheckedBriefing, Request]:
        request = self.by_token(tracking_token)
        if request.status != Status.NEEDS_INFO:
            raise TransitionNotAllowed("Only requests waiting for information can be edited")
        checked = self._intake.check(briefing, self.catalog())
        if checked.is_valid:
            self._writer.replace_briefing(request.id, checked.briefing, checked.rush, checked.score,
                                          self._clock.now())
            request = self.perform(request.id, "resubmit", actor=REQUESTER, as_requester=True)
        return checked, request

    # Reading

    def by_token(self, tracking_token: str) -> Request:
        return self._found(self._reader.get_by_token(tracking_token))

    def get(self, request_id: int) -> Request:
        return self._found(self._reader.get(request_id))

    def timeline(self, request_id: int) -> list[RequestEvent]:
        return self._reader.events(request_id)

    def inbox(self, request_filter: RequestFilter) -> list[Request]:
        return self._reader.find(request_filter)

    def all_requests(self) -> list[Request]:
        return self._reader.find(RequestFilter())

    def workload(self) -> Counter:
        return Counter(r.analyst_id for r in self.all_requests() if r.status in WORKLOAD_STATUSES)

    def briefing_markdown(self, request_id: int) -> str:
        return briefing_markdown(self.get(request_id), self.catalog())

    def slack_message(self, request_id: int) -> str:
        return slack_message(self.get(request_id), self.catalog())

    # Lifecycle

    def available_actions(self, request: Request) -> list[Action]:
        return self._commands.available_actions(request.status)

    def can_undo(self, request_id: int) -> bool:
        return self._lifecycle.can_undo(request_id)

    def perform(self, request_id: int, action: str, actor: str, note: str = "",
                as_requester: bool = False, **inputs) -> Request:
        request = self.get(request_id)
        command = self._commands.create(action, request, actor, note, as_requester, **inputs)
        self._lifecycle.run(command)
        return self._announce(request.status, command.target, request_id)

    def undo_last(self, request_id: int) -> Request:
        command = self._lifecycle.undo_last(request_id)
        return self._announce(command.target, command.request.status, request_id)

    def attach_task_url(self, request_id: int, url: str) -> None:
        self._writer.set_task_url(request_id, url)

    def _announce(self, from_status: Status, to_status: Status, request_id: int) -> Request:
        updated = self.get(request_id)
        self._events.notify(StatusChanged(self._snapshot(updated), from_status, to_status))
        return updated

    def _snapshot(self, request: Request) -> RequestSnapshot:
        catalog = self.catalog()
        briefing = request.briefing
        request_type = catalog.type(briefing.type_code)
        diretoria = catalog.diretoria(briefing.diretoria_id)
        return RequestSnapshot(
            request_id=request.id, public_code=request.public_code, title=briefing.title,
            type_code=briefing.type_code, type_label=request_type.label if request_type else briefing.type_code,
            diretoria=diretoria.name if diretoria else "", campaign=briefing.campaign,
            requester_name=briefing.requester_name, requester_email=briefing.requester_email,
            reviewers=briefing.reviewers, needed_by=briefing.needed_by, for_conference=briefing.for_conference,
            rush=request.rush, summary_markdown=briefing_markdown(request, catalog),
            delivery_url=request.delivery_url, delivered_at=request.delivered_at,
        )

    @staticmethod
    def _found(request: Request | None) -> Request:
        if request is None:
            raise RequestNotFound()
        return request
