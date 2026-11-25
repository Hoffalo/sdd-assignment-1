"""Requester-facing endpoints: catalog, live deadline check, submit, track, resubmit."""
from flask import Blueprint, current_app, jsonify, request

from avdesk_requests.domain.facade import RequestNotFound, RequestsFacade
from avdesk_requests.domain.lifecycle import TransitionNotAllowed
from avdesk_requests.domain.models import Status
from avdesk_requests.web.briefing_input import briefing_from_json, parse_date
from avdesk_requests.web.json_views import assessment_json, catalog_json, tracking_json

blueprint = Blueprint("public", __name__)


def requests_facade() -> RequestsFacade:
    return current_app.extensions["avdesk"].requests


def json_body() -> dict:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def tracking_response(token: str, status_code: int = 200):
    facade = requests_facade()
    tracked = facade.by_token(token)
    return jsonify(tracking_json(tracked, facade.timeline(tracked.id), tracked.status == Status.NEEDS_INFO)), \
        status_code


@blueprint.get("/catalog")
def catalog():
    return jsonify(catalog_json(requests_facade().catalog()))


@blueprint.get("/deadline")
def deadline_check():
    """Lets the form explain the lead-time rule live, using the same policy as submission."""
    assessment = requests_facade().assess_deadline(
        request.args.get("type_code", ""), parse_date(request.args.get("needed_by")),
        request.args.get("needs_c_level_approval") == "true")
    if assessment is None:
        return jsonify(error="type_code and needed_by are required"), 400
    return jsonify(assessment_json(assessment))


@blueprint.post("/requests")
def submit_request():
    facade = requests_facade()
    checked, created = facade.submit(briefing_from_json(json_body(), facade.catalog()))
    if created is None:
        return jsonify(errors=checked.errors), 422
    return jsonify(tracking_token=created.tracking_token, public_code=created.public_code), 201


@blueprint.get("/requests/by-token/<token>")
def tracking(token):
    return tracking_response(token)


@blueprint.put("/requests/by-token/<token>/briefing")
def resubmit(token):
    facade = requests_facade()
    facade.by_token(token)
    try:
        checked, _ = facade.resubmit(token, briefing_from_json(json_body(), facade.catalog()))
    except TransitionNotAllowed:
        return jsonify(error="Este pedido não pode mais ser editado."), 409
    if not checked.is_valid:
        return jsonify(errors=checked.errors), 422
    return tracking_response(token)


@blueprint.app_errorhandler(RequestNotFound)
def request_not_found(_error):
    return jsonify(error="Pedido não encontrado."), 404
