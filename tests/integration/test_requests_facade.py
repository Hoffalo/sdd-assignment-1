from datetime import date

import pytest

from avdesk.composition import build_requests_domain
from avdesk.requests_domain.briefing import BriefingBuilder, BriefingDirector
from avdesk.requests_domain.events import RequestObserver
from avdesk.requests_domain.lifecycle import MissingInput, NotUndoable, TransitionNotAllowed
from avdesk.requests_domain.models import Status
from avdesk.requests_domain.repository import RequestFilter

FAR_AWAY = date(2026, 12, 1)


@pytest.fixture
def domain(seeded_db, clock, tokens):
    return build_requests_domain(seeded_db, clock, tokens, coo_buffer_days=3)


@pytest.fixture
def facade(domain):
    return domain[0]


@pytest.fixture
def director():
    return BriefingDirector(BriefingBuilder())


@pytest.fixture
def submitted(facade, director):
    _, request = facade.submit(director.teaser(needed_by=FAR_AWAY))
    return request


def test_invalid_briefing_is_not_stored(facade, director):
    checked, request = facade.submit(director.teaser(needed_by=FAR_AWAY, requester_email="x@gmail.com"))

    assert (request, "requester_email" in checked.errors, facade.all_requests()) == (None, True, [])


def test_valid_briefing_is_stored_as_submitted_with_a_private_token(submitted):
    assert (submitted.status, submitted.tracking_token) == (Status.SUBMITTED, "token-1")


def test_answers_to_other_types_are_dropped_on_submit(facade, director):
    _, request = facade.submit(director.teaser(needed_by=FAR_AWAY, outro_justificativa="sobrou"))

    assert "outro_justificativa" not in request.briefing.answers


def test_short_deadline_with_reason_is_stored_as_rush(facade, director):
    _, request = facade.submit(director.teaser(needed_by=date(2026, 10, 14), rush_reason="Confirmado ontem"))

    assert request.rush


def test_conference_content_needs_more_notice(facade):
    plain = facade.assess_deadline("teaser", date(2026, 10, 21), for_conference=False)
    conference = facade.assess_deadline("teaser", date(2026, 10, 21), for_conference=True)

    assert (plain.rush, conference.rush) == (False, True)


def test_perform_moves_the_request_and_logs_the_timeline(facade, submitted):
    facade.perform(submitted.id, "accept", actor="admin", analyst_id=2)

    assert [e.to_status for e in facade.timeline(submitted.id)] == [Status.SUBMITTED, Status.ACCEPTED]


def test_perform_notifies_observers_with_a_snapshot(domain, submitted, mocker):
    facade, events = domain
    observer = mocker.Mock(spec=RequestObserver)
    events.attach(observer)

    facade.perform(submitted.id, "accept", actor="admin", analyst_id=2)

    event = observer.on_status_changed.call_args.args[0]
    assert (event.to_status, event.snapshot.diretoria, event.snapshot.type_label) == \
           (Status.ACCEPTED, "Comunicação", "Teaser")


def test_missing_input_leaves_the_status_untouched(facade, submitted):
    with pytest.raises(MissingInput):
        facade.perform(submitted.id, "decline", actor="admin", note="")

    assert facade.get(submitted.id).status == Status.SUBMITTED


def test_admin_cannot_use_the_requester_resubmit_action(facade, submitted):
    facade.perform(submitted.id, "request_info", actor="admin", note="Falta o roteiro")

    with pytest.raises(TransitionNotAllowed):
        facade.perform(submitted.id, "resubmit", actor="admin")


def test_requester_resubmits_an_edited_briefing(facade, submitted, director):
    facade.perform(submitted.id, "request_info", actor="admin", note="Qual é o tom?")

    checked, request = facade.resubmit(submitted.tracking_token,
                                       director.teaser(needed_by=FAR_AWAY, title="Teaser revisado"))

    assert (checked.is_valid, request.status, request.briefing.title) == (True, Status.SUBMITTED, "Teaser revisado")


def test_resubmit_is_refused_unless_information_was_requested(facade, submitted, director):
    with pytest.raises(TransitionNotAllowed):
        facade.resubmit(submitted.tracking_token, director.teaser(needed_by=FAR_AWAY))


def test_undo_restores_the_previous_status(facade, submitted):
    facade.perform(submitted.id, "decline", actor="admin", note="Fora do escopo")

    facade.undo_last(submitted.id)

    assert facade.get(submitted.id).status == Status.SUBMITTED


def test_undo_of_acceptance_is_refused(facade, submitted):
    facade.perform(submitted.id, "accept", actor="admin", analyst_id=1)

    with pytest.raises(NotUndoable):
        facade.undo_last(submitted.id)


def test_workload_counts_open_work_per_analyst(facade, director):
    for _ in range(2):
        _, request = facade.submit(director.teaser(needed_by=FAR_AWAY))
        facade.perform(request.id, "accept", actor="admin", analyst_id=2)

    assert facade.workload()[2] == 2


def test_inbox_filters_by_status(facade, submitted):
    assert facade.inbox(RequestFilter(status=Status.SUBMITTED))[0].id == submitted.id


def test_markdown_export_lists_answers_by_section(facade, submitted):
    markdown = facade.briefing_markdown(submitted.id)

    assert "## Sobre o teaser" in markdown and "Abertura das inscrições" in markdown


def test_answers_to_hidden_questions_are_dropped_on_submit(facade, director):
    _, request = facade.submit(director.teaser(needed_by=FAR_AWAY, tom="Institucional", tom_outro="sobrou",
                                               destinos=("YouTube",), instagram_principal="@gobrasa"))

    assert {"tom_outro", "instagram_principal"}.isdisjoint(request.briefing.answers)
