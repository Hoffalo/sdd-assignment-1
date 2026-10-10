"""Public feedback page reached through a single-use invite link."""
from flask import Blueprint, render_template, request

from avdesk.feedback_domain.models import OUTCOME_LABELS, RATING_DIMENSIONS, InviteState
from avdesk.web import services

blueprint = Blueprint("feedback", __name__)

# Every closed state answers 200 with a friendly page: a stale link is a normal
# situation for a reviewer, not a server error.
CLOSED_MESSAGES = {
    InviteState.USED: "Este link já foi usado. Obrigado pela sua avaliação!",
    InviteState.EXPIRED: "Este link expirou. Se ainda quiser avaliar, fale com a gerência de Audiovisual.",
    InviteState.NOT_FOUND: "Não encontramos este link de avaliação. Confira se ele foi copiado inteiro.",
}


@blueprint.get("/feedback/<token>")
def feedback_form(token):
    invite, state = services().feedback.open_invite(token)
    if state != InviteState.OPEN:
        return render_closed(state)
    return render_form(invite, form={}, errors={})


@blueprint.post("/feedback/<token>")
def submit_feedback(token):
    feedback = services().feedback
    result = feedback.submit(token, request.form)
    if result.response is not None:
        return render_template("message.html", heading="Obrigado!", message="Avaliação enviada. Muito obrigado!")
    if result.errors:
        invite, _ = feedback.open_invite(token)
        return render_form(invite, request.form, result.errors), 422
    return render_closed(result.state)


def render_form(invite, form, errors):
    return render_template("feedback_form.html", invite=invite, form=form, errors=errors,
                           dimensions=RATING_DIMENSIONS, outcomes=OUTCOME_LABELS)


def render_closed(state: InviteState):
    status = 404 if state == InviteState.NOT_FOUND else 200
    return render_template("message.html", heading="Link indisponível", message=CLOSED_MESSAGES[state]), status
