"""AV manager pages. Every facade is reached through the AdminOnly protection Proxy."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from avdesk.feedback_domain.models import OUTCOME_LABELS, RATING_DIMENSIONS
from avdesk.requests_domain.facade import RequestNotFound
from avdesk.requests_domain.lifecycle import MissingInput, NotUndoable, TransitionNotAllowed
from avdesk.requests_domain.models import Status
from avdesk.requests_domain.repository import RequestFilter, StaleTransition
from avdesk.services.admin_guard import AdminOnly, AdminRequired
from avdesk.web import security, services
from avdesk.web.forms import parse_int

blueprint = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_ACTOR = "gerência de AV"


def guarded(target):
    return AdminOnly(target, security.is_admin)


@blueprint.errorhandler(AdminRequired)
def ask_for_login(_error):
    return redirect(url_for("admin.login", next=request.path))


@blueprint.errorhandler(RequestNotFound)
def request_not_found(_error):
    return render_template("not_found.html"), 404


@blueprint.get("/login")
def login():
    return render_template("admin_login.html", error=None)


@blueprint.post("/login")
def do_login():
    if not security.password_matches(request.form.get("password", ""), services().config.admin_password):
        return render_template("admin_login.html", error="Senha incorreta."), 401
    security.log_in()
    target = request.args.get("next", "")
    # Only same-site paths, so the login page cannot be used to bounce people elsewhere.
    return redirect(target if target.startswith("/admin") else url_for("admin.inbox"))


@blueprint.post("/logout")
def logout():
    security.log_out()
    return redirect(url_for("public.landing"))


@blueprint.get("")
def inbox():
    requests = guarded(services().requests)
    status = request.args.get("status", "")
    request_filter = RequestFilter(
        status=Status(status) if status in Status._value2member_map_ else None,
        type_code=request.args.get("type_code") or None,
        diretoria_id=parse_int(request.args.get("diretoria_id")),
        analyst_id=parse_int(request.args.get("analyst_id")),
    )
    return render_template("admin_inbox.html", requests=requests.inbox(request_filter), catalog=requests.catalog(),
                           workload=requests.workload(), statuses=list(Status), current=request.args,
                           threshold=services().config.workload_warn_threshold)


@blueprint.get("/pedidos/<int:request_id>")
def detail(request_id):
    requests = guarded(services().requests)
    tracked = requests.get(request_id)
    return render_template(
        "admin_detail.html", tracked=tracked, catalog=requests.catalog(), timeline=requests.timeline(request_id),
        actions=requests.available_actions(tracked), can_undo=requests.can_undo(request_id),
        workload=requests.workload(), threshold=services().config.workload_warn_threshold,
        invites=guarded(services().feedback).invites_for_request(request_id),
        markdown=requests.briefing_markdown(request_id), slack=requests.slack_message(request_id))


@blueprint.post("/pedidos/<int:request_id>/acao")
def perform(request_id):
    requests = guarded(services().requests)
    form = request.form
    try:
        requests.perform(request_id, form.get("action", ""), actor=ADMIN_ACTOR, note=form.get("note", ""),
                         analyst_id=parse_int(form.get("analyst_id")), delivery_url=form.get("delivery_url", ""))
        flash("Status atualizado.")
    except MissingInput as error:
        flash(error.message, "error")
    except (TransitionNotAllowed, StaleTransition):
        flash("Esse pedido mudou de status enquanto você olhava. Confira e tente de novo.", "error")
    return redirect(url_for("admin.detail", request_id=request_id))


@blueprint.post("/pedidos/<int:request_id>/desfazer")
def undo(request_id):
    try:
        guarded(services().requests).undo_last(request_id)
        flash("Última mudança desfeita.")
    except (NotUndoable, StaleTransition):
        flash("Não há mudança que possa ser desfeita.", "error")
    return redirect(url_for("admin.detail", request_id=request_id))


@blueprint.get("/metricas")
def metrics():
    dashboard = guarded(services().metrics).dashboard()
    return render_template("admin_metrics.html", dashboard=dashboard, dimensions=RATING_DIMENSIONS,
                           outcomes=OUTCOME_LABELS)
