"""Starts both services for real: two databases, two HTTP servers on free ports.

The service packages are not installed, so their folders are put on the
import path here. Their own test packages are never imported: all three
suites are named `tests`, and CI runs each one separately.
"""
import json
import os
import socket
import sys
import threading
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services" / "requests"), str(ROOT / "services" / "feedback")]

from avdesk_feedback import composition as feedback_composition  # noqa: E402
from avdesk_feedback.config import Config as FeedbackConfig  # noqa: E402
from avdesk_feedback.database import DatabaseUrl as FeedbackDatabaseUrl  # noqa: E402
from avdesk_requests import composition as requests_composition  # noqa: E402
from avdesk_requests.config import Config as RequestsConfig  # noqa: E402
from avdesk_requests.database import Database, DatabaseUrl, RetryPolicy  # noqa: E402

SERVER_URL_ENV = "TEST_SQLSERVER_URL"
SIGNING_KEY = "cross-seam-signing-key"
ADMIN_PASSWORD = "cross-seam-admin"
PLACEHOLDER_DB = "mssql://placeholder:x@localhost/placeholder"
TEST_RETRY = RetryPolicy(attempts=2, first_delay_s=1, max_delay_s=1)
# The services run on the real clock here, so the date must stay comfortably
# beyond every lead time (a rush request would also need a rush reason).
NEEDED_BY = (date.today() + timedelta(days=120)).isoformat()
BRIEFING = {
    "requester_name": "Ana Souza", "requester_email": "ana@gobrasa.org", "diretoria_id": 4,
    "type_code": "teaser", "title": "Teaser BRASA Summit Europa", "campaign": "Summit Europa",
    "needed_by": NEEDED_BY, "needed_by_reason": "Abertura das inscrições",
    "answers": {
        "objetivo": "Que estudantes queiram se inscrever", "mensagem_chave": "A conferência é sua",
        "publicos": ["Universitários no exterior"], "tom": "Inspirador (estilo Programa de Bolsas)",
        "referencia_tom": "Aftermovie de 2025", "destinos": ["Instagram"], "instagram_principal": "@brasasummiteuropa",
        "instagram_collab": ["@gobrasa"], "formatos": ["Vertical 9:16"],
        "aprovadores": "Diretoria de Conferências", "teaser_anuncio": "Inscrições abertas",
        "avaliadores": "Bruno Lima",
    },
}


def call(method: str, url: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, object]:
    request = urllib.request.Request(url, method=method, headers={"Content-Type": "application/json", **(headers or {})},
                                     data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class ServedApp:
    """One service on a fixed port that a test can stop and start again, as an outage."""

    def __init__(self, app, port: int):
        self._app = app
        self._port = port
        self._server = None
        self.url = f"http://127.0.0.1:{port}"

    def start(self) -> None:
        self._server = make_server("127.0.0.1", self._port, self._app, threaded=True)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


@pytest.fixture
def sql_server() -> Database:
    raw_url = os.environ.get(SERVER_URL_ENV)
    if not raw_url:
        pytest.skip(f"{SERVER_URL_ENV} is not set; the cross-seam tests need a SQL Server")
    return Database(DatabaseUrl.parse(raw_url), retry=TEST_RETRY, autocommit=True)


@pytest.fixture
def database_urls(sql_server):
    names = [f"avdesk_cross_{side}_{uuid.uuid4().hex[:10]}" for side in ("requests", "feedback")]
    with sql_server.connect() as session:
        for name in names:
            session.execute(f"CREATE DATABASE [{name}]")
    yield [sql_server.url.with_database(name) for name in names]
    with sql_server.connect() as session:
        for name in names:
            session.execute(f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
            session.execute(f"DROP DATABASE [{name}]")


@pytest.fixture
def ports():
    return free_port(), free_port()


@pytest.fixture
def requests(database_urls, ports):
    requests_port, feedback_port = ports
    config = RequestsConfig.from_env({"DATABASE_URL": PLACEHOLDER_DB, "ADMIN_PASSWORD": ADMIN_PASSWORD,
                                      "ADMIN_TOKEN_SECRET": SIGNING_KEY,
                                      "FEEDBACK_URL": f"http://127.0.0.1:{feedback_port}"})
    served = ServedApp(requests_composition.create_app(replace(config, database_url=database_urls[0])), requests_port)
    served.start()
    yield served
    served.stop()


@pytest.fixture
def feedback(database_urls, ports):
    requests_port, feedback_port = ports
    config = FeedbackConfig.from_env({"DATABASE_URL": PLACEHOLDER_DB, "ADMIN_TOKEN_SECRET": SIGNING_KEY,
                                      "REQUESTS_URL": f"http://127.0.0.1:{requests_port}"})
    # Each service has its own DatabaseUrl class (no shared code); same fields.
    feedback_url = FeedbackDatabaseUrl(**asdict(database_urls[1]))
    served = ServedApp(feedback_composition.create_app(replace(config, database_url=feedback_url)), feedback_port)
    served.start()
    yield served
    served.stop()


@pytest.fixture
def admin_headers(requests) -> dict:
    token = call("POST", f"{requests.url}/admin/session", {"password": ADMIN_PASSWORD})[1]["token"]
    return {"Authorization": f"Bearer {token}"}
