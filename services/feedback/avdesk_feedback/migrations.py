"""Versioned schema migrations: numbered SQL files applied once each, in order, at startup.

The schema is never recreated. Each file in migrations/ (001_init.sql,
002_...) runs exactly once and is recorded in schema_migrations together with
a checksum, so a second boot applies nothing and an applied file that was
edited stops the boot instead of drifting silently (corrections go in a new
file). Forward-only by design; ADR-7 holds the recovery plan.

A line containing only GO ends a batch, as in sqlcmd. SQL Server compiles a
whole batch before running it, so a column added by ALTER TABLE cannot be
used by an UPDATE in the same batch; GO is how one migration adds and
backfills a column.
"""
import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from avdesk_feedback.database import Database

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
FILE_PATTERN = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")
BATCH_SEPARATOR = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)

CREATE_LEDGER = """
IF OBJECT_ID(N'schema_migrations', N'U') IS NULL
    CREATE TABLE schema_migrations (
        version     INT           NOT NULL PRIMARY KEY,
        name        NVARCHAR(200) NOT NULL,
        checksum    CHAR(64)      NOT NULL,
        applied_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
    )
"""


class MigrationFileError(Exception):
    """The migrations folder is malformed (for example two files share a number)."""


class AppliedMigrationEdited(Exception):
    """A migration already applied to this database no longer matches its file."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    batches: tuple[str, ...]
    checksum: str


def _read_migration(path: Path, version: int) -> Migration:
    # Checksummed with Unix line endings, so a Windows checkout of the same
    # commit is not mistaken for an edit.
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    batches = tuple(batch for batch in BATCH_SEPARATOR.split(text) if batch.strip())
    return Migration(version, path.stem, batches, hashlib.sha256(text.encode("utf-8")).hexdigest())


def load_migrations(directory: Path) -> list[Migration]:
    migrations: dict[int, Migration] = {}
    for path in sorted(Path(directory).iterdir()):
        match = FILE_PATTERN.match(path.name)
        if not match:
            continue
        version = int(match.group(1))
        if version in migrations:
            raise MigrationFileError(f"{path.name} reuses number {version:03d} of {migrations[version].name}")
        migrations[version] = _read_migration(path, version)
    return [migrations[v] for v in sorted(migrations)]


class MigrationRunner:
    """Brings a database up to the latest migration.

    One transaction per migration: if any batch fails, its earlier batches and
    its ledger row are rolled back together and the boot fails loudly. Runs
    with a single replica (max replicas 1), so two runners never race.
    """

    def __init__(self, database: Database):
        self._db = database

    def _applied_checksums(self) -> dict[int, str]:
        with self._db.connect() as session:
            session.execute(CREATE_LEDGER)
            rows = session.execute("SELECT version, checksum FROM schema_migrations").fetchall()
        return {row["version"]: row["checksum"] for row in rows}

    def apply(self, migrations: list[Migration]) -> list[Migration]:
        applied = self._applied_checksums()
        newly_applied = []
        for migration in migrations:
            if migration.version in applied:
                if applied[migration.version] != migration.checksum:
                    raise AppliedMigrationEdited(
                        f"{migration.name} was edited after it was applied; put the change in a new migration")
                continue
            with self._db.connect() as session:
                for batch in migration.batches:
                    session.execute(batch)
                session.execute("INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                                (migration.version, migration.name, migration.checksum))
            log.info("Applied migration %s", migration.name)
            newly_applied.append(migration)
        if not newly_applied:
            log.info("Schema is up to date (%d migrations)", len(migrations))
        return newly_applied
