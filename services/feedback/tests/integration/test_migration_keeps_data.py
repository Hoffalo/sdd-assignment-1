"""Migrations that change a table already holding rows must keep those rows.

Reproduces production on a fresh database: the schema as it was deployed,
real invites in it, then the newer migrations applied on top.
"""
from datetime import date, datetime, timezone

from avdesk_feedback.domain.models import DeliveredWork
from avdesk_feedback.domain.repository import NewInvite, SqlServerFeedbackRepository
from avdesk_feedback.migrations import MIGRATIONS_DIR, MigrationRunner, load_migrations

DEPLOYED_BEFORE_RENAME = 3
AT = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
WORK = DeliveredWork(42, "AV-2026-0042", "Teaser", "Teaser", "Conferências", "https://drive.google.com/x",
                     date(2026, 12, 1), AT)


def test_renaming_the_diretoria_snapshot_keeps_existing_invites(empty_database):
    migrations = load_migrations(MIGRATIONS_DIR)
    MigrationRunner(empty_database).apply([m for m in migrations if m.version <= DEPLOYED_BEFORE_RENAME])
    with empty_database.connect() as session:
        session.execute(
            "INSERT INTO feedback_invites (token, request_id, public_code, request_title, type_label, diretoria, "
            "delivery_url, needed_by, delivered_at, recipient_label, is_requester, expires_at, created_at) "
            "VALUES ('t-1', 42, 'AV-2026-0042', 'Teaser', 'Teaser', N'Conferências', 'https://drive.google.com/x', "
            "'2026-12-01', '2026-11-25 12:00', 'Ana', 1, '2026-12-25 12:00', '2026-11-25 12:00')")

    MigrationRunner(empty_database).apply(migrations)

    assert SqlServerFeedbackRepository(empty_database).invite_by_token("t-1").work.diretoria == "Conferências"


def test_invites_written_after_the_rename_read_back_the_same(empty_database):
    MigrationRunner(empty_database).apply(load_migrations(MIGRATIONS_DIR))
    repository = SqlServerFeedbackRepository(empty_database)

    repository.add_invites(WORK, [NewInvite("t-2", "Ana", True, AT)], AT)

    assert repository.invite_by_token("t-2").work.diretoria == "Conferências"
