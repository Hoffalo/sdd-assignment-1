import pytest

from avdesk_feedback.migrations import MigrationFileError, load_migrations


def write(directory, name, text):
    (directory / name).write_text(text, encoding="utf-8", newline="")


def test_migrations_are_ordered_by_their_number_not_by_file_name(tmp_path):
    write(tmp_path, "010_later.sql", "SELECT 10")
    write(tmp_path, "002_second.sql", "SELECT 2")
    write(tmp_path, "001_first.sql", "SELECT 1")

    migrations = load_migrations(tmp_path)

    assert [m.version for m in migrations] == [1, 2, 10]


def test_a_migration_is_named_after_its_file(tmp_path):
    write(tmp_path, "001_init.sql", "SELECT 1")

    [migration] = load_migrations(tmp_path)

    assert migration.name == "001_init"


def test_files_that_are_not_numbered_sql_are_ignored(tmp_path):
    write(tmp_path, "001_init.sql", "SELECT 1")
    write(tmp_path, "README.md", "notes")

    assert len(load_migrations(tmp_path)) == 1


def test_two_files_with_the_same_number_are_rejected(tmp_path):
    write(tmp_path, "001_init.sql", "SELECT 1")
    write(tmp_path, "001_other.sql", "SELECT 2")

    with pytest.raises(MigrationFileError):
        load_migrations(tmp_path)


def test_a_go_line_splits_a_migration_into_batches(tmp_path):
    write(tmp_path, "001_init.sql", "ALTER TABLE t ADD c INT\nGO\nUPDATE t SET c = 1\n")

    [migration] = load_migrations(tmp_path)

    assert [b.strip() for b in migration.batches] == ["ALTER TABLE t ADD c INT", "UPDATE t SET c = 1"]


def test_go_inside_a_word_does_not_split(tmp_path):
    write(tmp_path, "001_init.sql", "UPDATE t SET category = 'GOLD'\n")

    [migration] = load_migrations(tmp_path)

    assert len(migration.batches) == 1


def test_line_endings_do_not_change_the_checksum(tmp_path):
    unix, windows = tmp_path / "unix", tmp_path / "windows"
    unix.mkdir()
    windows.mkdir()
    write(unix, "001_init.sql", "SELECT 1\nSELECT 2\n")
    write(windows, "001_init.sql", "SELECT 1\r\nSELECT 2\r\n")

    assert load_migrations(unix)[0].checksum == load_migrations(windows)[0].checksum


def test_any_edit_changes_the_checksum(tmp_path):
    original, edited = tmp_path / "original", tmp_path / "edited"
    original.mkdir()
    edited.mkdir()
    write(original, "001_init.sql", "SELECT 1")
    write(edited, "001_init.sql", "SELECT 2")

    assert load_migrations(original)[0].checksum != load_migrations(edited)[0].checksum
