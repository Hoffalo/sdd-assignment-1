"""Composition root: the only module that chooses concrete classes.

Everything else receives its collaborators through constructors and depends
on abstractions (DIP), so swapping SQLite, the clock or the task tracker
happens here and nowhere else. This is also where observers are attached,
which is what connects the two domains without either importing the other.
"""
from dataclasses import dataclass

from flask import Flask

from avdesk.clock import Clock, SystemClock
from avdesk.config import Config
from avdesk.db import Database, create_schema, load_reference_data, load_seed
from avdesk.feedback_domain.events import FeedbackEventSubject
from avdesk.feedback_domain.facade import FeedbackFacade
from avdesk.feedback_domain.repository import SqliteFeedbackRepository
from avdesk.requests_domain.events import RequestEventSubject
from avdesk.requests_domain.facade import RequestsFacade
from avdesk.requests_domain.intake import BriefingIntake, BriefingScorer
from avdesk.requests_domain.lifecycle import Lifecycle, StatusCommandFactory
from avdesk.requests_domain.repository import SqliteCatalogReader, SqliteRequestRepository
from avdesk.requests_domain.validators import BriefingValidator
from avdesk.services.metrics import MetricsService
from avdesk.services.seam import FeedbackInviteObserver, FeedbackOutcomeApplier
from avdesk.services.task_observer import TaskTrackerObserver
from avdesk.task_tracker import ClickUpTaskTracker, DisabledTaskTracker, TaskTracker
from avdesk.tokens import SecureTokenGenerator, TokenGenerator
from avdesk.web import admin, feedback, public, security


@dataclass(frozen=True)
class AppServices:
    requests: RequestsFacade
    feedback: FeedbackFacade
    metrics: MetricsService
    config: Config


def build_requests_domain(database: Database, clock: Clock, tokens: TokenGenerator,
                          coo_buffer_days: int) -> tuple[RequestsFacade, RequestEventSubject]:
    repository = SqliteRequestRepository(database)
    events = RequestEventSubject()
    facade = RequestsFacade(
        catalog_reader=SqliteCatalogReader(database),
        reader=repository,
        writer=repository,
        intake=BriefingIntake(BriefingValidator(), BriefingScorer(), clock, coo_buffer_days),
        commands=StatusCommandFactory(repository, clock),
        lifecycle=Lifecycle(),
        events=events,
        tokens=tokens,
        clock=clock,
    )
    return facade, events


def build_feedback_domain(database: Database, clock: Clock, tokens: TokenGenerator,
                          ttl_days: int) -> tuple[FeedbackFacade, FeedbackEventSubject]:
    repository = SqliteFeedbackRepository(database)
    events = FeedbackEventSubject()
    facade = FeedbackFacade(reader=repository, writer=repository, events=events, tokens=tokens, clock=clock,
                            ttl_days=ttl_days)
    return facade, events


def build_task_tracker(config: Config) -> TaskTracker:
    if config.clickup_enabled:
        return ClickUpTaskTracker(config.clickup_api_token, config.clickup_list_id)
    return DisabledTaskTracker()


def build_services(config: Config, database: Database, clock: Clock, tokens: TokenGenerator,
                   tracker: TaskTracker) -> AppServices:
    requests, request_events = build_requests_domain(database, clock, tokens, config.coo_review_buffer_days)
    feedback, feedback_events = build_feedback_domain(database, clock, tokens, config.feedback_ttl_days)

    request_events.attach(FeedbackInviteObserver(feedback))
    request_events.attach(TaskTrackerObserver(tracker, requests))
    feedback_events.attach(FeedbackOutcomeApplier(requests))

    return AppServices(requests, feedback, MetricsService(requests, feedback), config)


def create_app(config: Config, clock: Clock | None = None, tokens: TokenGenerator | None = None,
               tracker: TaskTracker | None = None) -> Flask:
    database = Database(config.database_path)
    create_schema(database)
    load_reference_data(database, load_seed())

    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
    app.secret_key = config.secret_key
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
    app.extensions["avdesk"] = build_services(config, database, clock or SystemClock(),
                                              tokens or SecureTokenGenerator(), tracker or build_task_tracker(config))

    security.install(app)
    app.register_blueprint(public.blueprint)
    app.register_blueprint(feedback.blueprint)
    app.register_blueprint(admin.blueprint)
    return app
