"""The seam endpoints of the requests service, with the feedback service replaced by a stub.

Delivering must work whether or not the feedback service answers; the cross-seam
test at the repository root runs both real services together.
"""
from dataclasses import replace

import pytest

from avdesk_requests.composition import create_app
from avdesk_requests.config import Config
from avdesk_requests.feedback_client import FeedbackUnavailable
from avdesk_requests.web.admin_guard import SERVICE_CLAIM, AdminTokens
from tests.integration.test_api_journeys import ADMIN_PASSWORD, BRIEFING, act, request_id_of

SIGNING_KEY = "test-signing-key"


class SwitchableFeedback:
    """A feedback service that can be taken down and brought back between calls."""

    def __init__(self):
        self.up = True
        self.snapshots = []

    def create_invites(self, snapshot):
        if not self.up:
            raise FeedbackUnavailable("feedback is down")
        self.snapshots.append(snapshot)


@pytest.fixture
def feedback():
    return SwitchableFeedback()


@pytest.fixture
def client(empty_database, clock, tokens, feedback):
    config = Config.from_env({"DATABASE_URL": "mssql://placeholder:x@localhost/placeholder",
                              "ADMIN_PASSWORD": ADMIN_PASSWORD, "ADMIN_TOKEN_SECRET": SIGNING_KEY})
    app = create_app(replace(config, database_url=empty_database.url), clock=clock, tokens=tokens,
                     feedback=feedback)
    return app.test_client()


@pytest.fixture
def admin(client):
    token = client.post("/admin/session", json={"password": ADMIN_PASSWORD}).json["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def service():
    return {"Authorization": f"Bearer {AdminTokens(SIGNING_KEY, 300, SERVICE_CLAIM).issue()}"}


@pytest.fixture
def in_production(client, admin):
    request_id = request_id_of(client, admin, client.post("/requests", json=BRIEFING).json["public_code"])
    act(client, admin, request_id, "accept", analyst_id=2)
    act(client, admin, request_id, "start_production")
    return request_id


def deliver(client, admin, request_id):
    return act(client, admin, request_id, "deliver", delivery_url="https://drive.google.com/final")


@pytest.fixture
def delivered(client, admin, in_production):
    deliver(client, admin, in_production)
    return in_production


# Requests -> Feedback

def test_delivery_sends_the_request_to_the_feedback_service(feedback, delivered):
    assert [(s.request_id, s.reviewers) for s in feedback.snapshots] == [(delivered, ("Bruno Lima",))]


def test_delivery_still_succeeds_when_the_feedback_service_is_down(client, admin, feedback, in_production):
    feedback.up = False

    response = deliver(client, admin, in_production)

    assert (response.status_code, response.json["status"], response.json["invites_pending"]) == (
        200, "delivered", True)


def test_retrying_once_the_feedback_service_is_back_clears_the_pending_flag(client, admin, feedback,
                                                                             in_production):
    feedback.up = False
    deliver(client, admin, in_production)
    feedback.up = True

    response = client.post(f"/admin/requests/{in_production}/invites", headers=admin)

    assert (response.json["invites_pending"], len(feedback.snapshots)) == (False, 1)


def test_a_retry_that_fails_again_keeps_the_flag(client, admin, feedback, in_production):
    feedback.up = False
    deliver(client, admin, in_production)

    response = client.post(f"/admin/requests/{in_production}/invites", headers=admin)

    assert (response.status_code, response.json["invites_pending"]) == (200, True)


def test_invites_cannot_be_retried_before_delivery(client, admin, in_production):
    response = client.post(f"/admin/requests/{in_production}/invites", headers=admin)

    assert response.status_code == 409


def test_retrying_invites_needs_the_admin(client, delivered):
    response = client.post(f"/admin/requests/{delivered}/invites")

    assert response.status_code == 401


# Feedback -> Requests

def test_an_approving_verdict_closes_the_delivered_request(client, service, delivered):
    response = client.post(f"/requests/{delivered}/verdict", json={"verdict": "approved"}, headers=service)

    assert (response.status_code, response.json["status"]) == (200, "closed")


def test_a_major_changes_verdict_reopens_the_request(client, service, delivered):
    response = client.post(f"/requests/{delivered}/verdict", json={"verdict": "major_changes"}, headers=service)

    assert response.json["status"] == "in_production"


def test_the_verdict_shows_on_the_timeline_as_coming_from_the_feedback(client, admin, service, delivered):
    client.post(f"/requests/{delivered}/verdict", json={"verdict": "approved"}, headers=service)

    last = client.get(f"/admin/requests/{delivered}", headers=admin).json["timeline"][-1]
    assert (last["actor"], last["note"]) == ("avaliação", "Avaliação: aprovado.")


def test_a_verdict_for_a_request_the_manager_already_moved_changes_nothing(client, service, in_production):
    response = client.post(f"/requests/{in_production}/verdict", json={"verdict": "approved"}, headers=service)

    assert (response.status_code, response.json["status"]) == (200, "in_production")


def test_sending_the_same_verdict_twice_is_harmless(client, service, delivered):
    client.post(f"/requests/{delivered}/verdict", json={"verdict": "approved"}, headers=service)

    response = client.post(f"/requests/{delivered}/verdict", json={"verdict": "approved"}, headers=service)

    assert (response.status_code, response.json["status"]) == (200, "closed")


def test_an_unknown_verdict_is_rejected(client, service, delivered):
    response = client.post(f"/requests/{delivered}/verdict", json={"verdict": "maybe"}, headers=service)

    assert (response.status_code, response.json["field"]) == (422, "verdict")


def test_a_verdict_for_an_unknown_request_is_not_found(client, service):
    response = client.post("/requests/999/verdict", json={"verdict": "approved"}, headers=service)

    assert response.status_code == 404


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer forged"}])
def test_verdicts_need_a_service_token(client, delivered, headers):
    response = client.post(f"/requests/{delivered}/verdict", json={"verdict": "approved"}, headers=headers)

    assert response.status_code == 401


def test_an_admin_token_is_not_a_service_token(client, admin, delivered):
    response = client.post(f"/requests/{delivered}/verdict", json={"verdict": "approved"}, headers=admin)

    assert response.status_code == 401
