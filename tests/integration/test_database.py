import json

import pytest

from avdesk.db import Database, create_schema, load_seed, seed_if_empty


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

    seed_if_empty(migrated_db, seed)
    first = table_counts(migrated_db)
    seed_if_empty(migrated_db, seed)

    assert table_counts(migrated_db) == first


def test_seed_skips_tables_that_already_have_data(migrated_db):
    with migrated_db.connect() as conn:
        conn.execute("INSERT INTO diretorias (name) VALUES ('Só esta')")

    seed_if_empty(migrated_db, {"diretorias": [{"name": "Outra"}]})

    assert table_counts(migrated_db)["diretorias"] == 1


def test_seed_rejects_unknown_tables(migrated_db):
    with pytest.raises(ValueError):
        seed_if_empty(migrated_db, {"not_a_table": [{"x": 1}]})


def test_seed_serialises_list_values_as_json(migrated_db):
    seed_if_empty(migrated_db, load_seed())

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
