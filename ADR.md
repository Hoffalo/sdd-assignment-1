# Architecture Decision Records

## 1. Python with Flask, server-rendered templates and stdlib sqlite3
Date: 2026-10-10
Status: Decided
Context: AV Desk is a small internal tool for about 40 BRASA board members and a few hundred video requests a year. It must run as one process in one container, store everything in SQLite, and I must be able to explain every line of it on paper.
Decision: Python 3.12 with Flask and Jinja templates, served by waitress, using the standard-library sqlite3 module behind repository interfaces instead of an ORM.
Alternatives considered: Django, rejected because its admin, ORM and project scaffolding are far more than this app needs and the ORM would hide the repository seam I want to show between domain rules and storage. FastAPI, rejected because its main benefits (async, automatic JSON schemas) do not help an app that renders HTML forms. An ORM such as SQLAlchemy, rejected because hand-written parameterised SQL in two small adapters is easier to explain than ORM sessions.
Consequences: Few dependencies (five pinned packages) and explicit code, at the cost of writing SQL and form parsing by hand. Swapping SQLite later means writing a new adapter for the same RequestReader/RequestWriter contracts, not touching the rules.

## 2. Two domains, one Facade each, connected only by events and snapshots
Date: 2026-10-10
Status: Decided
Context: The assignment requires two domains that could each become a separate service in Assignment 2. AV Desk naturally splits at delivery: taking in and producing a request, then collecting feedback about the result.
Decision: `requests_domain` (briefing, lead time, lifecycle) and `feedback_domain` (invites, responses) never import each other. Each exposes one Facade. Only `avdesk/services/` may know both, and exactly three things cross the seam: (1) a `StatusChanged` event carrying an immutable `RequestSnapshot` when a request is delivered, which creates feedback invites; (2) the requester's feedback outcome, which closes or reopens the request through `RequestsFacade.perform`; (3) the metrics page, which reads from both facades. The same Observer mechanism also creates the ClickUp task when a request is accepted.
Alternatives considered: One shared package where feedback code reads the `requests` table directly, rejected because it welds the domains together and would need a rewrite to split. Calling the feedback facade directly from the requests facade, rejected because requests would then depend on feedback (a Coupler smell) instead of announcing an event.
Consequences: The Observer here is the in-process, direct-reference version from class, so a listener runs in the same thread and cannot survive a service split. In Assignment 2 the event becomes a Pub/Sub message through a broker and facade calls become HTTP calls, without changing the domain code.

## 3. Feedback keeps a soft reference and a snapshot, with no foreign key into requests
Date: 2026-10-10
Status: Decided
Context: Every feedback invite and response is about one request, so the two domains' data is related. Assignment 2 will give each domain its own database, where a cross-database foreign key cannot exist.
Decision: `feedback_invites.request_id` is a plain integer with no FOREIGN KEY. Each invite stores a snapshot of what it needs from the request at delivery time (public code, title, type label, diretoria, delivery link, dates). Foreign keys are used only inside a domain (for example `request_events.request_id` and `feedback_responses.invite_id`).
Alternatives considered: A hard foreign key from `feedback_invites` to `requests`, rejected because it makes the feedback tables unusable without the requests tables and blocks the split. Storing nothing but the id and querying the requests tables when showing an invite, rejected for the same reason.
Consequences: Feedback can be lifted into its own database unchanged. The snapshot may become stale if a request is edited after delivery; that is acceptable because it records what was delivered, and the metrics service joins the two sides by `request_id` in code.

## 4. Test-first pyramid with fakes for the database and an injected clock
Date: 2026-10-17
Status: Decided
Context: The brief requires at least 70% coverage of the core business logic of both domains, and the class asks for TDD, the testing pyramid, fixtures and the right use of mocks, stubs and fakes. Rules that depend on dates (lead time, link expiry) would make tests flaky if they read the real clock.
Decision: The core rules (configuration, lead time, briefing validation and scoring, the lifecycle, feedback rules) were written test-first with a red commit followed by a green commit; repositories, facades and services were tested alongside their code. Rules are unit-tested with no database, using `FixedClock`, `SequentialTokens` and `mocker` mocks for collaborators; repositories, seeding and the domain seam are integration-tested against a real SQLite file in a temp dir; a few end-to-end journeys use the Flask test client. Coverage is measured with `pytest --cov=avdesk`.
Alternatives considered: Mocking the database everywhere to push the unit share to 75–80%, rejected because the riskiest code (atomic status transitions, idempotent seeding, the absence of a cross-domain foreign key) is only meaningful against real SQLite. Browser-driven E2E tests (Playwright), rejected as slow and heavy for one container.
Consequences: 183 tests run in about 15 seconds with 97% coverage; the split is 62% unit, 27% integration, 10% end-to-end, below the slides' unit share by choice. Templates and JavaScript are covered only indirectly through the end-to-end tests.
