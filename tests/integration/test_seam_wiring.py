"""The two domains talking through the real observers wired by the composition root."""
from datetime import date

import pytest

from avdesk.composition import build_services
from avdesk.config import Config
from avdesk.feedback_domain.models import InviteState
from avdesk.integrations.task_tracker import TaskTracker
from avdesk.requests_domain.briefing import BriefingBuilder, BriefingDirector
from avdesk.requests_domain.models import Status

FORM = {"rating_tone": "5", "rating_quality": "5", "rating_process": "4", "rating_usefulness": "5", "comment": ""}


class RecordingTracker(TaskTracker):
    def __init__(self):
        self.drafts = []

    def create_task(self, draft):
        self.drafts.append(draft)
        return "https://app.clickup.com/t/abc"


@pytest.fixture
def tracker():
    return RecordingTracker()


@pytest.fixture
def services(seeded_db, clock, tokens, tracker):
    return build_services(Config.from_env({}), seeded_db, clock, tokens, tracker)


@pytest.fixture
def delivered(services):
    briefing = BriefingDirector(BriefingBuilder()).teaser(needed_by=date(2026, 12, 1), avaliadores="Bruno")
    _, request = services.requests.submit(briefing)
    services.requests.perform(request.id, "accept", actor="admin", analyst_id=2)
    services.requests.perform(request.id, "start_production", actor="admin")
    services.requests.perform(request.id, "deliver", actor="admin", delivery_url="https://drive.google.com/final")
    return services.requests.get(request.id)


def test_acceptance_creates_a_clickup_task_and_keeps_its_link(delivered, tracker):
    assert (len(tracker.drafts), delivered.task_url) == (1, "https://app.clickup.com/t/abc")


def test_delivery_creates_one_invite_per_person(services, delivered):
    invites = services.feedback.invites_for_request(delivered.id)

    assert [(i.recipient_label, i.is_requester) for i in invites] == [("Pessoa Solicitante", True), ("Bruno", False)]


def test_requester_approval_closes_the_request(services, delivered):
    requester_invite = services.feedback.invites_for_request(delivered.id)[0]

    services.feedback.submit(requester_invite.token, {**FORM, "outcome": "approved"})

    assert services.requests.get(delivered.id).status == Status.CLOSED


def test_requester_asking_for_major_changes_reopens_the_request(services, delivered):
    requester_invite = services.feedback.invites_for_request(delivered.id)[0]

    services.feedback.submit(requester_invite.token, {**FORM, "outcome": "major_changes"})

    assert services.requests.get(delivered.id).status == Status.IN_PRODUCTION


def test_reviewer_response_is_stored_but_leaves_status_alone(services, delivered):
    reviewer_invite = services.feedback.invites_for_request(delivered.id)[1]

    services.feedback.submit(reviewer_invite.token, {**FORM, "outcome": "major_changes"})

    assert (services.requests.get(delivered.id).status,
            services.feedback.open_invite(reviewer_invite.token)[1]) == (Status.DELIVERED, InviteState.USED)


def test_metrics_combine_both_domains(services, delivered):
    requester_invite = services.feedback.invites_for_request(delivered.id)[0]
    services.feedback.submit(requester_invite.token, {**FORM, "outcome": "approved"})

    dashboard = services.metrics.dashboard()

    assert (dashboard.response_rate, dashboard.ratings_by_type["Teaser"]["rating_tone"]) == (0.5, 5)
