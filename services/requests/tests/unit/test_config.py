import pytest

from avdesk_requests.config import Config, MissingSetting, get_config, reset_config


@pytest.fixture(autouse=True)
def fresh_singleton():
    reset_config()
    yield
    reset_config()


DATABASE_URL = "mssql://requests_app:pw@sql:1433/requests"
BASE = {"DATABASE_URL": DATABASE_URL, "ADMIN_PASSWORD": "pw", "ADMIN_TOKEN_SECRET": "signing-key"}


def test_defaults_apply_when_only_the_database_is_given():
    config = Config.from_env(BASE)

    assert (config.port, config.version, config.approval_buffer_days) == (8000, "dev", 3)


def test_port_is_read_from_environment():
    assert Config.from_env({**BASE, "PORT": "9123"}).port == 9123


def test_the_database_comes_from_database_url():
    assert Config.from_env(BASE).database_url.database == "requests"


def test_the_version_is_the_commit_the_image_was_built_from():
    assert Config.from_env({**BASE, "GIT_SHA": "abc123"}).version == "abc123"


@pytest.mark.parametrize("secret", ["DATABASE_URL", "ADMIN_PASSWORD", "ADMIN_TOKEN_SECRET"])
def test_every_secret_is_required(secret):
    env = {k: v for k, v in BASE.items() if k != secret}

    with pytest.raises(MissingSetting):
        Config.from_env(env)


def test_cors_defaults_to_the_local_ui_origin():
    assert Config.from_env(BASE).cors_origin == "http://localhost:8080"


def test_cors_origin_is_read_from_environment():
    assert Config.from_env({**BASE, "CORS_ORIGIN": "https://x.web.core.windows.net"}).cors_origin ==         "https://x.web.core.windows.net"


def test_clickup_is_enabled_only_when_token_and_list_are_both_set():
    only_token = Config.from_env({**BASE, "CLICKUP_API_TOKEN": "pk_x"})
    both = Config.from_env({**BASE, "CLICKUP_API_TOKEN": "pk_x", "CLICKUP_LIST_ID": "123"})

    assert (only_token.clickup_enabled, both.clickup_enabled) == (False, True)


def test_get_config_returns_the_same_instance(monkeypatch):
    for key, value in BASE.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("PORT", "8100")

    assert get_config() is get_config()


def test_reset_config_rereads_the_environment(monkeypatch):
    for key, value in BASE.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("PORT", "8100")
    before = get_config()
    monkeypatch.setenv("PORT", "8200")
    reset_config()

    assert (before.port, get_config().port) == (8100, 8200)
