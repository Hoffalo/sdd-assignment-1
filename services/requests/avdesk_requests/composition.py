"""Composition root of the requests service: the only module that chooses concrete classes.

Everything else receives its collaborators through constructors and depends
on abstractions (DIP), so swapping the database adapter, the clock or the
task tracker happens here and nowhere else. Boot order matters: migrations,
then seed data, then the app, so no request ever sees an old schema.
"""
from dataclasses import dataclass

from flask import Flask

from avdesk_requests.clock import Clock, SystemClock
from avdesk_requests.config import Config
from avdesk_requests.database import Database, RetryPolicy
from avdesk_requests.domain.events import RequestEventSubject
from avdesk_requests.domain.facade import RequestsFacade
from avdesk_requests.domain.intake import BriefingIntake, BriefingScorer
from avdesk_requests.domain.lifecycle import Lifecycle, StatusCommandFactory
from avdesk_requests.domain.repository import SqlServerCatalogReader, SqlServerRequestRepository
from avdesk_requests.domain.validators import BriefingValidator
from avdesk_requests.health import DatabaseHealthProbe
from avdesk_requests.migrations import MIGRATIONS_DIR, MigrationRunner, load_migrations
from avdesk_requests.seeding import load_reference_data, load_seed
from avdesk_requests.task_observer import TaskTrackerObserver
from avdesk_requests.task_tracker import ClickUpTaskTracker, DisabledTaskTracker, TaskTracker
from avdesk_requests.tokens import SecureTokenGenerator, TokenGenerator
from avdesk_requests.web import create_web_app

# /health must answer in seconds, so it tries the database once; the boot
# uses the default policy and waits out a paused serverless database.
HEALTH_RETRY = RetryPolicy(attempts=1)


@dataclass(frozen=True)
class AppServices:
    requests: RequestsFacade
    config: Config


def build_requests_domain(database: Database, clock: Clock, tokens: TokenGenerator,
                          approval_buffer_days: int) -> tuple[RequestsFacade, RequestEventSubject]:
    repository = SqlServerRequestRepository(database)
    events = RequestEventSubject()
    facade = RequestsFacade(
        catalog_reader=SqlServerCatalogReader(database),
        reader=repository,
        writer=repository,
        intake=BriefingIntake(BriefingValidator(), BriefingScorer(), clock, approval_buffer_days),
        commands=StatusCommandFactory(repository, clock),
        lifecycle=Lifecycle(),
        events=events,
        tokens=tokens,
        clock=clock,
    )
    return facade, events


def build_task_tracker(config: Config) -> TaskTracker:
    if config.clickup_enabled:
        return ClickUpTaskTracker(config.clickup_api_token, config.clickup_list_id)
    return DisabledTaskTracker()


def build_services(config: Config, database: Database, clock: Clock, tokens: TokenGenerator,
                   tracker: TaskTracker) -> AppServices:
    requests, request_events = build_requests_domain(database, clock, tokens, config.approval_buffer_days)
    request_events.attach(TaskTrackerObserver(tracker, requests))
    return AppServices(requests, config)


def prepare_database(database: Database) -> None:
    MigrationRunner(database).apply(load_migrations(MIGRATIONS_DIR))
    load_reference_data(database, load_seed())


def create_app(config: Config, clock: Clock | None = None, tokens: TokenGenerator | None = None,
               tracker: TaskTracker | None = None) -> Flask:
    database = Database(config.database_url)
    prepare_database(database)

    health_probe = DatabaseHealthProbe(database.with_retry(HEALTH_RETRY))
    app = create_web_app(health_probe, config.version)
    app.extensions["avdesk"] = build_services(config, database, clock or SystemClock(),
                                              tokens or SecureTokenGenerator(), tracker or build_task_tracker(config))
    return app
