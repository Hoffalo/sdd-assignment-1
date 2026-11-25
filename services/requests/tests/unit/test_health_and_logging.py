import logging

import pytest

from avdesk_requests.health import HealthProbe
from avdesk_requests.web import create_web_app

VERSION = "4f2c9e1"


class StubProbe(HealthProbe):
    def __init__(self, healthy: bool):
        self.healthy = healthy

    def database_is_healthy(self) -> bool:
        return self.healthy


def client_with(healthy: bool):
    return create_web_app(StubProbe(healthy), version=VERSION).test_client()


def test_health_is_ok_when_the_database_answers():
    response = client_with(healthy=True).get("/health")

    assert (response.status_code, response.json) == (200, {"status": "ok", "db": "ok", "version": VERSION})


def test_health_is_unavailable_when_the_database_does_not_answer():
    response = client_with(healthy=False).get("/health")

    assert (response.status_code, response.json["db"]) == (503, "unavailable")


def test_every_request_is_logged_with_method_path_status_and_duration(caplog):
    with caplog.at_level(logging.INFO, logger="avdesk_requests.web.request_log"):
        client_with(healthy=True).get("/health")

    [line] = [r.getMessage() for r in caplog.records if r.name == "avdesk_requests.web.request_log"]
    assert line.startswith("GET /health 200 ") and line.endswith("ms")


@pytest.mark.parametrize("healthy, status", [(True, 200), (False, 503)])
def test_failed_requests_are_logged_too(caplog, healthy, status):
    with caplog.at_level(logging.INFO, logger="avdesk_requests.web.request_log"):
        client_with(healthy).get("/health")

    assert f"GET /health {status} " in caplog.text
