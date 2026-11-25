from datetime import date

from avdesk_requests.web.briefing_input import briefing_from_json, parse_int
from tests.factories import make_catalog


def test_core_fields_are_read_and_trimmed():
    briefing = briefing_from_json({"title": "  Teaser  ", "needed_by": "2026-12-01", "diretoria_id": "2",
                                   "needs_c_level_approval": True}, make_catalog())

    assert (briefing.title, briefing.needed_by, briefing.diretoria_id, briefing.needs_c_level_approval) == \
        ("Teaser", date(2026, 12, 1), 2, True)


def test_answers_outside_the_catalog_are_ignored():
    briefing = briefing_from_json({"answers": {"objetivo": "x", "injected": "y"}}, make_catalog())

    assert "injected" not in briefing.answers


def test_multichoice_answers_become_tuples():
    briefing = briefing_from_json({"answers": {"destinos": ["YouTube", "Instagram"]}}, make_catalog())

    assert briefing.answers["destinos"] == ("YouTube", "Instagram")


def test_wrongly_typed_values_become_blank_for_the_validator_to_reject():
    briefing = briefing_from_json({"title": 5, "needed_by": "amanhã", "answers": {"objetivo": ["a"]}},
                                  make_catalog())

    assert (briefing.title, briefing.needed_by, briefing.answers["objetivo"]) == ("", None, "")


def test_only_the_boolean_true_asks_for_c_level_approval():
    assert briefing_from_json({"needs_c_level_approval": "false"}, make_catalog()).needs_c_level_approval is False


def test_booleans_are_not_mistaken_for_ids():
    assert parse_int(True) is None
