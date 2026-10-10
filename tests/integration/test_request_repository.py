from datetime import date, datetime, timezone

import pytest

from avdesk.requests_domain.briefing import BriefingBuilder, BriefingDirector
from avdesk.requests_domain.models import Status
from avdesk.requests_domain.repository import (
    RequestFilter, SqliteCatalogReader, SqliteRequestRepository, StaleTransition,
)

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def repo(seeded_db):
    return SqliteRequestRepository(seeded_db)


@pytest.fixture
def stored(repo):
    briefing = BriefingDirector(BriefingBuilder()).teaser(needed_by=date(2026, 12, 1))
    return repo.add(briefing, tracking_token="tok-1", rush=False, score=75, at=NOW)


def test_catalog_is_loaded_from_seeded_tables(seeded_db):
    catalog = SqliteCatalogReader(seeded_db).load()

    assert [t.code for t in catalog.types] == ["teaser", "institucional", "redes_sociais", "outro"]


def test_seeded_questions_keep_their_options(seeded_db):
    catalog = SqliteCatalogReader(seeded_db).load()

    tom = next(q for q in catalog.questions if q.key == "tom")
    assert "Institucional" in tom.options


def test_added_request_round_trips_with_its_briefing(repo, stored):
    loaded = repo.get_by_token("tok-1")

    assert loaded.briefing == stored.briefing


def test_multichoice_answers_come_back_as_tuples(stored, repo):
    assert repo.get(stored.id).briefing.answers["publicos"] == ("Universitários no exterior",)


def test_new_request_gets_a_public_code_and_a_first_event(repo, stored):
    events = repo.events(stored.id)

    assert (stored.public_code, [e.to_status for e in events]) == ("AV-2026-0001", [Status.SUBMITTED])


def test_transition_updates_status_fields_and_timeline(repo, stored):
    repo.apply_transition(stored.id, Status.SUBMITTED, Status.ACCEPTED, {"analyst_id": 1, "accepted_at": NOW},
                          "", "admin", NOW)

    loaded = repo.get(stored.id)
    assert (loaded.status, loaded.analyst_id, loaded.accepted_at, len(repo.events(stored.id))) == \
           (Status.ACCEPTED, 1, NOW, 2)


def test_transition_from_a_stale_status_is_rejected(repo, stored):
    with pytest.raises(StaleTransition):
        repo.apply_transition(stored.id, Status.ACCEPTED, Status.IN_PRODUCTION, {}, "", "admin", NOW)


def test_transition_cannot_set_arbitrary_columns(repo, stored):
    with pytest.raises(ValueError):
        repo.apply_transition(stored.id, Status.SUBMITTED, Status.ACCEPTED, {"title": "x"}, "", "admin", NOW)


def test_replacing_the_briefing_keeps_the_same_request(repo, stored):
    updated = BriefingDirector(BriefingBuilder()).teaser(needed_by=date(2026, 12, 1), title="Novo título")

    repo.replace_briefing(stored.id, updated, rush=True, score=90, at=NOW)

    loaded = repo.get(stored.id)
    assert (loaded.briefing.title, loaded.rush, loaded.briefing_score) == ("Novo título", True, 90)


def test_find_filters_by_status(repo, stored):
    assert repo.find(RequestFilter(status=Status.SUBMITTED)) == [repo.get(stored.id)]
    assert repo.find(RequestFilter(status=Status.CLOSED)) == []


def test_task_url_is_stored(repo, stored):
    repo.set_task_url(stored.id, "https://app.clickup.com/t/abc")

    assert repo.get(stored.id).task_url == "https://app.clickup.com/t/abc"
