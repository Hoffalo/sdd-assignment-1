"""AV manager endpoints. Every facade call goes through the AdminOnly protection Proxy."""
from flask import Blueprint, current_app, jsonify, request

from avdesk_requests.domain.lifecycle import MissingInput, NotUndoable, TransitionNotAllowed
from avdesk_requests.domain.metrics import request_metrics
from avdesk_requests.domain.models import Status
from avdesk_requests.domain.repository import RequestFilter, StaleTransition
from avdesk_requests.web.admin_guard import AdminOnly, AdminRequired, AdminTokens, bearer_token, password_matches
from avdesk_requests.web.briefing_input import parse_int
from avdesk_requests.web.json_views import detail_json, metrics_json, summary_json
from avdesk_requests.web.public_api import json_body

blueprint = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_ACTOR = "gerência de AV"
STALE_MESSAGE = "Esse pedido mudou de status enquanto você olhava. Confira e tente de novo."


def admin_tokens() -> AdminTokens:
    return current_app.extensions["avdesk_admin_tokens"]


def guarded_requests():
    tokens = admin_tokens()
    return AdminOnly(current_app.extensions["avdesk"].requests,
                     lambda: tokens.is_valid(bearer_token(request.headers.get("Authorization"))))


def detail_response(request_id: int):
    requests = guarded_requests()
    tracked = requests.get(request_id)
    return jsonify(detail_json(tracked, requests.timeline(request_id), requests.available_actions(tracked),
                               requests.can_undo(request_id), requests.briefing_markdown(request_id),
                               requests.slack_message(request_id)))


@blueprint.errorhandler(AdminRequired)
def ask_for_login(_error):
    return jsonify(error="Entre como gerência de AV."), 401


@blueprint.post("/session")
def log_in():
    config = current_app.extensions["avdesk"].config
    password = json_body().get("password")
    if not isinstance(password, str) or not password_matches(password, config.admin_password):
        return jsonify(error="Senha incorreta."), 401
    tokens = admin_tokens()
    return jsonify(token=tokens.issue(), expires_in=tokens.ttl_seconds), 201


@blueprint.get("/requests")
def inbox():
    status = request.args.get("status", "")
    request_filter = RequestFilter(
        status=Status(status) if status in Status._value2member_map_ else None,
        type_code=request.args.get("type_code") or None,
        diretoria_id=parse_int(request.args.get("diretoria_id")),
        analyst_id=parse_int(request.args.get("analyst_id")),
    )
    return jsonify([summary_json(r) for r in guarded_requests().inbox(request_filter)])


@blueprint.get("/workload")
def workload():
    requests = guarded_requests()
    counts = requests.workload()
    config = current_app.extensions["avdesk"].config
    analysts = requests.catalog().analysts
    return jsonify(threshold=config.workload_warn_threshold,
                   analysts=[{"id": a.id, "name": a.name, "open": counts[a.id]} for a in analysts])


@blueprint.get("/requests/<int:request_id>")
def detail(request_id):
    return detail_response(request_id)


@blueprint.post("/requests/<int:request_id>/actions")
def perform(request_id):
    requests = guarded_requests()
    body = json_body()
    try:
        requests.perform(request_id, str(body.get("action", "")), actor=ADMIN_ACTOR, note=str(body.get("note", "")),
                         analyst_id=parse_int(body.get("analyst_id")), review_url=str(body.get("review_url", "")),
                         delivery_url=str(body.get("delivery_url", "")))
    except MissingInput as error:
        return jsonify(error=error.message, field=error.field), 422
    except (TransitionNotAllowed, StaleTransition):
        return jsonify(error=STALE_MESSAGE), 409
    return detail_response(request_id)


@blueprint.post("/requests/<int:request_id>/undo")
def undo(request_id):
    try:
        guarded_requests().undo_last(request_id)
    except (NotUndoable, StaleTransition):
        return jsonify(error="Não há mudança que possa ser desfeita."), 409
    return detail_response(request_id)


@blueprint.post("/requests/<int:request_id>/invites")
def retry_invites(request_id):
    requests = guarded_requests()
    if requests.get(request_id).delivered_at is None:
        return jsonify(error="O pedido ainda não foi entregue."), 409
    # The outcome is in the detail's invites_pending, so the page shows the
    # same notice whether the first try or this retry failed.
    current_app.extensions["avdesk"].invites.send(requests.snapshot(request_id))
    return detail_response(request_id)


@blueprint.get("/metrics")
def metrics():
    requests = guarded_requests()
    return jsonify(metrics_json(request_metrics(requests.all_requests(), requests.catalog())))
