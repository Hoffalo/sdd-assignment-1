"""Whole journeys through HTTP, as a requester, the AV manager and a reviewer would click them."""
import re

import pytest

from avdesk.requests_domain.models import Status
from tests.conftest import ADMIN_PASSWORD

BRIEFING_FORM = {
    "requester_name": "Ana Souza", "requester_email": "ana@gobrasa.org", "diretoria_id": "4",
    "type_code": "teaser", "title": "Teaser BRASA Summit Europa", "campaign": "Summit Europa",
    "needed_by": "2026-12-01", "needed_by_reason": "Abertura das inscrições",
    "q_objetivo": "Que estudantes queiram se inscrever", "q_mensagem_chave": "A conferência é sua",
    "q_publicos": ["Universitários no exterior"], "q_tom": "Inspirador (estilo Programa de Bolsas)",
    "q_referencia_tom": "Aftermovie de 2025", "q_destinos": ["Instagram"], "q_formatos": ["Vertical 9:16"],
    "q_aprovadores": "Diretoria de Conferências", "q_teaser_anuncio": "Inscrições abertas",
    "q_avaliadores": "Bruno Lima",
}
RATINGS = {"rating_tone": "5", "rating_quality": "5", "rating_process": "4", "rating_usefulness": "5"}


def csrf(client) -> str:
    with client.session_transaction() as session:
        session.setdefault("csrf_token", "test-csrf")
        return session["csrf_token"]


def post(client, url, data=None, **kwargs):
    return client.post(url, data={**(data or {}), "csrf_token": csrf(client)}, **kwargs)


def login(client):
    return post(client, "/admin/login", {"password": ADMIN_PASSWORD})


def submit_briefing(client, **overrides) -> str:
    response = post(client, "/pedido/novo", {**BRIEFING_FORM, **overrides})
    assert response.status_code == 302, response.get_data(as_text=True)
    return response.headers["Location"].rsplit("/", 1)[-1]


def act(client, request_id, action, **fields):
    return post(client, f"/admin/pedidos/{request_id}/acao", {"action": action, **fields})


def requests_facade(app):
    return app.extensions["avdesk"].requests


@pytest.fixture
def delivered(app, client):
    token = submit_briefing(client)
    request_id = requests_facade(app).by_token(token).id
    login(client)
    act(client, request_id, "accept", analyst_id="2")
    act(client, request_id, "start_production")
    act(client, request_id, "deliver", delivery_url="https://drive.google.com/final")
    return request_id


def invite_links(client, request_id) -> list[str]:
    page = client.get(f"/admin/pedidos/{request_id}").get_data(as_text=True)
    return re.findall(r'data-copy="http://localhost(/feedback/[^"]+)"', page)


def test_new_briefing_redirects_to_its_private_tracking_page(client):
    token = submit_briefing(client)

    page = client.get(f"/pedido/{token}").get_data(as_text=True)

    assert "Teaser BRASA Summit Europa" in page and "Recebido" in page


def test_invalid_briefing_is_shown_again_with_messages(client):
    response = post(client, "/pedido/novo", {**BRIEFING_FORM, "requester_email": "ana@gmail.com"})

    assert response.status_code == 422 and "@gobrasa.org" in response.get_data(as_text=True)


def test_deadline_check_explains_rush_live(client):
    result = client.get("/pedido/prazo?type_code=teaser&needed_by=2026-10-14").get_json()

    assert (result["rush"], result["earliest_date"]) == (True, "23/10/2026")


def test_full_happy_path_closes_the_request(app, client, delivered):
    requester_link, _reviewer_link = invite_links(client, delivered)

    response = post(client, requester_link, {**RATINGS, "outcome": "approved"})

    assert "Muito obrigado" in response.get_data(as_text=True)
    assert requests_facade(app).get(delivered).status == Status.CLOSED


def test_major_changes_from_the_requester_reopen_production(app, client, delivered):
    requester_link, _ = invite_links(client, delivered)

    post(client, requester_link, {**RATINGS, "outcome": "major_changes"})

    assert requests_facade(app).get(delivered).status == Status.IN_PRODUCTION


def test_feedback_link_works_only_once(client, delivered):
    requester_link, _ = invite_links(client, delivered)
    post(client, requester_link, {**RATINGS, "outcome": "approved"})

    second = post(client, requester_link, {**RATINGS, "outcome": "approved"})

    assert second.status_code == 200 and "já foi usado" in second.get_data(as_text=True)


def test_expired_feedback_link_shows_a_friendly_page(client, clock, delivered):
    requester_link, _ = invite_links(client, delivered)
    clock.advance(days=31)

    response = client.get(requester_link)

    assert response.status_code == 200 and "expirou" in response.get_data(as_text=True)


def test_out_of_range_rating_is_rejected(client, delivered):
    requester_link, _ = invite_links(client, delivered)

    response = post(client, requester_link, {**RATINGS, "rating_tone": "7", "outcome": "approved"})

    assert response.status_code == 422


def test_requester_completes_the_briefing_when_asked(app, client):
    token = submit_briefing(client)
    request_id = requests_facade(app).by_token(token).id
    login(client)
    act(client, request_id, "request_info", note="Qual é a referência de tom?")

    post(client, f"/pedido/{token}", {**BRIEFING_FORM, "q_referencia_tom": "Vídeo do PdB 2025"})

    assert requests_facade(app).get(request_id).status == Status.SUBMITTED


@pytest.mark.parametrize("path", ["/admin", "/admin/metricas", "/admin/pedidos/1"])
def test_admin_pages_redirect_to_login_when_logged_out(client, path):
    response = client.get(path)

    assert response.status_code == 302 and "/admin/login" in response.headers["Location"]


def test_wrong_password_is_refused(client):
    assert post(client, "/admin/login", {"password": "errada"}).status_code == 401


def test_post_without_csrf_token_is_rejected(client):
    assert client.post("/pedido/novo", data=BRIEFING_FORM).status_code == 400


def test_admin_sees_inbox_and_metrics(client, delivered):
    inbox = client.get("/admin").get_data(as_text=True)
    metrics = client.get("/admin/metricas")

    assert "Teaser BRASA Summit Europa" in inbox and metrics.status_code == 200


def test_missing_note_on_decline_is_reported_and_changes_nothing(app, client):
    token = submit_briefing(client)
    request_id = requests_facade(app).by_token(token).id
    login(client)

    act(client, request_id, "decline", note="")

    assert requests_facade(app).get(request_id).status == Status.SUBMITTED


def test_unknown_tracking_token_is_a_404(client):
    assert client.get("/pedido/nao-existe").status_code == 404
