import json

import pytest

from avdesk.db import MIGRATIONS, Database, create_schema, load_reference_data, load_seed


def table_counts(database: Database) -> dict[str, int]:
    with database.connect() as conn:
        names = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
        return {n: conn.execute(f'SELECT count(*) FROM "{n}"').fetchone()[0] for n in names}


def test_schema_is_created_on_an_empty_data_dir(tmp_path):
    database = Database(tmp_path / "fresh" / "avdesk.sqlite3")

    create_schema(database)

    assert {"requests", "request_events", "feedback_invites", "feedback_responses"} <= set(table_counts(database))


def test_creating_the_schema_twice_keeps_existing_rows(migrated_db):
    with migrated_db.connect() as conn:
        conn.execute("INSERT INTO diretorias (name) VALUES ('Teste')")

    create_schema(migrated_db)

    assert table_counts(migrated_db)["diretorias"] == 1


def test_seeding_twice_does_not_duplicate_rows(migrated_db):
    seed = load_seed()

    load_reference_data(migrated_db, seed)
    first = table_counts(migrated_db)
    load_reference_data(migrated_db, seed)

    assert table_counts(migrated_db) == first


def test_seed_skips_tables_that_already_have_data(migrated_db):
    with migrated_db.connect() as conn:
        conn.execute("INSERT INTO diretorias (name) VALUES ('Só esta')")

    load_reference_data(migrated_db, {"diretorias": [{"name": "Outra"}]})

    assert table_counts(migrated_db)["diretorias"] == 1


def test_seed_rejects_unknown_tables(migrated_db):
    with pytest.raises(ValueError):
        load_reference_data(migrated_db, {"not_a_table": [{"x": 1}]})


def test_seed_serialises_list_values_as_json(migrated_db):
    load_reference_data(migrated_db, load_seed())

    with migrated_db.connect() as conn:
        raw = conn.execute("SELECT options_json FROM briefing_questions WHERE kind = 'choice' LIMIT 1").fetchone()[0]

    assert isinstance(json.loads(raw), list)


def test_feedback_tables_hold_no_foreign_key_into_requests(migrated_db):
    with migrated_db.connect() as conn:
        targets = {row["table"] for table in ("feedback_invites", "feedback_responses")
                   for row in conn.execute(f"PRAGMA foreign_key_list({table})")}

    assert targets <= {"feedback_invites"}


def test_foreign_keys_are_enforced(migrated_db):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        with migrated_db.connect() as conn:
            conn.execute("INSERT INTO request_events (request_id, to_status, actor, created_at) "
                         "VALUES (999, 'submitted', 'x', '2026-01-01')")


# Upgrading an existing database

def columns(database: Database, table: str) -> set[str]:
    with database.connect() as conn:
        return {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def schema_version(database: Database) -> int:
    with database.connect() as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


@pytest.fixture
def old_db(tmp_path):
    """A database created before the follow-up questions and review links existed."""
    database = Database(tmp_path / "old.sqlite3")
    with database.connect() as conn:
        conn.execute("CREATE TABLE request_types (code TEXT PRIMARY KEY, min_lead_business_days INTEGER)")
        conn.execute("CREATE TABLE briefing_questions (key TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE requests (id INTEGER PRIMARY KEY, status TEXT)")
    return database


def test_a_new_database_starts_at_the_latest_version(migrated_db):
    assert schema_version(migrated_db) == len(MIGRATIONS)


def test_an_old_database_gains_the_new_columns(old_db):
    create_schema(old_db)

    assert {"depends_on", "depends_value"} <= columns(old_db, "briefing_questions") and \
           "review_url" in columns(old_db, "requests")


def test_an_old_database_counts_lead_time_in_calendar_days(old_db):
    create_schema(old_db)

    assert "min_lead_days" in columns(old_db, "request_types")


def test_upgrading_twice_is_harmless(old_db):
    create_schema(old_db)
    create_schema(old_db)

    assert schema_version(old_db) == len(MIGRATIONS)


# The briefing catalog follows seed.json

def question_keys(database: Database) -> set[str]:
    with database.connect() as conn:
        return {row["key"] for row in conn.execute("SELECT key FROM briefing_questions")}


def test_removed_questions_disappear_from_an_existing_database(seeded_db):
    seed = load_seed()
    seed["briefing_questions"] = [q for q in seed["briefing_questions"] if q["key"] != "musica"]

    load_reference_data(seeded_db, seed)

    assert "musica" not in question_keys(seeded_db)


def test_edited_questions_are_updated_in_an_existing_database(seeded_db):
    seed = load_seed()
    next(q for q in seed["briefing_questions"] if q["key"] == "objetivo")["label"] = "Novo texto"

    load_reference_data(seeded_db, seed)

    with seeded_db.connect() as conn:
        label = conn.execute("SELECT label FROM briefing_questions WHERE key = 'objetivo'").fetchone()[0]
    assert label == "Novo texto"


def test_seed_once_tables_keep_their_rows(seeded_db):
    load_reference_data(seeded_db, {"diretorias": [{"name": "Só esta"}]})

    assert table_counts(seeded_db)["diretorias"] == 8


def test_catalog_rows_must_list_every_column(seeded_db):
    seed = load_seed()
    del seed["briefing_questions"][0]["help"]

    with pytest.raises(ValueError):
        load_reference_data(seeded_db, seed)
