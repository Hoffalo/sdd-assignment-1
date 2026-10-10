def test_landing_answers_without_login(client):
    response = client.get("/")

    assert response.status_code == 200


def test_healthz_reports_ok(client):
    response = client.get("/healthz")

    assert response.get_json() == {"status": "ok"}
