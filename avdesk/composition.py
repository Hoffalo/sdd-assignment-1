"""Composition root: the only module that chooses concrete classes.

Everything else receives its collaborators through constructors and depends
on abstractions (DIP), so swapping SQLite, the clock or the task tracker
happens here and nowhere else.
"""
from flask import Flask

from avdesk.clock import Clock, SystemClock
from avdesk.config import Config
from avdesk.db import Database, create_schema, load_seed, seed_if_empty
from avdesk.requests_domain.events import RequestEventSubject
from avdesk.requests_domain.facade import RequestsFacade
from avdesk.requests_domain.intake import BriefingIntake
from avdesk.requests_domain.lifecycle import Lifecycle, StatusCommandFactory
from avdesk.requests_domain.repository import SqliteCatalogReader, SqliteRequestRepository
from avdesk.requests_domain.scoring import BriefingScorer
from avdesk.requests_domain.validators import BriefingValidator
from avdesk.tokens import SecureTokenGenerator, TokenGenerator
from avdesk.web import public


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


def create_app(config: Config, clock: Clock | None = None, tokens: TokenGenerator | None = None) -> Flask:
    clock = clock or SystemClock()
    tokens = tokens or SecureTokenGenerator()

    database = Database(config.database_path)
    create_schema(database)
    seed_if_empty(database, load_seed())

    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
    app.secret_key = config.secret_key
    app.register_blueprint(public.blueprint)
    return app
