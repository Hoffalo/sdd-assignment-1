"""Requester-facing pages: landing with the scope gate, briefing form, tracking page."""
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

from avdesk.requests_domain.briefing import Briefing
from avdesk.requests_domain.facade import RequestNotFound
from avdesk.requests_domain.lifecycle import TransitionNotAllowed
from avdesk.requests_domain.models import Status
from avdesk.web import services
from avdesk.web.forms import ANSWER_PREFIX, briefing_from_form, parse_date, question_sections

blueprint = Blueprint("public", __name__)


@blueprint.get("/")
def landing():
    return render_template("landing.html")


@blueprint.get("/healthz")
def healthz():
    return jsonify(status="ok")


@blueprint.get("/pedido/novo")
def new_request():
    return render_briefing_form(Briefing(), errors={}, action=url_for("public.new_request"))


@blueprint.post("/pedido/novo")
def submit_request():
    requests = services().requests
    catalog = requests.catalog()
    checked, created = requests.submit(briefing_from_form(request.form, catalog))
    if created is None:
        return render_briefing_form(checked.briefing, checked.errors, url_for("public.new_request")), 422
    flash("Pedido enviado! Guarde este link: é por ele que você acompanha o seu pedido.")
    return redirect(url_for("public.tracking", token=created.tracking_token))


@blueprint.get("/pedido/prazo")
def deadline_check():
    """Lets the form explain the lead-time rule live, using the same Python policy as submission."""
    assessment = services().requests.assess_deadline(
        request.args.get("type_code", ""), parse_date(request.args.get("needed_by")),
        request.args.get("needs_c_level_approval") == "sim")
    if assessment is None:
        return jsonify({})
    return jsonify(rush=assessment.rush, available_days=assessment.available_days,
                   required_days=assessment.required_days,
                   earliest_date=assessment.earliest_date.strftime("%d/%m/%Y"),
                   work_deadline=assessment.work_deadline.strftime("%d/%m/%Y"))


@blueprint.get("/pedido/<token>")
def tracking(token):
    return render_tracking(find_by_token(token), errors={})


@blueprint.post("/pedido/<token>")
def resubmit(token):
    requests = services().requests
    current = find_by_token(token)
    try:
        checked, updated = requests.resubmit(token, briefing_from_form(request.form, requests.catalog()))
    except TransitionNotAllowed:
        flash("Este pedido não pode mais ser editado.", "error")
        return redirect(url_for("public.tracking", token=token))
    if not checked.is_valid:
        return render_tracking(current, checked.errors, edited=checked.briefing), 422
    flash("Briefing atualizado e reenviado. Obrigado!")
    return redirect(url_for("public.tracking", token=token))


def find_by_token(token: str):
    try:
        return services().requests.by_token(token)
    except RequestNotFound:
        abort(404)


def render_briefing_form(briefing: Briefing, errors: dict, action: str):
    catalog = services().requests.catalog()
    return render_template("briefing_form.html", briefing=briefing, errors=errors, action=action,
                           catalog=catalog, sections=question_sections(catalog), prefix=ANSWER_PREFIX)


def render_tracking(tracked, errors: dict, edited: Briefing | None = None):
    requests = services().requests
    catalog = requests.catalog()
    return render_template("tracking.html", tracked=tracked, timeline=requests.timeline(tracked.id),
                           catalog=catalog, sections=question_sections(catalog),
                           editable=tracked.status == Status.NEEDS_INFO,
                           briefing=edited or tracked.briefing, errors=errors, prefix=ANSWER_PREFIX,
                           action=url_for("public.resubmit", token=tracked.tracking_token))


@blueprint.app_errorhandler(404)
def not_found(_error):
    return render_template("message.html", heading="Não encontramos esta página",
                           message="Confira se o link foi copiado inteiro.", back_home=True), 404
