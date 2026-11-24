"""HTTP glue of the feedback service: turns requests into facade calls and back.

Assembled here from already-built collaborators, so tests can create the
Flask app with stubs and no database; choosing concrete classes is the
composition root's job.
"""
from flask import Flask, jsonify

from avdesk_feedback.health import HealthProbe
from avdesk_feedback.web import request_log


def create_web_app(health_probe: HealthProbe, version: str) -> Flask:
    app = Flask(__name__)
    request_log.install(app)

    @app.get("/health")
    def health():
        if health_probe.database_is_healthy():
            return jsonify(status="ok", db="ok", version=version), 200
        return jsonify(status="unavailable", db="unavailable", version=version), 503

    return app
