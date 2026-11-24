"""Composition root of the feedback service: the only module that chooses concrete classes.

Boot order matters: migrations first, then the app, so no request ever sees
an old schema. The feedback service has no seed data: its tables hold only
what users submit.
"""
from dataclasses import dataclass

from flask import Flask

from avdesk_feedback.clock import Clock, SystemClock
from avdesk_feedback.config import Config
from avdesk_feedback.database import Database, RetryPolicy
from avdesk_feedback.domain.events import FeedbackEventSubject
from avdesk_feedback.domain.facade import FeedbackFacade
from avdesk_feedback.domain.repository import SqlServerFeedbackRepository
from avdesk_feedback.health import DatabaseHealthProbe
from avdesk_feedback.migrations import MIGRATIONS_DIR, MigrationRunner, load_migrations
from avdesk_feedback.tokens import SecureTokenGenerator, TokenGenerator
from avdesk_feedback.web import create_web_app

# /health must answer in seconds, so it tries the database once; the boot
# uses the default policy and waits out a paused serverless database.
HEALTH_RETRY = RetryPolicy(attempts=1)


@dataclass(frozen=True)
class AppServices:
    feedback: FeedbackFacade
    config: Config


def build_feedback_domain(database: Database, clock: Clock, tokens: TokenGenerator,
                          ttl_days: int) -> tuple[FeedbackFacade, FeedbackEventSubject]:
    repository = SqlServerFeedbackRepository(database)
    events = FeedbackEventSubject()
    facade = FeedbackFacade(reader=repository, writer=repository, events=events, tokens=tokens, clock=clock,
                            ttl_days=ttl_days)
    return facade, events


def create_app(config: Config, clock: Clock | None = None, tokens: TokenGenerator | None = None) -> Flask:
    database = Database(config.database_url)
    MigrationRunner(database).apply(load_migrations(MIGRATIONS_DIR))

    feedback, _ = build_feedback_domain(database, clock or SystemClock(), tokens or SecureTokenGenerator(),
                                        config.feedback_ttl_days)
    app = create_web_app(DatabaseHealthProbe(database.with_retry(HEALTH_RETRY)), config.version)
    app.extensions["avdesk"] = AppServices(feedback, config)
    return app
