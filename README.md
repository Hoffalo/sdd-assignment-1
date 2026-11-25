# AV Desk

Intake and feedback tool for video requests to the Audiovisual team of BRASA, the association of Brazilian students abroad.

Before AV Desk, video requests arrived through scattered Slack threads: vague asks, late deadlines, the wrong tone discovered only at the end, no visibility and no feedback. AV Desk replaces that with:
- a structured briefing whose questions depend on the type of video;
- a deadline rule that flags rushed requests;
- a status lifecycle with a triage inbox;
- an automatic ClickUp task when a request is accepted;
- single-use feedback links on delivery;
- a metrics page built from the answers.

**Live:** https://lhoffmannui.z50.web.core.windows.net (static UI on Azure Storage, calling two Container Apps).

The UI is in Brazilian Portuguese; code and documentation are in English.

> Assignment 2 split the Assignment 1 monolith into two services. Each code directory has its own README explaining its files and decisions.

## Architecture

```
                 browser (ui/ on the Storage static website)
                 │  HTTPS + CORS            │  HTTPS + CORS
                 ▼                          ▼
   services/requests  ── POST /invites ──▶  services/feedback
   (intake, lifecycle, ◀── POST /requests/{id}/verdict ──  (invites, answers,
    catalog, ClickUp)                                        feedback metrics)
          │                                        │
   requests database                          feedback database
   (own login, no access to the other)        (own login, no access to the other)
```

There are two services, one per domain, each with its own container, database and login. They meet at the delivery seam drawn in Assignment 1 (ADR-2, ADR-6):
- When a request is delivered, the requests service sends a copy of the delivered work to the feedback service, which creates the invites.
- When the requester answers, the feedback service sends the verdict back, and the request is closed or reopened.
- The metrics page is joined in the browser from both services.

Every call across the seam has a 10 s timeout. **If the other service is down, nothing is lost.** The user's action is saved, the missed call is flagged, and the admin page offers a one-click retry. Every other page keeps working (ADR-10).

The full description is in [`system.yaml`](system.yaml), plus the OpenAPI documents for [requests](services/requests/openapi.yaml) and [feedback](services/feedback/openapi.yaml).

## Run it locally: whole system

You need Docker Desktop. From a clean clone:

```bash
docker compose up --build
```

Then open http://localhost:8080. The admin area is at http://localhost:8080/admin/entrar.html, and the local password is `local-admin`.

| Container | What it is | Port |
|---|---|---|
| `sqlserver` | SQL Server 2022, one database per service | not published |
| `db-init` | Runs [`db/init.sql`](db/init.sql) once (databases and logins), then exits | — |
| `requests` | Requests service | 8001 |
| `feedback` | Feedback service | 8002 |
| `ui` | Stock `nginx:alpine` serving `ui/` (no Dockerfile) | 8080 |

To try partial failure, run `docker compose stop feedback`, deliver a request, and look at the admin page. Then run `docker compose start feedback` and press "Criar links agora".

The compose file carries throwaway local passwords so a clean clone runs with no setup. Override them in a `.env` file. They are never used on Azure.

## Run a single service

Python 3.12 and a SQL Server you can reach. For example, start only the database with `docker compose up sqlserver db-init`, after publishing port 1433 in compose. Then:

```bash
cd services/requests
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
DATABASE_URL='mssql://avdesk_requests:LocalDev_Only_Requests_1@localhost:1433/avdesk_requests' \
ADMIN_PASSWORD=local-admin ADMIN_TOKEN_SECRET=local-only-signing-key \
FEEDBACK_URL=http://localhost:8002 PORT=8001 .venv/bin/python app.py
```

The feedback service is the same, from `services/feedback`, with its own `DATABASE_URL`, `ADMIN_TOKEN_SECRET`, `REQUESTS_URL` and `PORT=8002`. Each service applies its migrations on start; a second start applies nothing. Every variable each service reads, with its default, is listed in [`system.yaml`](system.yaml).

## Tests and coverage

The integration tests need a SQL Server. One throwaway container is enough:

```bash
docker run -d --name avdesk-test-sql -e ACCEPT_EULA=Y -e MSSQL_SA_PASSWORD='<a password>' -p 14330:1433 \
  mcr.microsoft.com/mssql/server:2022-latest
export TEST_SQLSERVER_URL='mssql://sa:<a password>@localhost:14330/master'
```

| Suite | Command | Latest result |
|---|---|---|
| requests | `cd services/requests && python -m pytest --cov=avdesk_requests` | 262 tests, 98% coverage |
| feedback | `cd services/feedback && python -m pytest --cov=avdesk_feedback` | 112 tests, 97% coverage |
| both together | `python -m pytest` (repository root) | 4 cross-seam journeys over real HTTP |
| lint | `ruff check services tests` | clean |

Without `TEST_SQLSERVER_URL` the integration tests are skipped, not failed. CI always sets it. In each service's suite the other service is a stub; the cross-seam suite runs both for real, including an outage on each side ([tests/README.md](tests/README.md), ADR-9).

## How deployment works

[`.github/workflows/pipeline.yml`](.github/workflows/pipeline.yml) runs on every push and pull request. It:
- validates `system.yaml` and both OpenAPI documents;
- lints and tests each service against a throwaway SQL Server, failing below 70% coverage;
- runs the cross-seam journeys;
- builds both images.

On a push to `main`, and only if all of that passed in the same run, it then:
- pushes `ghcr.io/hoffalo/avdesk-{requests,feedback}:<commit sha>`;
- signs in to Azure as the `lhoffmann-github` managed identity through OIDC, so no Azure password is stored anywhere;
- updates both Container Apps, passing secrets as Container Apps secrets;
- uploads `ui/` to the static website with a generated `config.js` that holds both service URLs;
- fails unless both `/health` endpoints report the new commit within 5 minutes.

Changes reach `main` only through pull requests, so CI runs before CD.

The one-time initial setup (resource group, identity, SQL server and databases, Container Apps environment and apps, storage account) is scripted in [`infra/setup.sh`](infra/setup.sh) and documented step by step in [infra/README.md](infra/README.md). Every resource is pay-per-use and scales to zero (ADR-8).

## How to use it

**Requester** (any BRASA board member or team lead, no account needed):
1. On the home page, choose "Um vídeo".
2. Fill in the briefing. Pick the type first: the questions adapt to it. The bar at the top shows how complete the briefing is, and the deadline notice says whether the date gives enough notice.
3. Submit, then **keep the tracking link**: it is the only way back to the request. If the AV team asks for more information, the same page shows a form to complete and resubmit. When a cut is ready for review, it shows a button that opens the cut on Frame.io.
4. After delivery you receive a feedback link. Your answer closes the request, or sends it back to production if you ask for major changes.

**AV manager** (`admin/entrar.html`, shared password):
1. The inbox lists every request with its deadline, rush flag, status and briefing score, plus each person's open workload.
2. On a request, the available actions follow its status. Delivering creates the feedback links in the feedback service. If that service was down, the page says so and offers "Criar links agora". The same applies to "Reenviar veredito" when the requester's answer could not reach the request.
3. The metrics page shows rush share, turnaround, on-time rate, response rate, ratings by type and diretoria, and briefing score by outcome. If the feedback service is down, only its half is missing, with a notice.

**Reviewer**: open the link, rate four aspects from 1 to 5, choose an outcome, and optionally comment. Each link works once and expires after 30 days.

When the app has been idle, the first page may take up to a minute while Azure starts a container and resumes its database. The page says "o AV Desk está acordando" and retries by itself.

## Project structure

```
docker-compose.yml          the whole system locally
system.yaml                 machine-readable system description (validated against system.schema.json)
db/init.sql                 local databases and logins, one per service
services/requests/          requests service: Dockerfile, requirements, migrations/, openapi.yaml, tests/
services/feedback/          feedback service: same layout
ui/                         static pages (HTML, CSS, ES modules); config.js holds the service URLs
tests/cross_seam/           both services together over real HTTP
infra/                      one-time Azure setup (script + README)
.github/workflows/          CI/CD pipeline
ADR.md, AI_USAGE.md         decision records (1-10) and AI usage log
docs/                       report, design notes, diagrams
```

## Design patterns and principles

| Pattern | Where | Business reason |
|---|---|---|
| Singleton | `Config` in each service | One consistent set of settings, created safely under waitress's threads |
| Factory Method | `StatusCommandFactory` | An admin button sends an action name; the right status command is built from one map |
| Builder | `BriefingBuilder`, `BriefingDirector` | A briefing has many optional parts; presets keep tests short |
| Adapter | SQL Server repositories, `ClickUpTaskTracker`, `HttpFeedbackInvites`, `HttpRequestVerdicts`, clock, tokens | Rules talk to our contracts; databases, HTTP and vendors are swappable and fakeable |
| Proxy | `AdminOnly` | One object enforces the admin token for every admin call |
| Facade | `RequestsFacade`, `FeedbackFacade` | One front door per domain; the HTTP APIs call only these |
| Observer | Status-change and response subjects, plus their listeners | Delivery creates invites, acceptance creates a ClickUp task, and a verdict moves the request, without the domains knowing each other |
| Strategy | `StandardLeadTime`, `CLevelApprovalLeadTime` | A video that needs C-Level approval needs extra notice |
| Command | `StatusChange`, `Lifecycle` | Every status change is audited, and a wrong click can be undone |

Full reasoning and trade-offs: [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md). Decisions: [ADR.md](ADR.md).

## Project conventions

- **Business rules never touch Flask, SQL or HTTP.** Only `repository.py` files contain SQL, only `web/` imports Flask, and only the `*_client.py` adapters make HTTP calls.
- **Each service owns its data.** No service reads the other's database. Feedback keeps a snapshot of the delivered request instead of a foreign key (ADR-3, ADR-7).
- **Schema changes are new migration files**, never edits; a checksum stops a service whose applied migration was edited.
- **The briefing is data.** Types, questions and follow-up questions live in `services/requests/seed.json` and reach existing databases on the next start.
- **Every status change goes through the action table** (`ACTIONS` in `lifecycle.py`), and every change writes a timeline row.
- **Calls across the seam never fail the user's action.** They time out after 10 s, and are flagged for a retry instead.
- **Links are the authorisation.** Requesters and reviewers have no accounts; an unguessable token in the URL fragment grants access to one request or one form.
- **Too little notice is flagged, not blocked**, and lead time counts calendar days.
- **Only the requester's feedback moves the request.**
- **Time is UTC and injected**, stored as `DATETIME2` in UTC.
- **No secrets in the repository.** Local passwords are throwaway compose defaults; Azure secrets live in GitHub Actions secrets and Container Apps secrets.
- **Comments explain why, never what.** Each pattern is named in its class or module docstring.
- **Language.** UI text and business codes are Brazilian Portuguese; code and docs are English.

## Secret incidents

None so far. A leaked secret would be revoked or rotated within 24 hours and recorded here: what leaked, when, and what was done.

## Documentation map

| Document | What it gives you |
|---|---|
| [docs/REPORT.md](docs/REPORT.md) | The report: architecture before and after, deployment, databases, evidence, AI disclosure |
| [ADR.md](ADR.md) | Architecture decision records 1-10 |
| [AI_USAGE.md](AI_USAGE.md) | How AI was used, prompt by prompt, infrastructure files included |
| [infra/README.md](infra/README.md) | Azure resources, their cost, and how to reproduce the setup |
| [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md) | Problem, reason and trade-off for every pattern and principle |
| `services/*/avdesk_*/domain/README.md`, `tests/README.md`, `ui/README.md` | Directory-level detail |
