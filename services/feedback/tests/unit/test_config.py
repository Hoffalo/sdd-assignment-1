import pytest

from avdesk_feedback.config import Config, MissingSetting, get_config, reset_config

DATABASE_URL = "mssql://feedback_app:pw@sql:1433/feedback"
BASE = {"DATABASE_URL": DATABASE_URL}


@pytest.fixture(autouse=True)
def fresh_singleton():
    reset_config()
    yield
    reset_config()


def test_defaults_apply_when_only_the_database_is_given():
    config = Config.from_env(BASE)

    assert (config.port, config.version, config.feedback_ttl_days) == (8000, "dev", 30)


def test_settings_are_read_from_environment():
    config = Config.from_env({**BASE, "PORT": "9001", "GIT_SHA": "abc123", "FEEDBACK_TTL_DAYS": "7"})

    assert (config.port, config.version, config.feedback_ttl_days) == (9001, "abc123", 7)


def test_a_missing_database_url_stops_the_boot():
    with pytest.raises(MissingSetting):
        Config.from_env({})


def test_get_config_returns_the_same_instance(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)

    assert get_config() is get_config()
