"""Whole journeys through the HTTP API, as the UI drives them for a requester and the AV manager.

Run against a real SQL Server database (one per test). Journeys that cross
into the feedback service live with the cross-seam tests.
"""
from dataclasses import replace

import pytest

from avdesk_requests.composition import create_app
from avdesk_requests.config import Config

ADMIN_PASSWORD = "test-admin"
BRIEFING = {
    "requester_name": "Ana Souza", "requester_email": "ana@gobrasa.org", "diretoria_id": 4,
    "type_code": "teaser", "title": "Teaser BRASA Summit Europa", "campaign": "Summit Europa",
    "needed_by": "2026-12-01", "needed_by_reason": "Abertura das inscrições",
    "answers": {
        "objetivo": "Que estudantes queiram se inscrever", "mensagem_chave": "A conferência é sua",
        "publicos": ["Universitários no exterior"], "tom": "Inspirador (estilo Programa de Bolsas)",
        "referencia_tom": "Aftermovie de 2025", "destinos": ["Instagram"], "instagram_principal": "@brasasummiteuropa",
        "instagram_collab": ["@gobrasa"], "formatos": ["Vertical 9:16"],
        "aprovadores": "Diretoria de Conferências", "teaser_anuncio": "Inscrições abertas",
        "avaliadores": "Bruno Lima",
    },
}


@pytest.fixture
def client(empty_database, clock, tokens):
    config = Config.from_env({"DATABASE_URL": "mssql://placeholder:x@localhost/placeholder",
                              "ADMIN_PASSWORD": ADMIN_PASSWORD, "ADMIN_TOKEN_SECRET": "test-signing-key"})
    app = create_app(replace(config, database_url=empty_database.url), clock=clock, tokens=tokens)
    return app.test_client()


@pytest.fixture
def admin(client):
    token = client.post("/admin/session", json={"password": ADMIN_PASSWORD}).json["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def submitted(client):
    return client.post("/requests", json=BRIEFING).json


def act(client, admin, request_id, action, **inputs):
    return client.post(f"/admin/requests/{request_id}/actions", json={"action": action, **inputs}, headers=admin)


def request_id_of(client, admin, public_code) -> int:
    return next(r["id"] for r in client.get("/admin/requests", headers=admin).json if r["public_code"] == public_code)


# Requester

def test_the_catalog_lists_types_questions_and_diretorias(client):
    catalog = client.get("/catalog").json

    assert ([t["code"] for t in catalog["types"]][:1], len(catalog["diretorias"]), bool(catalog["questions"])) == \
        (["teaser"], 8, True)


def test_a_valid_briefing_returns_its_private_tracking_token(client):
    response = client.post("/requests", json=BRIEFING)

    assert (response.status_code, response.json["public_code"]) == (201, "AV-2026-0001")


def test_an_invalid_briefing_returns_the_field_errors(client):
    response = client.post("/requests", json={**BRIEFING, "requester_email": "ana@gmail.com"})

    assert (response.status_code, "requester_email" in response.json["errors"]) == (422, True)


def test_instagram_without_a_primary_account_is_rejected(client):
    answers = {k: v for k, v in BRIEFING["answers"].items() if k != "instagram_principal"}

    response = client.post("/requests", json={**BRIEFING, "answers": answers})

    assert "instagram_principal" in response.json["errors"]


def test_a_body_that_is_not_json_is_treated_as_an_empty_briefing(client):
    response = client.post("/requests", data="not json", content_type="text/plain")

    assert response.status_code == 422


def test_the_deadline_check_explains_rush_live(client):
    response = client.get("/deadline?type_code=teaser&needed_by=2026-10-12")

    assert (response.json["rush"], response.json["required_days"]) == (True, 10)


def test_the_deadline_check_needs_a_type_and_a_date(client):
    assert client.get("/deadline?type_code=teaser").status_code == 400


def test_the_tracking_view_hides_the_requester_email(client, submitted):
    tracked = client.get(f"/requests/by-token/{submitted['tracking_token']}").json

    assert (tracked["status"], "requester_email" in tracked["briefing"]) == ("submitted", False)


def test_an_unknown_tracking_token_is_a_404(client):
    assert client.get("/requests/by-token/nope").status_code == 404


def test_the_requester_sees_the_frameio_link_while_in_review(client, admin, submitted):
    request_id = request_id_of(client, admin, submitted["public_code"])
    act(client, admin, request_id, "accept", analyst_id=1)
    act(client, admin, request_id, "start_production")
    act(client, admin, request_id, "send_to_review", review_url="https://f.io/abc")

    tracked = client.get(f"/requests/by-token/{submitted['tracking_token']}").json

    assert (tracked["status"], tracked["review_url"]) == ("in_review", "https://f.io/abc")


def test_the_requester_completes_the_briefing_when_asked(client, admin, submitted):
    request_id = request_id_of(client, admin, submitted["public_code"])
    act(client, admin, request_id, "request_info", note="Falta o roteiro")

    response = client.put(f"/requests/by-token/{submitted['tracking_token']}/briefing",
                          json={**BRIEFING, "title": "Teaser com roteiro"})

    assert (response.json["status"], response.json["briefing"]["title"]) == ("submitted", "Teaser com roteiro")


def test_a_briefing_that_is_not_waiting_for_information_cannot_be_edited(client, submitted):
    response = client.put(f"/requests/by-token/{submitted['tracking_token']}/briefing", json=BRIEFING)

    assert response.status_code == 409


# AV manager

@pytest.mark.parametrize("path", ["/admin/requests", "/admin/requests/1", "/admin/workload", "/admin/metrics"])
def test_admin_endpoints_need_a_token(client, path):
    assert client.get(path).status_code == 401


def test_a_forged_token_is_refused(client):
    assert client.get("/admin/requests", headers={"Authorization": "Bearer forged"}).status_code == 401


def test_the_wrong_password_is_refused(client):
    assert client.post("/admin/session", json={"password": "nope"}).status_code == 401


def test_the_admin_sees_the_full_briefing_and_the_actions(client, admin, submitted):
    request_id = request_id_of(client, admin, submitted["public_code"])

    detail = client.get(f"/admin/requests/{request_id}", headers=admin).json

    assert (detail["briefing"]["requester_email"], [a["name"] for a in detail["actions"]][:1]) == \
        ("ana@gobrasa.org", ["accept"])


def test_a_missing_note_on_decline_is_reported_and_changes_nothing(client, admin, submitted):
    request_id = request_id_of(client, admin, submitted["public_code"])

    response = act(client, admin, request_id, "decline")

    assert (response.status_code, client.get(f"/admin/requests/{request_id}", headers=admin).json["status"]) == \
        (422, "submitted")


def test_an_action_that_is_not_allowed_now_is_a_conflict(client, admin, submitted):
    request_id = request_id_of(client, admin, submitted["public_code"])

    assert act(client, admin, request_id, "deliver", delivery_url="https://drive.google.com/x").status_code == 409


def test_the_last_change_can_be_undone(client, admin, submitted):
    request_id = request_id_of(client, admin, submitted["public_code"])
    act(client, admin, request_id, "request_info", note="Falta o roteiro")

    response = client.post(f"/admin/requests/{request_id}/undo", headers=admin)

    assert response.json["status"] == "submitted"


def test_acceptance_cannot_be_undone_because_it_created_a_task(client, admin, submitted):
    request_id = request_id_of(client, admin, submitted["public_code"])
    act(client, admin, request_id, "accept", analyst_id=1)

    assert client.post(f"/admin/requests/{request_id}/undo", headers=admin).status_code == 409


def test_workload_counts_open_requests_per_analyst(client, admin, submitted):
    act(client, admin, request_id_of(client, admin, submitted["public_code"]), "accept", analyst_id=1)

    analysts = client.get("/admin/workload", headers=admin).json["analysts"]

    assert next(a["open"] for a in analysts if a["id"] == 1) == 1


def test_the_inbox_filters_by_status(client, admin, submitted):
    assert client.get("/admin/requests?status=accepted", headers=admin).json == []


def test_metrics_count_requests_and_publish_scores(client, admin, submitted):
    metrics = client.get("/admin/metrics", headers=admin).json

    assert (metrics["total_requests"], list(metrics["briefing_scores"])) == (1, ["1"])
