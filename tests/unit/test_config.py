from pathlib import Path

import pytest

from avdesk.config import Config, get_config, reset_config


@pytest.fixture(autouse=True)
def fresh_singleton():
    reset_config()
    yield
    reset_config()


def test_defaults_apply_when_environment_is_empty():
    config = Config.from_env({})

    assert (config.port, config.data_dir, config.feedback_ttl_days) == (8000, Path("data"), 30)


def test_port_and_data_dir_are_read_from_environment():
    config = Config.from_env({"PORT": "9123", "DATA_DIR": "/data"})

    assert (config.port, config.data_dir) == (9123, Path("/data"))


def test_database_lives_inside_data_dir():
    config = Config.from_env({"DATA_DIR": "/data"})

    assert config.database_path == Path("/data/avdesk.sqlite3")


def test_missing_admin_password_falls_back_to_an_insecure_default():
    config = Config.from_env({})

    assert config.admin_password_is_default


def test_secret_key_is_derived_from_admin_password_when_unset():
    first = Config.from_env({"ADMIN_PASSWORD": "a"})
    second = Config.from_env({"ADMIN_PASSWORD": "b"})

    assert first.secret_key != second.secret_key


def test_clickup_is_enabled_only_when_token_and_list_are_both_set():
    only_token = Config.from_env({"CLICKUP_API_TOKEN": "pk_x"})
    both = Config.from_env({"CLICKUP_API_TOKEN": "pk_x", "CLICKUP_LIST_ID": "123"})

    assert (only_token.clickup_enabled, both.clickup_enabled) == (False, True)


def test_get_config_returns_the_same_instance(monkeypatch):
    monkeypatch.setenv("PORT", "8100")

    assert get_config() is get_config()


def test_reset_config_rereads_the_environment(monkeypatch):
    monkeypatch.setenv("PORT", "8100")
    before = get_config()
    monkeypatch.setenv("PORT", "8200")
    reset_config()

    assert (before.port, get_config().port) == (8100, 8200)
