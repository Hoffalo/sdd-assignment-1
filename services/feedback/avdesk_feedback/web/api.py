"""Feedback endpoints: a reviewer's single-use invite, and the AV manager's read-only views."""
from flask import Blueprint, current_app, jsonify, request

from avdesk_feedback.domain.facade import FeedbackFacade
from avdesk_feedback.domain.metrics import feedback_metrics
from avdesk_feedback.domain.models import InviteState
from avdesk_feedback.web.admin_guard import AdminOnly, AdminRequired, AdminTokens, bearer_token
from avdesk_feedback.web.json_views import admin_invite_json, metrics_json, public_invite_json

blueprint = Blueprint("feedback", __name__)

# A used or expired link is a normal situation for a reviewer, not an error,
# so it is reported as a state; only an unknown token is a 404.
NOT_FOUND = 404
CLOSED = 409


def feedback_facade() -> FeedbackFacade:
    return current_app.extensions["avdesk"].feedback


def guarded_feedback():
    tokens: AdminTokens = current_app.extensions["avdesk_admin_tokens"]
    return AdminOnly(feedback_facade(), lambda: tokens.is_valid(bearer_token(request.headers.get("Authorization"))))


def form_values() -> dict[str, str]:
    """The domain parses text, as it did from the A1 HTML form, so JSON numbers become strings here."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return {}
    return {k: str(v) for k, v in body.items() if isinstance(v, (str, int)) and not isinstance(v, bool)}


@blueprint.get("/invites/<token>")
def open_invite(token):
    invite, state = feedback_facade().open_invite(token)
    return jsonify(public_invite_json(invite, state)), NOT_FOUND if state == InviteState.NOT_FOUND else 200


@blueprint.post("/invites/<token>/response")
def submit_response(token):
    result = feedback_facade().submit(token, form_values())
    if result.response is not None:
        return jsonify(state=str(InviteState.USED)), 201
    if result.errors:
        return jsonify(errors=result.errors), 422
    return jsonify(state=str(result.state)), NOT_FOUND if result.state == InviteState.NOT_FOUND else CLOSED


@blueprint.get("/admin/requests/<int:request_id>/invites")
def invites_for_request(request_id):
    return jsonify([admin_invite_json(i) for i in guarded_feedback().invites_for_request(request_id)])


@blueprint.get("/admin/metrics")
def metrics():
    feedback = guarded_feedback()
    return jsonify(metrics_json(feedback_metrics(feedback.all_invites(), feedback.all_responses())))


@blueprint.app_errorhandler(AdminRequired)
def ask_for_login(_error):
    return jsonify(error="Entre como gerência de AV."), 401
