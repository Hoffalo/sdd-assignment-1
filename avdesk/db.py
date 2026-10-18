"""SQLite access shared by both domains: connections, schema, migrations, reference data.

Startup is idempotent by design (assignment §7.11): tables are created only
if missing, migrations run once each, and reference data is loaded without
ever duplicating rows, so a restart never duplicates or wipes what users entered.
"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

PACKAGE_DIR = Path(__file__).resolve().parent
SCHEMA_FILES = (
    PACKAGE_DIR / "requests_domain" / "schema.sql",
    PACKAGE_DIR / "feedback_domain" / "schema.sql",
)
SEED_FILE = PACKAGE_DIR.parent / "seed.json"

# Append-only. schema.sql always describes the latest shape, so a new database
# is stamped at len(MIGRATIONS); an older one replays only the steps it lacks.
# The step number is kept in SQLite's own PRAGMA user_version.
MIGRATIONS = (
    "ALTER TABLE briefing_questions ADD COLUMN depends_on TEXT",
    "ALTER TABLE briefing_questions ADD COLUMN depends_value TEXT",
    "ALTER TABLE requests ADD COLUMN review_url TEXT",
)

# The briefing catalog is configuration owned by seed.json, so it follows the
# file on every boot: rows are matched by their natural key and updated.
# Questions missing from the file are removed (nothing references them);
# request types are never removed because requests point at them.
# Diretorias and analysts are not listed: requests point at them by id, so
# they are seeded once into empty tables and never rewritten.
SYNCED_TABLES = {
    "request_types": ("code", False),
    "briefing_questions": ("key", True),
}


class Database:
    """Hands out one connection per unit of work.

    Deliberately not a Singleton: waitress runs requests on several threads
    and a sqlite3 connection must not be shared between them.
    """

    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {row["name"] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}


def create_schema(database: Database, schema_files=SCHEMA_FILES, migrations=MIGRATIONS) -> None:
    with database.connect() as conn:
        is_new = not _table_names(conn)
        for schema in schema_files:
            conn.executescript(Path(schema).read_text(encoding="utf-8"))
        version = len(migrations) if is_new else conn.execute("PRAGMA user_version").fetchone()[0]
        for step in migrations[version:]:
            conn.execute(step)
        # PRAGMA values cannot be bound as parameters; this is an int we computed.
        conn.execute(f"PRAGMA user_version = {len(migrations)}")


def load_seed(path: Path = SEED_FILE) -> dict[str, list[dict[str, Any]]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {table: rows for table, rows in data.items() if not table.startswith("_")}


def _values(row: dict[str, Any]) -> list[Any]:
    return [json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for v in row.values()]


def _insert(conn: sqlite3.Connection, table: str, row: dict[str, Any], upsert_key: str | None = None) -> None:
    columns = ", ".join(f'"{c}"' for c in row)
    placeholders = ", ".join("?" for _ in row)
    statement = f'INSERT INTO "{table}" ({columns}) VALUES ({placeholders})'
    if upsert_key:
        updates = ", ".join(f'"{c}" = excluded."{c}"' for c in row if c != upsert_key)
        statement += f' ON CONFLICT ("{upsert_key}") DO UPDATE SET {updates}'
    conn.execute(statement, _values(row))


def _sync(conn: sqlite3.Connection, table: str, rows: list[dict[str, Any]], key: str, prune: bool) -> None:
    table_columns = {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")')}
    for row in rows:
        # A synced row overwrites the stored one, so a missing column would
        # silently keep a stale value; every column must be stated.
        if set(row) != table_columns:
            raise ValueError(f"seed.json row {row.get(key)!r} in {table} must list exactly {sorted(table_columns)}")
        _insert(conn, table, row, upsert_key=key)
    if prune:
        keys = [row[key] for row in rows]
        conn.execute(f'DELETE FROM "{table}" WHERE "{key}" NOT IN ({", ".join("?" for _ in keys)})', keys)


def load_reference_data(database: Database, seed: dict[str, list[dict[str, Any]]]) -> None:
    with database.connect() as conn:
        existing = _table_names(conn)
        for table, rows in seed.items():
            # Table names cannot be bound as SQL parameters, so only names that
            # already exist in the schema are allowed into the statement.
            if table not in existing:
                raise ValueError(f"seed.json names unknown table {table!r}")
            if table in SYNCED_TABLES:
                _sync(conn, table, rows, *SYNCED_TABLES[table])
            elif not conn.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone():
                for row in rows:
                    _insert(conn, table, row)
