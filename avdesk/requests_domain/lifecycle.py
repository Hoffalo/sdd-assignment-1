"""Request lifecycle: which status changes exist and how each one runs.

ACTIONS is the single table of allowed moves; TRANSITIONS is derived from it,
so the rules can never disagree with the buttons the admin sees.

Command: every status change is an object with execute() and undo(). The
repository is the receiver that applies it (and writes the timeline row in
the same transaction), Lifecycle is the invoker that keeps the history used
by "undo last change". StatusCommandFactory is the Factory Method that turns
an action name from a form into the right command class via a factory map.
"""
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from avdesk.clock import Clock
from avdesk.requests_domain.models import Request, Status
from avdesk.requests_domain.repository import RequestWriter
from avdesk.requests_domain.validators import is_http_url

NOTE_REQUIRED = frozenset({Status.NEEDS_INFO, Status.DECLINED})
# Statuses that trigger work outside this domain (ClickUp task, feedback
# invites, closing the feedback loop); moving into or out of them cannot be
# reversed by just restoring a status here.
IRREVERSIBLE = frozenset({Status.ACCEPTED, Status.DELIVERED, Status.CLOSED})


class TransitionNotAllowed(Exception):
    pass


class MissingInput(Exception):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


class NotUndoable(Exception):
    pass


class StatusChange:
    """Base Command. Subclasses add required inputs and extra stored fields."""

    def __init__(self, receiver: RequestWriter, clock: Clock, request: Request, target: Status,
                 actor: str, note: str = "", **inputs):
        self.receiver = receiver
        self.clock = clock
        self.request = request
        self.target = target
        self.actor = actor
        self.note = note.strip()
        self.inputs = inputs

    @property
    def undoable(self) -> bool:
        return not ({self.request.status, self.target} & IRREVERSIBLE)

    def execute(self) -> None:
        self.check_inputs()
        now = self.clock.now()
        self.receiver.apply_transition(self.request.id, self.request.status, self.target,
                                       self.fields(now), self.note, self.actor, now)

    def undo(self) -> None:
        if not self.undoable:
            raise NotUndoable("Esta mudança não pode ser desfeita.")
        # Undo is a correction, not a business move, so it may go "backwards"
        # along a path the transition table does not offer (e.g. declined -> submitted).
        self.receiver.apply_transition(self.request.id, self.target, self.request.status, {},
                                       "Mudança desfeita", self.actor, self.clock.now())

    def check_inputs(self) -> None:
        if self.target in NOTE_REQUIRED and not self.note:
            raise MissingInput("note", "Escreva uma mensagem para a pessoa solicitante.")

    def fields(self, now: datetime) -> dict:
        return {}


class AcceptRequest(StatusChange):
    def check_inputs(self) -> None:
        if not self.inputs.get("analyst_id"):
            raise MissingInput("analyst_id", "Escolha quem vai produzir o vídeo.")

    def fields(self, now: datetime) -> dict:
        return {"analyst_id": int(self.inputs["analyst_id"]), "accepted_at": now}


class DeliverRequest(StatusChange):
    def check_inputs(self) -> None:
        if not is_http_url(self.inputs.get("delivery_url", "")):
            raise MissingInput("delivery_url", "Cole o link do Drive com o arquivo final.")

    def fields(self, now: datetime) -> dict:
        return {"delivery_url": self.inputs["delivery_url"].strip(), "delivered_at": now}


@dataclass(frozen=True)
class Action:
    name: str
    label: str
    command: type[StatusChange]
    sources: frozenset[Status]
    target: Status
    by_requester: bool = False


S = Status
ACTIONS: tuple[Action, ...] = (
    Action("accept", "Aceitar", AcceptRequest, frozenset({S.SUBMITTED}), S.ACCEPTED),
    Action("request_info", "Pedir mais informações", StatusChange, frozenset({S.SUBMITTED}), S.NEEDS_INFO),
    Action("resubmit", "Reenviar briefing", StatusChange, frozenset({S.NEEDS_INFO}), S.SUBMITTED, by_requester=True),
    Action("decline", "Recusar", StatusChange, frozenset({S.SUBMITTED, S.NEEDS_INFO}), S.DECLINED),
    Action("start_production", "Iniciar produção", StatusChange, frozenset({S.ACCEPTED}), S.IN_PRODUCTION),
    Action("send_to_review", "Enviar para revisão", StatusChange, frozenset({S.IN_PRODUCTION}), S.IN_REVIEW),
    Action("request_changes", "Pedir ajustes", StatusChange, frozenset({S.IN_REVIEW}), S.IN_PRODUCTION),
    Action("deliver", "Marcar como entregue", DeliverRequest, frozenset({S.IN_PRODUCTION, S.IN_REVIEW}), S.DELIVERED),
    Action("close", "Concluir", StatusChange, frozenset({S.DELIVERED}), S.CLOSED),
    Action("reopen", "Reabrir para ajustes", StatusChange, frozenset({S.DELIVERED}), S.IN_PRODUCTION),
    Action("cancel", "Cancelar", StatusChange,
           frozenset({S.SUBMITTED, S.NEEDS_INFO, S.ACCEPTED, S.IN_PRODUCTION}), S.CANCELLED),
)

TRANSITIONS: dict[Status, frozenset[Status]] = {
    status: frozenset(a.target for a in ACTIONS if status in a.sources) for status in Status
}


class StatusCommandFactory:
    def __init__(self, receiver: RequestWriter, clock: Clock):
        self._receiver = receiver
        self._clock = clock
        self._factory_map = {action.name: action for action in ACTIONS}

    def create(self, action_name: str, request: Request, actor: str, note: str = "",
               as_requester: bool = False, **inputs) -> StatusChange:
        action = self._factory_map.get(action_name)
        if action is None or request.status not in action.sources:
            raise TransitionNotAllowed(f"{action_name!r} is not allowed from {request.status}")
        if action.by_requester != as_requester:
            raise TransitionNotAllowed(f"{action_name!r} cannot be performed by this actor")
        return action.command(self._receiver, self._clock, request, action.target, actor, note, **inputs)

    def available_actions(self, status: Status) -> list[Action]:
        return [a for a in ACTIONS if status in a.sources and not a.by_requester]


class Lifecycle:
    """Command invoker with an undo history per request.

    The history lives in process memory: it is meant for "I clicked the
    wrong button" moments and is lost on restart, which is acceptable because
    every change is also in the persistent timeline.
    """

    def __init__(self):
        self._history: dict[int, list[StatusChange]] = defaultdict(list)
        self._lock = threading.Lock()

    def run(self, command: StatusChange) -> None:
        command.execute()
        with self._lock:
            self._history[command.request.id].append(command)

    def can_undo(self, request_id: int) -> bool:
        with self._lock:
            history = self._history.get(request_id)
            return bool(history) and history[-1].undoable

    def undo_last(self, request_id: int) -> StatusChange:
        with self._lock:
            history = self._history.get(request_id)
            if not history or not history[-1].undoable:
                raise NotUndoable("Não há mudança que possa ser desfeita.")
            command = history.pop()
        command.undo()
        return command
