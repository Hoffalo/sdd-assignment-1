"""HTTP glue of the feedback service: turns JSON requests into facade calls and back.

Assembled here from already-built collaborators, so tests can create the
Flask app with stubs and no database; choosing concrete classes is the
composition root's job. The service only speaks JSON: the pages live in ui/.
"""
from flask import Flask, jsonify

from avdesk_feedback.health import HealthProbe
from avdesk_feedback.web import api, cors, request_log
from avdesk_feedback.web.admin_guard import AdminTokens


def create_web_app(health_probe: HealthProbe, version: str, cors_origin: str = "") -> Flask:
    app = Flask(__name__)
    request_log.install(app)
    cors.install(app, cors_origin)

    @app.get("/health")
    def health():
        if health_probe.database_is_healthy():
            return jsonify(status="ok", db="ok", version=version), 200
        return jsonify(status="unavailable", db="unavailable", version=version), 503

    @app.after_request
    def never_cache(response):
        # Answers change with every status update and some are admin-only, so
        # the browser must always ask again (a reload once showed stale data).
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="Not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="Method not allowed"), 405

    @app.errorhandler(500)
    def server_error(_error):
        # The traceback goes to the log (Flask logs it); the caller gets JSON, never HTML.
        return jsonify(error="Erro interno. Tente de novo em instantes."), 500

    return app


def register_api(app: Flask, services, admin_tokens: AdminTokens, service_tokens: AdminTokens) -> None:
    app.extensions["avdesk"] = services
    app.extensions["avdesk_admin_tokens"] = admin_tokens
    app.extensions["avdesk_service_tokens"] = service_tokens
    app.register_blueprint(api.blueprint)
