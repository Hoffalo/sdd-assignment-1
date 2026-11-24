import pytest

from avdesk_requests.web import create_web_app
from avdesk_requests.web.admin_guard import AdminOnly, AdminRequired, AdminTokens, bearer_token, password_matches
from tests.unit.test_health_and_logging import StubProbe

UI_ORIGIN = "https://avdeskui.z28.web.core.windows.net"


@pytest.fixture
def client():
    return create_web_app(StubProbe(True), version="x", cors_origin=UI_ORIGIN).test_client()


def test_the_ui_origin_may_read_responses(client):
    response = client.get("/health", headers={"Origin": UI_ORIGIN})

    assert response.headers["Access-Control-Allow-Origin"] == UI_ORIGIN


def test_any_other_origin_gets_no_cors_header(client):
    response = client.get("/health", headers={"Origin": "https://evil.example"})

    assert "Access-Control-Allow-Origin" not in response.headers


def test_a_preflight_from_the_ui_allows_the_authorization_header(client):
    response = client.options("/admin/requests", headers={"Origin": UI_ORIGIN,
                                                          "Access-Control-Request-Method": "GET"})

    assert (response.status_code, "Authorization" in response.headers["Access-Control-Allow-Headers"]) == \
        (204, True)


def test_responses_vary_by_origin_so_caches_do_not_mix_them(client):
    assert "Origin" in client.get("/health").headers["Vary"]


def test_an_issued_token_is_valid():
    tokens = AdminTokens("secret", ttl_seconds=60)

    assert tokens.is_valid(tokens.issue())


def test_a_token_signed_with_another_secret_is_rejected():
    assert not AdminTokens("secret", 60).is_valid(AdminTokens("other", 60).issue())


def test_an_expired_token_is_rejected():
    tokens = AdminTokens("secret", ttl_seconds=-1)

    assert not tokens.is_valid(tokens.issue())


@pytest.mark.parametrize("header, token", [("Bearer abc", "abc"), ("bearer abc", "abc"), ("Basic abc", None),
                                           ("Bearer ", None), (None, None)])
def test_only_a_bearer_header_carries_a_token(header, token):
    assert bearer_token(header) == token


def test_the_password_is_compared_exactly():
    assert (password_matches("pw", "pw"), password_matches("pw ", "pw")) == (True, False)


def test_the_proxy_forwards_calls_for_the_admin(mocker):
    target = mocker.Mock()
    target.inbox.return_value = ["row"]

    assert AdminOnly(target, lambda: True).inbox() == ["row"]


def test_the_proxy_refuses_everyone_else(mocker):
    with pytest.raises(AdminRequired):
        AdminOnly(mocker.Mock(), lambda: False).inbox()
