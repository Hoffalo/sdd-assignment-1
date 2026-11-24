"""The seam endpoints of the feedback service, with the requests service replaced by a stub.

A reviewer's answer must be stored whether or not the requests service answers;
the cross-seam test at the repository root runs both real services together.
"""
from dataclasses import replace

import pytest

from avdesk_feedback.composition import create_app
from avdesk_feedback.config import Config
from avdesk_feedback.domain.models import Outcome
from avdesk_feedback.requests_client import RequestsUnavailable
from avdesk_feedback.web.admin_guard import SERVICE_CLAIM, AdminTokens
from tests.integration.test_api import ANSWER, TOKEN_SECRET

INVITES_BODY = {
    "work": {"request_id": 42, "public_code": "AV-2026-0042", "title": "Teaser", "type_label": "Teaser",
             "diretoria": "Conferências", "delivery_url": "https://drive.google.com/x", "needed_by": "2026-10-20",
             "delivered_at": "2026-10-09T12:00:00+00:00"},
    "recipients": [{"label": "Ana", "is_requester": True}, {"label": "Bruno", "is_requester": False}],
}


class SwitchableRequests:
    """A requests service that can be taken down and brought back between calls."""

    def __init__(self):
        self.up = True
        self.sent = []

    def send_verdict(self, request_id, outcome):
        if not self.up:
            raise RequestsUnavailable("requests is down")
        self.sent.append((request_id, outcome))


@pytest.fixture
def requests_service():
    return SwitchableRequests()


@pytest.fixture
def client(empty_database, clock, tokens, requests_service):
    config = Config.from_env({"DATABASE_URL": "mssql://placeholder:x@localhost/placeholder",
                              "ADMIN_TOKEN_SECRET": TOKEN_SECRET})
    app = create_app(replace(config, database_url=empty_database.url), clock=clock, tokens=tokens,
                     verdicts=requests_service)
    return app.test_client()


@pytest.fixture
def admin():
    return {"Authorization": f"Bearer {AdminTokens(TOKEN_SECRET, 60).issue()}"}


@pytest.fixture
def service():
    return {"Authorization": f"Bearer {AdminTokens(TOKEN_SECRET, 300, SERVICE_CLAIM).issue()}"}


@pytest.fixture
def invites(client, service):
    return client.post("/invites", json=INVITES_BODY, headers=service).json


def answer(client, invite):
    return client.post(f"/invites/{invite['token']}/response", json=ANSWER)


def admin_invites(client, admin):
    return client.get("/admin/requests/42/invites", headers=admin).json


# Requests -> Feedback

def test_a_delivery_creates_one_invite_per_person(client, service):
    response = client.post("/invites", json=INVITES_BODY, headers=service)

    assert (response.status_code, [(i["recipient_label"], i["is_requester"]) for i in response.json]) == (
        201, [("Ana", True), ("Bruno", False)])


def test_the_same_delivery_sent_twice_keeps_the_first_invites(client, service, invites):
    again = client.post("/invites", json=INVITES_BODY, headers=service).json

    assert [i["token"] for i in again] == [i["token"] for i in invites]


def test_a_new_delivery_after_changes_gets_new_invites(client, service, invites):
    redelivered = {**INVITES_BODY, "work": {**INVITES_BODY["work"], "delivered_at": "2026-10-15T09:00:00+00:00"}}

    again = client.post("/invites", json=redelivered, headers=service).json

    assert not {i["token"] for i in again} & {i["token"] for i in invites}


@pytest.mark.parametrize("body", [{}, {"work": INVITES_BODY["work"], "recipients": []},
                                  {**INVITES_BODY, "work": {**INVITES_BODY["work"], "needed_by": "soon"}}])
def test_a_malformed_delivery_is_rejected(client, service, body):
    assert client.post("/invites", json=body, headers=service).status_code == 422


def test_creating_invites_needs_a_service_token(client):
    assert client.post("/invites", json=INVITES_BODY).status_code == 401


def test_an_admin_token_cannot_create_invites(client, admin):
    assert client.post("/invites", json=INVITES_BODY, headers=admin).status_code == 401


# Feedback -> Requests

def test_the_requesters_answer_reaches_the_requests_service(client, requests_service, invites):
    answer(client, invites[0])

    assert requests_service.sent == [(42, Outcome.APPROVED)]


def test_a_reviewers_answer_does_not(client, requests_service, invites):
    answer(client, invites[1])

    assert requests_service.sent == []


def test_the_answer_is_stored_even_when_the_requests_service_is_down(client, requests_service, invites):
    requests_service.up = False

    assert answer(client, invites[0]).status_code == 201


def test_an_undelivered_verdict_shows_as_pending_to_the_manager(client, admin, requests_service, invites):
    requests_service.up = False
    answer(client, invites[0])

    assert [i["verdict_pending"] for i in admin_invites(client, admin)] == [True, False]


def test_resending_once_the_requests_service_is_back_clears_the_flag(client, admin, requests_service, invites):
    requests_service.up = False
    answer(client, invites[0])
    requests_service.up = True

    response = client.post("/admin/requests/42/verdict", headers=admin)

    assert ([i["verdict_pending"] for i in response.json], requests_service.sent) == (
        [False, False], [(42, Outcome.APPROVED)])


def test_resending_with_nothing_pending_sends_nothing(client, admin, requests_service, invites):
    response = client.post("/admin/requests/42/verdict", headers=admin)

    assert (response.status_code, requests_service.sent) == (200, [])


def test_resending_needs_the_admin(client):
    assert client.post("/admin/requests/42/verdict").status_code == 401
