import pytest

from avdesk.composition import create_app
from avdesk.config import Config
from avdesk.db import Database, create_schema, load_seed, seed_if_empty
from tests.doubles import FixedClock, SequentialTokens

ADMIN_PASSWORD = "test-admin"


@pytest.fixture
def clock():
    return FixedClock()


@pytest.fixture
def tokens():
    return SequentialTokens()


@pytest.fixture
def migrated_db(tmp_path):
    database = Database(tmp_path / "avdesk.sqlite3")
    create_schema(database)
    yield database


@pytest.fixture
def seeded_db(migrated_db):
    seed_if_empty(migrated_db, load_seed())
    return migrated_db


@pytest.fixture
def app(tmp_path, clock, tokens):
    config = Config.from_env({"DATA_DIR": str(tmp_path / "data"), "ADMIN_PASSWORD": ADMIN_PASSWORD})
    flask_app = create_app(config, clock=clock, tokens=tokens)
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()
