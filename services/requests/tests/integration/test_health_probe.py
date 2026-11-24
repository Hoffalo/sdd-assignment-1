from avdesk_requests.database import Database, DatabaseUrl, RetryPolicy
from avdesk_requests.health import DatabaseHealthProbe


def test_a_migrated_database_is_healthy(migrated_db):
    assert DatabaseHealthProbe(migrated_db).database_is_healthy()


def test_a_database_without_the_probe_table_is_unhealthy(empty_database):
    assert not DatabaseHealthProbe(empty_database).database_is_healthy()


def test_an_unreachable_server_is_unhealthy():
    nowhere = Database(DatabaseUrl.parse("mssql://u:p@127.0.0.1:1/none"), retry=RetryPolicy(attempts=1))

    assert not DatabaseHealthProbe(nowhere).database_is_healthy()
