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
Status: Superseded by [6]
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

## 5. No outbound e-mail, Slack or Frame.io integration
Date: 2026-10-18
Status: Decided
Context: Requesters and reviewers have to be told when a request changes, when feedback is due and when a cut is ready for review. BRASA's team works in Slack, e-mail and Frame.io, so sending messages and embedding the review player automatically were the obvious features.
Decision: The app sends nothing on its own and embeds nothing. The admin page offers a "copy Slack message" button, copyable feedback links and a pre-filled `mailto:` link; the requester follows progress on the private tracking page, which links to the Frame.io review in a new tab.
Alternatives considered: SMTP e-mail on each status change, rejected because it needs credentials, a sending domain and retry handling for a few hundred messages a year, and §1c forbids the background worker reliable sending would need. A Slack webhook, rejected for the same reasons plus a workspace app approval. Embedding the Frame.io player in the tracking page, rejected because Frame.io does not support embeds on other sites and comments fail inside them. (ClickUp task creation was kept, because accepted work must enter the team's tracker, and it fails safe when not configured.)
Consequences: The AV manager spends one click to share each link, in exchange for no secrets beyond ADMIN_PASSWORD and no delivery failures to handle. In Assignment 2 a notification service can subscribe to the same status events and send these messages without changing either domain.

## 6. Two services split at the delivery seam, talking over HTTP
Date: 2026-11-24
Status: Decided
Context: Assignment 2 requires one service per domain, each with its own container and database, and forbids message brokers. ADR-2 drew the seam at delivery and expected the in-process events to become Pub/Sub messages; without a broker they have to become HTTP calls.
Decision: The seam stays where ADR-2 put it. `services/requests` owns intake, lead time, the lifecycle, the briefing catalog and the ClickUp task; `services/feedback` owns invites and responses. Each folder has its own package (`avdesk_requests`, `avdesk_feedback`), requirements file, migrations and tests, and nothing is shared at runtime. What crossed the seam in-process now crosses it as HTTP: (1) delivering a request makes the requests service `POST` the delivered-work snapshot to the feedback service, which creates the invites; (2) the requester's verdict makes the feedback service `POST` the outcome to the requests service, which closes or reopens the request; (3) the metrics page is assembled in the browser from both services. The small infrastructure modules (clock, tokens, SQL Server adapter, migration runner, health probe) are copied into each service rather than shared.
Alternatives considered: Moving the seam so that feedback lives inside requests, rejected because ADR-2/3 already removed every join across it (feedback keeps a snapshot, not a foreign key), so the split needs no new calls for reads. A shared internal library for the copied infrastructure, rejected because it would couple the two images' builds and releases again for about 250 lines that change rarely; if they start to diverge in fixes, that is the signal to extract one.
Consequences: ADR-2 held, but its events are no longer fire-and-forget inside one transaction: each call across the seam can now fail on its own, so every outbound call needs a timeout and a designed failure. The domain packages were moved unchanged except for their imports, which is the evidence the A1 seam was in the right place. The duplicated infrastructure must be fixed in two places. When the other service is unavailable, the design degrades rather than fails. The user's own action (delivering, answering) is always stored. The missed call is flagged on the sender's data, and the AV manager retries it with one click. Every other page keeps working (ADR-10).

## 7. One database per service, versioned SQL migrations applied at startup
Date: 2026-11-25
Status: Decided
Context: Assignment 1 created its SQLite schema on first boot. Assignment 2 gives each service its own SQL Server database (Azure SQL serverless in production) with its own login, and the schema must now change in place while rows are kept.
Decision: Each service owns numbered T-SQL files in `services/<name>/migrations/`, starting at `001_init.sql`, plus a small runner of its own (`migrations.py`). The runner records version, name, a SHA-256 checksum and the time in `schema_migrations`. It applies each pending file in its own transaction, splitting batches on `GO`, before the app accepts requests, and it refuses to start if an applied file was edited. The requests database holds the request tables and the seeded catalog; the feedback database holds invites and responses. The only link between them is `feedback_invites.request_id`, a plain integer (ADR-3). Referential integrity at the seam is therefore compensated in code: invites carry a snapshot of the delivered work, a verdict for an unknown request gets a 404, and a repeated delivery is recognised by `(request_id, delivered_at)`. Each login (`avdesk_requests`, `avdesk_feedback`) has DDL, read and write rights in its own database only: `db/init.sql` locally, contained users on Azure (`infra/create_db_users.py`). The SQLite data of Assignment 1 was demo data only, so no rows were carried across engines; the migration that changes a populated table (`003`, adding the pending flags with a default) runs on live rows locally and on Azure.
Alternatives considered: Alembic, rejected because the code has no SQLAlchemy models; it would add a tool and an ORM only to run SQL files I already write by hand, and the runner is about 100 lines with its own tests. Running migrations as a separate pipeline step against Azure SQL, rejected because CI must never touch Azure SQL, and because a container that migrates itself behaves the same in compose, CI and Azure. Down-migrations, rejected: forward-only is allowed, and down-migrations are rarely trusted under pressure.
Consequences: Recovery plan for a bad migration in production:
(1) A migration that fails rolls back as a whole. The new replica fails to start, and the previous revision keeps serving, since Container Apps only moves traffic to a healthy revision.
(2) The fix is a new numbered migration, never an edit.
(3) If a migration succeeded but damaged data, restore the database with Azure SQL point-in-time restore into a new database and point DATABASE_URL at it.
Startup migrations are safe only because each app has at most one replica (ADR-8). With more replicas they would race, and would need a lock (`sp_getapplock`) or a one-off job.

## 8. Serverless hosting: Container Apps Consumption, Azure SQL serverless free offer, static website
Date: 2026-11-25
Status: Decided
Context: The app must cost nothing while idle, which is most of the time: a few hundred requests a year, used during working hours.
Decision: Both services run on Azure Container Apps (Consumption plan, one environment `lhoffmann-env`), with 0 to 1 replica and public HTTPS ingress. Each has its own serverless database (`lhoffmann-requests-db`, `lhoffmann-feedback-db`) on one logical server, on the free offer: 0.5–1 vCore, auto-pause after 60 minutes, 32 GB. When the monthly allowance runs out, the database pauses instead of billing. The UI is a Storage static website (`lhoffmannui`), and images live on GHCR. Infrastructure is created once by `infra/setup.sh` (Azure CLI) and then changed only by the pipeline. Everything is in `norwayeast`, chosen from the five regions the subscription allows. `spaincentral` refuses free-offer databases, and `switzerlandnorth` refused new SQL servers. A failed attempt there still holds the name `lhoffmann-sql`, so the server is `lhoffmann-sql2`.
Cost model:
- Container Apps bills per vCPU-second and GiB-second of running replicas, with a free monthly grant this traffic stays well inside.
- The databases are free.
- Storage costs cents per GB.
- GHCR is free for public images.
Nothing has a fixed monthly cost.
Alternatives considered: Bicep instead of CLI commands, rejected for now: the setup runs once and the script is shorter to read, at the cost of no drift detection. Azure Container Registry, rejected because its Basic tier has a fixed monthly fee and GHCR does the same job. App Service, rejected because it is always on.
Consequences: Scale to zero means cold starts, in layers:
- After idle, the first request starts a container, which takes a few seconds.
- The container may then find its database paused, and resuming takes up to about a minute. `Database` therefore retries the connection with exponential backoff: 8 attempts, about 70 s.
- `/health` tries only once, so it answers quickly while the database resumes.
- Container Apps may answer that first request with 503 after about 30 s. The UI retries 502/503/504 and network errors, then shows "o AV Desk está acordando".
- The post-deploy health check waits up to 5 minutes.
- Calls across the seam use a 10 s timeout: enough to wake the other container, but not its database. A failure leaves a retry button (ADR-6).
- At most one replica keeps the startup migrations from running twice.

At 100x traffic:
- Raise the maximum replicas, and move migrations to a one-off Container Apps job, or to a SQL lock, so replicas cannot race.
- Leave the free offer for a database with a minimum vCore, so no request waits for a resume.
- Keep one replica warm in working hours.
- Add connection pooling.
- Replace the manual retry button with a queue that retries by itself.

## 9. Pipeline: one workflow, CI gates every deploy, a real cross-seam test
Date: 2026-11-25
Status: Decided
Context: Every push must be tested, and every merge to main deployed with no manual step, but only when CI passed on that same commit. CI may not touch Azure SQL.
Decision: One workflow (`.github/workflows/pipeline.yml`). On every push and pull request it runs four jobs:
- `specs` validates `system.yaml` against `system.schema.json`, and both OpenAPI documents against the OpenAPI specification.
- `test`, once per service, runs ruff, then all unit and integration tests against a throwaway SQL Server container, with `--cov-fail-under=70`. The container's password is generated per run.
- `cross-seam` starts both real services on two HTTP ports with two databases and runs four journeys: delivery creates invites; the requester's approval closes the request; feedback is down at delivery and the retry creates the invites; requests is down at the verdict and the resend applies it.
- `build` builds both images.

The deploy jobs `need` all four and run only for a push to main. They:
- push the images tagged with the commit SHA;
- sign in to Azure as the `lhoffmann-github` managed identity through OIDC;
- pass secrets to Container Apps as `secretref` variables;
- upload the UI with a generated `config.js`;
- fail unless both `/health` endpoints report that SHA within 5 minutes.

Each service's own suite replaces the other with a stub, a class implementing the same port. The cross-seam test then checks that the two halves really agree on paths, bodies, tokens and status codes.
Alternatives considered: Separate CI and CD workflows linked by `workflow_run`, rejected because the deploy would have to re-check which commit passed. Running the cross-seam test against `docker compose up`, rejected as slower and harder to diagnose: starting the apps in-process over real HTTP proves the same contract. A stored service principal secret, rejected in favour of OIDC, which leaves nothing to leak or rotate.
Consequences: Deliberately not tested:
- the browser JavaScript, which I checked by hand in the browser at each phase;
- the Azure resources themselves, beyond the post-deploy health check;
- the ClickUp adapter against the real ClickUp API;
- performance.

Integration tests are about half the suite, because the riskiest code (transactions, idempotent seeding, retries, the seam) means something only against a real SQL Server.

## 10. Not built: a message broker between the services
Date: 2026-11-25
Status: Decided
Context: Two calls cross the seam: delivery creates invites, and the verdict closes or reopens the request. When the receiving service is down, the sender cannot wait, because it is inside a user's click. A broker (Service Bus, RabbitMQ) would make both calls asynchronous and retry them automatically, which is what ADR-2 originally expected. §1c rules out brokers and background workers.
Decision: Not built. Each call is synchronous with a 10 s timeout. A failure is stored as a flag on the sender's own data (`requests.invites_pending`, `feedback_responses.verdict_pending`), which the admin page shows with a one-click retry. The receiver is idempotent, so a retry never duplicates: invites are keyed by delivery, and a verdict changes nothing unless the request is still delivered.
Alternatives considered: The UI calling both services itself (a client-side flow), rejected because the requester's verdict must reach the request even if the browser closes right after submitting, and at least one flow must be server-side. An outbox table drained by a background thread, rejected because that is a background job runner.
Consequences: A missed call waits for the AV manager to press a button; nothing retries by itself. At this volume that is rare, and it is visible rather than silent. A broker becomes worth building in any of three cases:
- retries become routine, for example many cold-start timeouts;
- a third consumer of the same events appears, such as the notification service from ADR-5;
- the manager can no longer be the one who notices.

At that point the two flags become an outbox, and the retry button becomes a subscriber.
