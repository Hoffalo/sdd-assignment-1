"""Endpoints only the feedback service calls, authenticated with a signed service token.

A service token carries its own claim, so an admin token cannot call these
and a service token cannot open admin pages. The verdict is idempotent: a
retry after a lost answer finds the request already moved and changes
nothing, so the feedback service may resend freely.
"""
from flask import Blueprint, current_app, jsonify, request

from avdesk_requests.domain.lifecycle import TransitionNotAllowed
from avdesk_requests.domain.repository import StaleTransition
from avdesk_requests.domain.verdict import Verdict
from avdesk_requests.web.admin_guard import AdminTokens, bearer_token
from avdesk_requests.web.public_api import json_body

blueprint = Blueprint("service", __name__)


@blueprint.post("/requests/<int:request_id>/verdict")
def apply_verdict(request_id):
    tokens: AdminTokens = current_app.extensions["avdesk_service_tokens"]
    if not tokens.is_valid(bearer_token(request.headers.get("Authorization"))):
        return jsonify(error="Service token required."), 401
    raw = json_body().get("verdict")
    if raw not in Verdict._value2member_map_:
        return jsonify(error="Unknown verdict.", field="verdict"), 422
    try:
        updated = current_app.extensions["avdesk"].requests.apply_requester_verdict(request_id, Verdict(raw))
    except (TransitionNotAllowed, StaleTransition):
        return jsonify(error="The request changed status at the same time; send the verdict again."), 409
    return jsonify(status=str(updated.status)), 200
