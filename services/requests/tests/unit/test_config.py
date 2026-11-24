import pytest

from avdesk_requests.config import Config, MissingSetting, get_config, reset_config


@pytest.fixture(autouse=True)
def fresh_singleton():
    reset_config()
    yield
    reset_config()


DATABASE_URL = "mssql://requests_app:pw@sql:1433/requests"
BASE = {"DATABASE_URL": DATABASE_URL}


def test_defaults_apply_when_only_the_database_is_given():
    config = Config.from_env(BASE)

    assert (config.port, config.version, config.approval_buffer_days) == (8000, "dev", 3)


def test_port_is_read_from_environment():
    assert Config.from_env({**BASE, "PORT": "9123"}).port == 9123


def test_the_database_comes_from_database_url():
    assert Config.from_env(BASE).database_url.database == "requests"


def test_a_missing_database_url_stops_the_boot():
    with pytest.raises(MissingSetting):
        Config.from_env({})


def test_the_version_is_the_commit_the_image_was_built_from():
    assert Config.from_env({**BASE, "GIT_SHA": "abc123"}).version == "abc123"


def test_missing_admin_password_falls_back_to_an_insecure_default():
    config = Config.from_env(BASE)

    assert config.admin_password_is_default


def test_secret_key_is_derived_from_admin_password_when_unset():
    first = Config.from_env({**BASE, "ADMIN_PASSWORD": "a"})
    second = Config.from_env({**BASE, "ADMIN_PASSWORD": "b"})

    assert first.secret_key != second.secret_key


def test_clickup_is_enabled_only_when_token_and_list_are_both_set():
    only_token = Config.from_env({**BASE, "CLICKUP_API_TOKEN": "pk_x"})
    both = Config.from_env({**BASE, "CLICKUP_API_TOKEN": "pk_x", "CLICKUP_LIST_ID": "123"})

    assert (only_token.clickup_enabled, both.clickup_enabled) == (False, True)


def test_get_config_returns_the_same_instance(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("PORT", "8100")

    assert get_config() is get_config()


def test_reset_config_rereads_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("PORT", "8100")
    before = get_config()
    monkeypatch.setenv("PORT", "8200")
    reset_config()

    assert (before.port, get_config().port) == (8100, 8200)
