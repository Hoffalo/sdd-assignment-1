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
from avdesk_feedback.requests_client import DisabledRequestVerdicts, HttpRequestVerdicts, RequestVerdicts
from avdesk_feedback.tokens import SecureTokenGenerator, TokenGenerator
from avdesk_feedback.verdict_observer import RequesterVerdictObserver
from avdesk_feedback.web import create_web_app, register_api
from avdesk_feedback.web.admin_guard import SERVICE_CLAIM, AdminTokens

# /health must answer in seconds, so it tries the database once; the boot
# uses the default policy and waits out a paused serverless database.
HEALTH_RETRY = RetryPolicy(attempts=1)
# Upper bound when verifying; matches the requests service default of 12 hours.
ADMIN_TOKEN_MAX_AGE_S = 12 * 60 * 60
# A service token is issued for each call, so a few minutes of life is plenty
# and a captured one is useless soon after.
SERVICE_TOKEN_TTL_S = 5 * 60


@dataclass(frozen=True)
class AppServices:
    feedback: FeedbackFacade
    config: Config
    verdicts: RequesterVerdictObserver


def build_feedback_domain(database: Database, clock: Clock, tokens: TokenGenerator,
                          ttl_days: int) -> tuple[FeedbackFacade, FeedbackEventSubject]:
    repository = SqlServerFeedbackRepository(database)
    events = FeedbackEventSubject()
    facade = FeedbackFacade(reader=repository, writer=repository, events=events, tokens=tokens, clock=clock,
                            ttl_days=ttl_days)
    return facade, events


def build_request_verdicts(config: Config, service_tokens: AdminTokens) -> RequestVerdicts:
    if config.requests_url:
        return HttpRequestVerdicts(config.requests_url, service_tokens.issue)
    return DisabledRequestVerdicts()


def create_app(config: Config, clock: Clock | None = None, tokens: TokenGenerator | None = None,
               verdicts: RequestVerdicts | None = None) -> Flask:
    database = Database(config.database_url)
    MigrationRunner(database).apply(load_migrations(MIGRATIONS_DIR))

    service_tokens = AdminTokens(config.admin_token_secret, SERVICE_TOKEN_TTL_S, SERVICE_CLAIM)
    feedback, feedback_events = build_feedback_domain(database, clock or SystemClock(),
                                                      tokens or SecureTokenGenerator(), config.feedback_ttl_days)
    verdict_observer = RequesterVerdictObserver(verdicts or build_request_verdicts(config, service_tokens), feedback)
    feedback_events.attach(verdict_observer)
    app = create_web_app(DatabaseHealthProbe(database.with_retry(HEALTH_RETRY)), config.version, config.cors_origin)
    # Only verifies admin tokens, so the lifetime the requests service chose applies.
    register_api(app, AppServices(feedback, config, verdict_observer),
                 AdminTokens(config.admin_token_secret, ADMIN_TOKEN_MAX_AGE_S), service_tokens)
    return app
