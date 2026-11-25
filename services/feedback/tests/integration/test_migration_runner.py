import pytest

from avdesk_feedback.migrations import AppliedMigrationEdited, MigrationRunner, load_migrations


def write(directory, name, text):
    (directory / name).write_text(text, encoding="utf-8")


@pytest.fixture
def migrations_dir(tmp_path):
    write(tmp_path, "001_init.sql", "CREATE TABLE notes (id INT IDENTITY PRIMARY KEY, body NVARCHAR(100) NOT NULL)")
    return tmp_path


def note_bodies(database) -> list:
    with database.connect() as session:
        return [row["body"] for row in session.execute("SELECT body FROM notes ORDER BY id").fetchall()]


def test_pending_migrations_are_applied_in_order(empty_database, migrations_dir):
    write(migrations_dir, "002_seed.sql", "INSERT INTO notes (body) VALUES (N'first')")

    applied = MigrationRunner(empty_database).apply(load_migrations(migrations_dir))

    assert [m.name for m in applied] == ["001_init", "002_seed"]


def test_a_second_boot_applies_nothing(empty_database, migrations_dir):
    runner = MigrationRunner(empty_database)
    runner.apply(load_migrations(migrations_dir))

    assert runner.apply(load_migrations(migrations_dir)) == []


def test_applied_migrations_are_recorded_in_the_database(empty_database, migrations_dir):
    MigrationRunner(empty_database).apply(load_migrations(migrations_dir))

    with empty_database.connect() as session:
        versions = [r["version"] for r in session.execute("SELECT version FROM schema_migrations").fetchall()]
    assert versions == [1]


def test_a_new_migration_keeps_the_rows_already_stored(empty_database, migrations_dir):
    runner = MigrationRunner(empty_database)
    runner.apply(load_migrations(migrations_dir))
    with empty_database.connect() as session:
        session.execute("INSERT INTO notes (body) VALUES (N'kept')")
    write(migrations_dir, "002_add_pinned.sql",
          "ALTER TABLE notes ADD pinned BIT NOT NULL CONSTRAINT df_notes_pinned DEFAULT 0")

    runner.apply(load_migrations(migrations_dir))

    assert note_bodies(empty_database) == ["kept"]


def test_a_column_can_be_added_and_backfilled_in_one_migration(empty_database, migrations_dir):
    runner = MigrationRunner(empty_database)
    runner.apply(load_migrations(migrations_dir))
    with empty_database.connect() as session:
        session.execute("INSERT INTO notes (body) VALUES (N'abc')")
    write(migrations_dir, "002_add_length.sql",
          "ALTER TABLE notes ADD body_length INT NULL\nGO\nUPDATE notes SET body_length = LEN(body)\n")

    runner.apply(load_migrations(migrations_dir))

    with empty_database.connect() as session:
        assert session.execute("SELECT body_length FROM notes").fetchone()["body_length"] == 3


def test_a_failing_migration_leaves_no_trace(empty_database, migrations_dir):
    write(migrations_dir, "002_broken.sql", "ALTER TABLE notes ADD extra INT NULL\nGO\nSELECT * FROM missing_table")

    # pymssql reports the missing table as a ProgrammingError; any error must roll back.
    with pytest.raises(Exception):  # noqa: B017
        MigrationRunner(empty_database).apply(load_migrations(migrations_dir))

    with empty_database.connect() as session:
        versions = [r["version"] for r in session.execute("SELECT version FROM schema_migrations").fetchall()]
    assert versions == [1]


def test_editing_an_applied_migration_stops_the_boot(empty_database, migrations_dir):
    runner = MigrationRunner(empty_database)
    runner.apply(load_migrations(migrations_dir))
    write(migrations_dir, "001_init.sql", "CREATE TABLE notes (id INT PRIMARY KEY)")

    with pytest.raises(AppliedMigrationEdited):
        runner.apply(load_migrations(migrations_dir))
