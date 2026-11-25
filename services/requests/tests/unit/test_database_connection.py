import pymssql
import pytest

from avdesk_requests.database import Database, DatabaseUnavailable, DatabaseUrl, RetryPolicy

URL = "mssql://requests_app:s3cr%40t@sql.example.net:1433/requests-db"


def test_a_database_url_names_server_login_and_database():
    url = DatabaseUrl.parse(URL)

    assert (url.host, url.port, url.user, url.database) == ("sql.example.net", 1433, "requests_app", "requests-db")


def test_a_percent_encoded_password_is_decoded():
    assert DatabaseUrl.parse(URL).password == "s3cr@t"


def test_the_port_defaults_to_the_sql_server_port():
    assert DatabaseUrl.parse("mssql://u:p@localhost/db").port == 1433


@pytest.mark.parametrize("bad", ["", "postgres://u:p@h/db", "mssql://u:p@h/", "mssql://h/db"])
def test_an_incomplete_or_foreign_url_is_rejected(bad):
    with pytest.raises(ValueError):
        DatabaseUrl.parse(bad)


def test_the_url_hides_the_password_when_printed():
    assert "s3cr" not in repr(DatabaseUrl.parse(URL))


def test_retry_waits_grow_and_are_capped():
    assert RetryPolicy(attempts=6, first_delay_s=1, max_delay_s=5).delays() == [1, 2, 4, 5, 5]


class FlakyConnect:
    """Fails a given number of times, then hands out a stub connection."""

    def __init__(self, failures: int, mocker):
        self.failures = failures
        self.calls = 0
        self.connection = mocker.Mock()

    def __call__(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise pymssql.OperationalError("40613 database is not currently available")
        return self.connection


def test_a_paused_database_is_retried_until_it_resumes(mocker):
    connect, waits = FlakyConnect(failures=2, mocker=mocker), []
    database = Database(DatabaseUrl.parse(URL), connect=connect, retry=RetryPolicy(attempts=5), sleep=waits.append)

    with database.connect():
        pass

    assert waits == [1, 2]


def test_a_database_that_never_answers_raises_after_the_last_attempt(mocker):
    connect = FlakyConnect(failures=99, mocker=mocker)
    database = Database(DatabaseUrl.parse(URL), connect=connect, retry=RetryPolicy(attempts=3), sleep=lambda s: None)

    with pytest.raises(DatabaseUnavailable):
        with database.connect():
            pass


def test_a_unit_of_work_commits_when_it_succeeds(mocker):
    connect = FlakyConnect(failures=0, mocker=mocker)
    database = Database(DatabaseUrl.parse(URL), connect=connect, sleep=lambda s: None)

    with database.connect():
        pass

    connect.connection.commit.assert_called_once()


def test_a_unit_of_work_rolls_back_when_it_fails(mocker):
    connect = FlakyConnect(failures=0, mocker=mocker)
    database = Database(DatabaseUrl.parse(URL), connect=connect, sleep=lambda s: None)

    with pytest.raises(RuntimeError):
        with database.connect():
            raise RuntimeError("boom")

    connect.connection.rollback.assert_called_once()
