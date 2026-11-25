"""The feedback HTTP API as a reviewer's link and the AV manager's pages use it, on a real SQL Server."""
from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

from avdesk_feedback.composition import create_app
from avdesk_feedback.config import Config
from avdesk_feedback.domain.facade import Recipient
from avdesk_feedback.domain.models import DeliveredWork
from avdesk_feedback.web.admin_guard import AdminTokens

TOKEN_SECRET = "test-signing-key"
WORK = DeliveredWork(42, "AV-2026-0042", "Teaser", "Teaser", "Conferências", "https://drive.google.com/x",
                     date(2026, 10, 20), datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc))
ANSWER = {"rating_tone": 5, "rating_quality": 4, "rating_process": "4", "rating_usefulness": 5,
          "outcome": "approved", "comment": "Ficou ótimo"}


@pytest.fixture
def app(empty_database, clock, tokens):
    config = Config.from_env({"DATABASE_URL": "mssql://placeholder:x@localhost/placeholder",
                              "ADMIN_TOKEN_SECRET": TOKEN_SECRET})
    return create_app(replace(config, database_url=empty_database.url), clock=clock, tokens=tokens)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def invite_tokens(app):
    invites = app.extensions["avdesk"].feedback.create_invites(WORK, [Recipient("Ana", True),
                                                                      Recipient("Bruno", False)])
    return [i.token for i in invites]


@pytest.fixture
def admin():
    return {"Authorization": f"Bearer {AdminTokens(TOKEN_SECRET, 60).issue()}"}


def test_an_open_invite_shows_the_delivered_video_and_the_form_choices(client, invite_tokens):
    body = client.get(f"/invites/{invite_tokens[0]}").json

    assert (body["state"], body["invite"]["public_code"], len(body["dimensions"])) == ("open", "AV-2026-0042", 4)


def test_an_unknown_invite_is_a_404(client):
    assert client.get("/invites/nope").status_code == 404


def test_a_complete_answer_is_stored(client, invite_tokens):
    assert client.post(f"/invites/{invite_tokens[0]}/response", json=ANSWER).status_code == 201


def test_an_invite_works_only_once(client, invite_tokens):
    client.post(f"/invites/{invite_tokens[0]}/response", json=ANSWER)

    response = client.post(f"/invites/{invite_tokens[0]}/response", json=ANSWER)

    assert (response.status_code, response.json["state"]) == (409, "used")


def test_a_used_invite_reports_its_state_instead_of_the_form(client, invite_tokens):
    client.post(f"/invites/{invite_tokens[0]}/response", json=ANSWER)

    assert client.get(f"/invites/{invite_tokens[0]}").json == {"state": "used"}


def test_an_expired_invite_is_closed(client, clock, invite_tokens):
    clock.advance(days=31)

    assert client.get(f"/invites/{invite_tokens[0]}").json["state"] == "expired"


def test_an_out_of_range_rating_is_rejected_with_field_errors(client, invite_tokens):
    response = client.post(f"/invites/{invite_tokens[0]}/response", json={**ANSWER, "rating_tone": 9})

    assert (response.status_code, list(response.json["errors"])) == (422, ["rating_tone"])


def test_a_boolean_is_not_accepted_as_a_rating(client, invite_tokens):
    response = client.post(f"/invites/{invite_tokens[0]}/response", json={**ANSWER, "rating_tone": True})

    assert "rating_tone" in response.json["errors"]


@pytest.mark.parametrize("path", ["/admin/requests/42/invites", "/admin/metrics"])
def test_admin_views_need_a_token_from_the_requests_service(client, path):
    assert client.get(path).status_code == 401


def test_a_token_signed_with_another_key_is_refused(client):
    forged = {"Authorization": f"Bearer {AdminTokens('other-key', 60).issue()}"}

    assert client.get("/admin/metrics", headers=forged).status_code == 401


def test_the_admin_sees_each_invite_and_whether_it_was_answered(client, admin, invite_tokens):
    client.post(f"/invites/{invite_tokens[0]}/response", json=ANSWER)

    invites = client.get("/admin/requests/42/invites", headers=admin).json

    assert [(i["recipient_label"], i["used_at"] is not None) for i in invites] == [("Ana", True), ("Bruno", False)]


def test_metrics_report_outcomes_ratings_and_the_requester_verdicts(client, admin, invite_tokens):
    client.post(f"/invites/{invite_tokens[0]}/response", json=ANSWER)

    metrics = client.get("/admin/metrics", headers=admin).json

    assert (metrics["response_rate"], metrics["ratings_by_type"]["Teaser"]["rating_tone"],
            metrics["requester_outcomes"]) == (0.5, 5, {"42": "approved"})
