"""Composition root: the only module that chooses concrete classes.

Everything else receives its collaborators through constructors and depends
on abstractions (DIP), so swapping SQLite, the clock or the task tracker
happens here and nowhere else.
"""
from flask import Flask

from avdesk.clock import Clock, SystemClock
from avdesk.config import Config
from avdesk.db import Database, create_schema, load_seed, seed_if_empty
from avdesk.tokens import SecureTokenGenerator, TokenGenerator
from avdesk.web import public


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
