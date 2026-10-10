import pytest

from avdesk.db import Database, create_schema, load_seed, seed_if_empty
from tests.doubles import FixedClock, SequentialTokens


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
