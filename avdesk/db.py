"""SQLite access shared by both domains: connections, schema creation, seeding.

Startup is idempotent by design (assignment §7.11): tables are created only
if missing and reference data is inserted only into empty tables, so a
restart never duplicates or wipes what users entered.
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


def create_schema(database: Database, schema_files=SCHEMA_FILES) -> None:
    with database.connect() as conn:
        for schema in schema_files:
            conn.executescript(Path(schema).read_text(encoding="utf-8"))


def load_seed(path: Path = SEED_FILE) -> dict[str, list[dict[str, Any]]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {table: rows for table, rows in data.items() if not table.startswith("_")}


def seed_if_empty(database: Database, seed: dict[str, list[dict[str, Any]]]) -> None:
    with database.connect() as conn:
        existing = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        for table, rows in seed.items():
            # Table names cannot be bound as SQL parameters, so only names that
            # already exist in the schema are allowed into the statement.
            if table not in existing:
                raise ValueError(f"seed.json names unknown table {table!r}")
            if conn.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone():
                continue
            for row in rows:
                columns = ", ".join(f'"{c}"' for c in row)
                placeholders = ", ".join("?" for _ in row)
                values = [json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                          for v in row.values()]
                conn.execute(f'INSERT INTO "{table}" ({columns}) VALUES ({placeholders})', values)
