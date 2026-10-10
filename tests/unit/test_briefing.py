from datetime import date

import pytest

from avdesk.requests_domain.briefing import BriefingBuilder, BriefingDirector
from avdesk.requests_domain.intake import BriefingScorer
from avdesk.requests_domain.leadtime import StandardLeadTime
from avdesk.requests_domain.validators import BriefingValidator
from tests.factories import make_catalog

TODAY = date(2026, 10, 9)
FAR_AWAY = date(2026, 12, 1)


@pytest.fixture
def catalog():
    return make_catalog()


@pytest.fixture
def director():
    return BriefingDirector(BriefingBuilder())


@pytest.fixture
def validator():
    return BriefingValidator()


def assess(briefing):
    return StandardLeadTime(min_days=10).assess(TODAY, briefing.needed_by)


# Builder and Director

def test_builder_collects_answers_step_by_step():
    briefing = BriefingBuilder().title("Teaser").answer("objetivo", "Inspirar").answer("tom", "Institucional").build()

    assert briefing.answers == {"objetivo": "Inspirar", "tom": "Institucional"}


def test_builder_starts_fresh_after_build():
    builder = BriefingBuilder()
    builder.title("Primeiro").build()

    assert builder.build().title == ""


def test_director_preset_produces_a_valid_briefing(director, validator, catalog):
    briefing = director.teaser(needed_by=FAR_AWAY)

    assert validator.validate(briefing, catalog, TODAY, assess(briefing)) == {}


def test_reviewers_are_read_one_per_line(director):
    briefing = BriefingBuilder().answer("avaliadores", "Ana\n\n  Bruno  \n").build()

    assert briefing.reviewers == ("Ana", "Bruno")


# Validator

def test_required_question_for_the_type_blocks_submission(director, validator, catalog):
    briefing = director.teaser(needed_by=FAR_AWAY, teaser_anuncio="")

    errors = validator.validate(briefing, catalog, TODAY, assess(briefing))

    assert "teaser_anuncio" in errors


def test_question_of_another_type_is_not_required(director, validator, catalog):
    briefing = director.teaser(needed_by=FAR_AWAY)

    errors = validator.validate(briefing, catalog, TODAY, assess(briefing))

    assert "outro_justificativa" not in errors


@pytest.mark.parametrize("email", ["ana@gmail.com", "ana@gobrasa.org.fake.com", "sem-arroba"])
def test_email_must_belong_to_gobrasa(director, validator, catalog, email):
    briefing = director.teaser(needed_by=FAR_AWAY, requester_email=email)

    assert "requester_email" in validator.validate(briefing, catalog, TODAY, assess(briefing))


def test_types_with_a_detail_label_require_the_detail(director, validator, catalog):
    briefing = director.social_video(needed_by=FAR_AWAY, type_detail="")

    assert "type_detail" in validator.validate(briefing, catalog, TODAY, assess(briefing))


def test_unknown_type_is_rejected(validator, catalog):
    briefing = BriefingBuilder().request_type("documentario").build()

    assert "type_code" in validator.validate(briefing, catalog, TODAY, None)


def test_needed_by_in_the_past_is_rejected(director, validator, catalog):
    briefing = director.teaser(needed_by=date(2026, 10, 1))

    assert "needed_by" in validator.validate(briefing, catalog, TODAY, None)


def test_rush_request_without_reason_is_rejected(director, validator, catalog):
    briefing = director.teaser(needed_by=date(2026, 10, 14))

    assert "rush_reason" in validator.validate(briefing, catalog, TODAY, assess(briefing))


def test_rush_request_with_reason_is_accepted(director, validator, catalog):
    briefing = director.teaser(needed_by=date(2026, 10, 14), rush_reason="Patrocinador confirmou ontem")

    assert validator.validate(briefing, catalog, TODAY, assess(briefing)) == {}


def test_url_answers_must_be_http(director, validator, catalog):
    briefing = director.teaser(needed_by=FAR_AWAY, roteiro_url="drive.google.com/x")

    assert "roteiro_url" in validator.validate(briefing, catalog, TODAY, assess(briefing))


def test_choice_answers_must_be_one_of_the_options(director, validator, catalog):
    briefing = director.teaser(needed_by=FAR_AWAY, tom="Sarcástico")

    assert "tom" in validator.validate(briefing, catalog, TODAY, assess(briefing))


def test_overlong_text_is_rejected(director, validator, catalog):
    briefing = director.teaser(needed_by=FAR_AWAY, title="x" * 500)

    assert "title" in validator.validate(briefing, catalog, TODAY, assess(briefing))


# Scorer

def test_score_is_zero_when_nothing_is_answered(catalog):
    briefing = BriefingBuilder().request_type("teaser").build()

    assert BriefingScorer().score(briefing, catalog) == 0


def test_score_is_full_when_every_question_is_answered(catalog):
    builder = BriefingBuilder().request_type("teaser")
    for question in catalog.questions_for("teaser"):
        builder.answer(question.key, question.options[0] if question.options else "ok")

    assert BriefingScorer().score(builder.build(), catalog) == 100


def test_score_counts_only_questions_of_the_chosen_type(catalog):
    briefing = BriefingBuilder().request_type("outro").answer("outro_justificativa", "Porque sim").build()

    # 3 common questions + 1 for "outro"; the teaser question is not counted.
    assert BriefingScorer().score(briefing, catalog) == 25
