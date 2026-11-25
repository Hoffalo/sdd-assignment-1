"""Both real services, each on its own HTTP port and database, talking across the seam.

This is the only test that runs the two together. Each service's own suite
replaces the other with a stub; here nothing is stubbed, so it proves the
two sides agree on paths, bodies, tokens and status codes, and that each
side survives the other being down.
"""
from tests.cross_seam.conftest import BRIEFING, call


def deliver_new_request(requests, admin_headers) -> int:
    public_code = call("POST", f"{requests.url}/requests", BRIEFING)[1]["public_code"]
    inbox = call("GET", f"{requests.url}/admin/requests", headers=admin_headers)[1]
    request_id = next(r["id"] for r in inbox if r["public_code"] == public_code)
    for action, inputs in [("accept", {"analyst_id": 2}), ("start_production", {}),
                           ("deliver", {"delivery_url": "https://drive.google.com/final"})]:
        call("POST", f"{requests.url}/admin/requests/{request_id}/actions", {"action": action, **inputs},
             headers=admin_headers)
    return request_id


def invites_of(feedback, admin_headers, request_id) -> list[dict]:
    return call("GET", f"{feedback.url}/admin/requests/{request_id}/invites", headers=admin_headers)[1]


def detail_of(requests, admin_headers, request_id) -> dict:
    return call("GET", f"{requests.url}/admin/requests/{request_id}", headers=admin_headers)[1]


def answer(feedback, invite, outcome) -> int:
    body = {"rating_tone": 5, "rating_quality": 5, "rating_process": 4, "rating_usefulness": 5,
            "outcome": outcome, "comment": ""}
    return call("POST", f"{feedback.url}/invites/{invite['token']}/response", body)[0]


def test_delivery_creates_invites_in_the_feedback_service(requests, feedback, admin_headers):
    request_id = deliver_new_request(requests, admin_headers)

    assert [(i["recipient_label"], i["is_requester"]) for i in invites_of(feedback, admin_headers, request_id)] == [
        ("Ana Souza", True), ("Bruno Lima", False)]


def test_the_requesters_approval_closes_the_request(requests, feedback, admin_headers):
    request_id = deliver_new_request(requests, admin_headers)

    answer(feedback, invites_of(feedback, admin_headers, request_id)[0], "approved")

    detail = detail_of(requests, admin_headers, request_id)
    assert (detail["status"], detail["timeline"][-1]["actor"]) == ("closed", "avaliação")


def test_delivery_while_feedback_is_down_is_kept_and_retried(requests, feedback, admin_headers):
    feedback.stop()
    request_id = deliver_new_request(requests, admin_headers)
    pending = detail_of(requests, admin_headers, request_id)["invites_pending"]
    feedback.start()

    retried = call("POST", f"{requests.url}/admin/requests/{request_id}/invites", headers=admin_headers)[1]

    assert (pending, retried["invites_pending"], len(invites_of(feedback, admin_headers, request_id))) == (
        True, False, 2)


def test_a_verdict_while_requests_is_down_is_stored_and_resent(requests, feedback, admin_headers):
    request_id = deliver_new_request(requests, admin_headers)
    requester_invite = invites_of(feedback, admin_headers, request_id)[0]
    requests.stop()
    stored = answer(feedback, requester_invite, "major_changes")
    pending = invites_of(feedback, admin_headers, request_id)[0]["verdict_pending"]
    requests.start()

    call("POST", f"{feedback.url}/admin/requests/{request_id}/verdict", headers=admin_headers)

    assert (stored, pending, detail_of(requests, admin_headers, request_id)["status"]) == (
        201, True, "in_production")
