from datetime import date, datetime, timezone

from avdesk_feedback.domain.metrics import average_ratings_by, feedback_metrics, response_rate
from avdesk_feedback.domain.models import DeliveredWork, FeedbackAnswer, FeedbackInvite, FeedbackResponse, Outcome

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def make_invite(id=1, type_label="Teaser", diretoria="Conferências", used=True) -> FeedbackInvite:
    work = DeliveredWork(id, f"AV-{id}", "Vídeo", type_label, diretoria, "https://drive.google.com/x",
                         date(2026, 10, 10), T0)
    return FeedbackInvite(id, f"t{id}", work, "Ana", True, T0, T0 if used else None, T0)


def make_response(invite_id=1, tone=5, outcome=Outcome.APPROVED, is_requester=True) -> FeedbackResponse:
    ratings = {"rating_tone": tone, "rating_quality": 4, "rating_process": 3, "rating_usefulness": 5}
    return FeedbackResponse(invite_id, invite_id, is_requester, FeedbackAnswer(ratings, outcome, ""), T0)


def test_response_rate_counts_used_invites():
    assert response_rate([make_invite(1), make_invite(2, used=False)]) == 0.5


def test_response_rate_is_none_without_invites():
    assert response_rate([]) is None


def test_ratings_are_averaged_per_dimension_and_group():
    averages = average_ratings_by([make_response(1, tone=5), make_response(2, tone=3)], lambda r: "Teaser")

    assert averages["Teaser"]["rating_tone"] == 4


def test_responses_without_a_group_are_skipped():
    assert average_ratings_by([make_response()], lambda r: None) == {}


def test_ratings_are_grouped_by_the_snapshot_taken_at_delivery():
    invites = [make_invite(1, type_label="Teaser"), make_invite(2, type_label="Institucional")]

    metrics = feedback_metrics(invites, [make_response(1, tone=5), make_response(2, tone=2)])

    assert {k: v["rating_tone"] for k, v in metrics.ratings_by_type.items()} == {"Institucional": 2, "Teaser": 5}


def test_only_the_requester_verdict_counts_as_the_outcome():
    responses = [make_response(1, outcome=Outcome.MAJOR_CHANGES),
                 make_response(1, outcome=Outcome.APPROVED, is_requester=False)]

    metrics = feedback_metrics([make_invite(1)], responses)

    assert (metrics.outcome_counts, metrics.requester_outcomes) == \
        ({Outcome.MAJOR_CHANGES: 1}, {1: Outcome.MAJOR_CHANGES})
