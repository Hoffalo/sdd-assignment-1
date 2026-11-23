"""Integration fixtures: a throwaway database on a real SQL Server per test.

The server comes from TEST_SQLSERVER_URL (a login allowed to create
databases, e.g. sa on the compose or CI container). Without it these tests
are skipped rather than failed, so the unit suite still runs on a laptop
with no Docker; CI always sets it. Azure SQL is never used here: every
connection would wake the serverless database and be billed.
"""
import os
import uuid

import pytest

from avdesk_requests.database import Database, DatabaseUrl, RetryPolicy

SERVER_URL_ENV = "TEST_SQLSERVER_URL"
# A test that waits a minute for a missing server is worse than a clear failure.
TEST_RETRY = RetryPolicy(attempts=2, first_delay_s=1, max_delay_s=1)


@pytest.fixture(scope="session")
def sql_server() -> Database:
    raw_url = os.environ.get(SERVER_URL_ENV)
    if not raw_url:
        pytest.skip(f"{SERVER_URL_ENV} is not set; integration tests need a SQL Server")
    return Database(DatabaseUrl.parse(raw_url), retry=TEST_RETRY, autocommit=True)


@pytest.fixture
def empty_database(sql_server):
    # A fresh database per test keeps tests independent (FIRST) at ~0.5 s each;
    # cleaning shared tables instead would leak identity values between tests.
    name = f"avdesk_requests_test_{uuid.uuid4().hex[:12]}"
    with sql_server.connect() as session:
        session.execute(f"CREATE DATABASE [{name}]")
    yield Database(sql_server.url.with_database(name), retry=TEST_RETRY)
    with sql_server.connect() as session:
        session.execute(f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        session.execute(f"DROP DATABASE [{name}]")
