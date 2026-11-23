# `feedback_domain/`: learning from what was delivered

This domain starts where the requests domain ends. When a video is delivered, it issues private feedback links, collects ratings and an outcome, and reports the outcome back as an event. It never imports `requests_domain`, and nothing in it imports Flask.

Its reason to exist is the fifth problem AV Desk solves: without structured feedback, the AV team never learned which requests went well.

## Files

| File | Responsibility | Pattern / principle |
|---|---|---|
| `models.py` | `Outcome`, rating dimensions, `DeliveredWork`, `FeedbackInvite`, `FeedbackAnswer`, `FeedbackResponse`, `ResponseReceived`, `InviteState` | Value objects |
| `rules.py` | `parse_answer`, `invite_state`, `invite_expiry` | Pure functions |
| `repository.py` | `FeedbackReader` / `FeedbackWriter` contracts and the SQLite adapter | ISP, **Adapter** |
| `events.py` | `FeedbackObserver` contract and `FeedbackEventSubject` | **Observer** |
| `facade.py` | `FeedbackFacade`, the only public entry point | **Facade** |
| `schema.sql` | `feedback_invites`, `feedback_responses` | |

## How the business rules map to code

### Who gets a link

One `FeedbackInvite` per person: the requester (always) and each reviewer the requester listed under *avaliadores* in the briefing. Each has its own token, so each answer is attributable and each link works once. The facade does not decide *who* gets invited; it receives a list of `Recipient`s from the seam (`services/seam.py`), because who counts as a reviewer is requests-domain knowledge.

### What a valid answer is

`parse_answer(form)` requires:

- all four ratings, each an integer from 1 to 5: tone and brand fit, quality of the result, process and communication, usefulness for the goal;
- one outcome: approved, approved with minor tweaks, or needs major changes;
- an optional comment of at most 3000 characters.

It returns either an answer or a dictionary of pt-BR error messages, never both. The four dimensions were chosen so metrics can tell *why* a delivery disappointed. Tone misalignment, the most common failure before AV Desk, is its own dimension.

### When a link works

`invite_state(invite, now)` returns one of four states:

| State | Condition | Page shown |
|---|---|---|
| `OPEN` | not used, `now < expires_at` | the form |
| `USED` | `used_at` is set | "already used, thank you" (HTTP 200) |
| `EXPIRED` | `now >= expires_at` | "expired, talk to the AV team" (HTTP 200) |
| `NOT_FOUND` | no invite with that token | "check the link" (HTTP 404) |

"Used" is checked before "expired", so a reviewer who answered in time is told the truth. Closed states are normal situations for a reviewer, so they get friendly pages, never errors. Links expire after `FEEDBACK_TTL_DAYS` (default 30).

### What happens after an answer

`FeedbackFacade.submit` validates, stores, then announces `ResponseReceived(request_id, public_code, outcome, is_requester)`. This domain does **not** decide what the outcome means for the request. That decision lives in `services/seam.py` (only the requester's answer closes or reopens the request), because it touches the requests lifecycle.

## Data: a snapshot instead of a foreign key

`feedback_invites.request_id` is a plain integer with **no foreign key** into the requests tables. Each invite stores its own copy of what it needs from the delivered request (`DeliveredWork`: code, title, type label, diretoria, delivery link, dates). This is ADR-3. In Assignment 2 this domain moves to its own database, where a cross-database key cannot exist.

The cost: if a request is edited after delivery, existing invites keep the old copy. That is acceptable, because the copy records what was actually delivered and reviewed.

Inside the domain, foreign keys are used normally: `feedback_responses.invite_id` points at its invite and is `UNIQUE`, so an invite has at most one response.

## Problems met while building this domain

- **Double submission.** Two quick submits of the same form could store two answers. `record_response` marks the invite used with `WHERE used_at IS NULL` in the same transaction as the insert; the second attempt changes no row and is treated as "already used". The `UNIQUE` column is a second line of defence.
- **Shared or separate event code?** Both domains need a subject/observer. Sharing one module would have created a dependency between them, so `events.py` deliberately mirrors `requests_domain/events.py` instead.

## How to extend

- **New rating dimension:** add it to `RATING_DIMENSIONS`, add the column (with its 1–5 CHECK) to `schema.sql` and the INSERT in `repository.py`. The form, validation and metrics loop over the dictionary and pick it up.
- **New outcome:** add it to `Outcome` and `OUTCOME_LABELS` and to the CHECK in `schema.sql`, then decide in `services/seam.py` what it does to the request.
