import json

import pymssql
import pytest

from avdesk_requests.database import Database
from avdesk_requests.seeding import load_reference_data, load_seed

DOMAIN_TABLES = {"diretorias", "analysts", "request_types", "briefing_questions", "requests", "request_events"}


def table_counts(database: Database) -> dict[str, int]:
    with database.connect() as session:
        names = [r["name"] for r in session.execute(
            "SELECT TABLE_NAME AS name FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'").fetchall()]
        return {n: session.execute(f"SELECT COUNT(*) AS n FROM [{n}]").fetchone()["n"] for n in names}


def test_migrations_create_every_table_of_the_requests_domain(migrated_db):
    assert DOMAIN_TABLES <= set(table_counts(migrated_db))


def test_the_requests_database_holds_no_feedback_tables(migrated_db):
    assert not {"feedback_invites", "feedback_responses"} & set(table_counts(migrated_db))


def test_seeding_twice_does_not_duplicate_rows(migrated_db):
    seed = load_seed()

    load_reference_data(migrated_db, seed)
    first = table_counts(migrated_db)
    load_reference_data(migrated_db, seed)

    assert table_counts(migrated_db) == first


def test_seed_skips_tables_that_already_have_data(migrated_db):
    with migrated_db.connect() as session:
        session.execute("INSERT INTO diretorias (name) VALUES (N'Só esta')")

    load_reference_data(migrated_db, {"diretorias": [{"name": "Outra"}]})

    assert table_counts(migrated_db)["diretorias"] == 1


def test_seed_rejects_unknown_tables(migrated_db):
    with pytest.raises(ValueError):
        load_reference_data(migrated_db, {"not_a_table": [{"x": 1}]})


def test_seeded_options_are_stored_as_json(seeded_db):
    with seeded_db.connect() as session:
        raw = session.execute(
            "SELECT TOP 1 options_json FROM briefing_questions WHERE kind = 'choice'").fetchone()["options_json"]

    assert isinstance(json.loads(raw), list)


def test_foreign_keys_inside_the_domain_are_enforced(migrated_db):
    with pytest.raises(pymssql.IntegrityError):
        with migrated_db.connect() as session:
            session.execute("INSERT INTO request_events (request_id, to_status, actor, created_at) "
                            "VALUES (999, 'submitted', 'x', '2026-01-01')")


# The briefing catalog follows seed.json

def question_keys(database: Database) -> set[str]:
    with database.connect() as session:
        return {row["key"] for row in session.execute("SELECT [key] FROM briefing_questions").fetchall()}


def test_removed_questions_disappear_from_an_existing_database(seeded_db):
    seed = load_seed()
    seed["briefing_questions"] = [q for q in seed["briefing_questions"] if q["key"] != "musica"]

    load_reference_data(seeded_db, seed)

    assert "musica" not in question_keys(seeded_db)


def test_edited_questions_are_updated_in_an_existing_database(seeded_db):
    seed = load_seed()
    next(q for q in seed["briefing_questions"] if q["key"] == "objetivo")["label"] = "Novo texto"

    load_reference_data(seeded_db, seed)

    with seeded_db.connect() as session:
        label = session.execute("SELECT label FROM briefing_questions WHERE [key] = 'objetivo'").fetchone()["label"]
    assert label == "Novo texto"


def test_seed_once_tables_keep_their_rows(seeded_db):
    load_reference_data(seeded_db, {"diretorias": [{"name": "Só esta"}]})

    assert table_counts(seeded_db)["diretorias"] == 8


def test_catalog_rows_must_list_every_column(seeded_db):
    seed = load_seed()
    del seed["briefing_questions"][0]["help"]

    with pytest.raises(ValueError):
        load_reference_data(seeded_db, seed)
