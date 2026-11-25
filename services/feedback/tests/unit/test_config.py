import pytest

from avdesk_feedback.config import Config, MissingSetting, get_config, reset_config

DATABASE_URL = "mssql://feedback_app:pw@sql:1433/feedback"
BASE = {"DATABASE_URL": DATABASE_URL, "ADMIN_TOKEN_SECRET": "signing-key"}


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


@pytest.mark.parametrize("secret", ["DATABASE_URL", "ADMIN_TOKEN_SECRET"])
def test_every_secret_is_required(secret):
    with pytest.raises(MissingSetting):
        Config.from_env({k: v for k, v in BASE.items() if k != secret})


def test_cors_defaults_to_the_local_ui_origin():
    assert Config.from_env(BASE).cors_origin == "http://localhost:8080"


def test_get_config_returns_the_same_instance(monkeypatch):
    for key, value in BASE.items():
        monkeypatch.setenv(key, value)

    assert get_config() is get_config()
