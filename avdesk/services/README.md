# `services/`: where the two domains meet

This is the only package allowed to import both `requests_domain` and `feedback_domain`. Keeping every cross-domain dependency here makes the seam visible: to know what Assignment 2 must turn into network calls, read this folder.

## Files

| File | What it does | Pattern |
|---|---|---|
| `seam.py` | `FeedbackInviteObserver` (delivery → invites) and `FeedbackOutcomeApplier` (requester's outcome → close or reopen) | **Observer** listeners |
| `task_observer.py` | `TaskTrackerObserver` (acceptance → ClickUp task) | **Observer** listener |
| `metrics.py` | Metric functions and `MetricsService`, the dashboard reader | Pure functions + read-only service |
| `admin_guard.py` | `AdminOnly`, which checks the admin login before forwarding any call | Protection **Proxy** |

## What crosses the seam (ADR-2)

Exactly three things:

1. **Requests → Feedback.** On `StatusChanged` to `delivered`, `FeedbackInviteObserver` translates the `RequestSnapshot` into feedback's own `DeliveredWork` and calls `FeedbackFacade.create_invites` for the requester plus every listed reviewer. The translation is the point: each domain keeps its own vocabulary, and only this class knows both.
2. **Feedback → Requests.** On `ResponseReceived`, `FeedbackOutcomeApplier` ignores reviewers. For the requester, "major changes" performs `reopen` and anything else performs `close`, with actor `avaliação` so the timeline shows who moved the request. If the request is no longer `delivered` (the manager moved it by hand), it does nothing.
3. **Metrics.** `MetricsService` reads both facades and never writes.

`TaskTrackerObserver` uses the same mechanism for a non-domain listener. On `accepted`, it creates a ClickUp task named `[AV-2026-0001] <title>`, with the Markdown briefing as description, the requester's date as due date and high priority if rush, then stores the task link on the request.

All listeners are attached in `composition.build_services`. Nothing in the domains knows they exist.

## Why Observer, and what it costs

Delivering must create invites, but the requests domain must not depend on the feedback domain. With the Observer pattern, the subject announces and listeners react.

This is the in-process version from class: the subject calls listeners directly, synchronously, in the same thread as the manager's click. Three consequences:

- **A slow listener slows the click.** ClickUp therefore has a 5-second timeout (§1c of the brief forbids moving it to a background worker).
- **A failing listener must not undo the click.** Subjects log and continue; the status change is already committed.
- **It cannot cross services.** In Assignment 2 the events become messages on a Pub/Sub broker, and the facade calls become HTTP calls.

## Metrics (`metrics.py`)

The calculations are plain functions over lists, so they are tested with a handful of hand-made rows:

| Function | Business question |
|---|---|
| `rush_share` | How often do people ask too late? |
| `turnaround_days`, `median_turnaround_by` | How long does production take, accepted → delivered, per type? (Median, so one stuck request doesn't distort it.) |
| `on_time_rate` | How often is a delivery on or before the requested date? |
| `response_rate` | Do people actually answer feedback? |
| `average_ratings_by` | Which types and diretorias rate us best or worst, per dimension? |
| `average_score_by_outcome` | Do fuller briefings lead to approvals? (Requester answers only.) |

Rates return `None` when there is nothing to measure, so the page shows "—" instead of a misleading 0%.

A caching proxy and a Strategy family for metrics were considered and **not** used: at a few hundred requests a year the queries are instant, and wrapping each function in a class would be a pattern for its own sake (see `docs/DESIGN_NOTES.md`).

## The admin Proxy (`admin_guard.py`)

Admin routes receive `AdminOnly(facade, is_admin)` instead of the facade. Any attribute access first calls `is_admin()`; if it is false, `AdminRequired` is raised and the admin blueprint turns it into a redirect to the login page. The rule lives in one object, so a new admin page cannot forget it. The trade-off: forwarding through `__getattr__` is shorter but less explicit than spelling out every method.

## Problems met here

- **The ClickUp request.** "Create a ClickUp task automatically on acceptance" collided with two brief rules: no required external dependency (§7.6) and no background workers (§1c). The answer was an optional adapter (disabled unless both env vars are set), a synchronous call with a timeout, and failures logged without blocking acceptance.
- **Re-announcing "accepted".** An undo out of `accepted` would have triggered `TaskTrackerObserver` again and created a duplicate task. The lifecycle forbids that undo (see the requests domain README).
- **Outcome after manual moves.** If the manager closed a request before the requester answered, applying "close" again would fail. The applier checks the current status first.
