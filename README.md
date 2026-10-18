# AV Desk

Intake and feedback tool for video requests to the Audiovisual team of BRASA, the association of Brazilian students abroad.

Before AV Desk, video requests arrived through scattered Slack threads: vague asks, late deadlines, wrong tone discovered at the end, no visibility, no feedback. AV Desk replaces that with a structured briefing whose questions depend on the type of video, a deadline rule that flags rushed requests, a status lifecycle with a triage inbox, an automatic ClickUp task on acceptance, single-use feedback links on delivery, and a metrics page built from the answers.

The UI is in Brazilian Portuguese; code and documentation are in English.

> Each code directory has its own README explaining its files and design decisions.

## Quick start

Python 3.12 or newer.

### Directly on a machine

```bash
python -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

(On Windows: `.venv\Scripts\pip install -r requirements.txt` and `.venv\Scripts\python app.py`.)

```bash
ADMIN_PASSWORD=change-me .venv/bin/python app.py
```

Open http://localhost:8000. The admin area is at http://localhost:8000/admin.

### With Docker

```bash
docker build -t avdesk .
```

```bash
docker run -p 8000:8000 -v avdesk-data:/data -e ADMIN_PASSWORD=change-me avdesk
```

The start command is `python app.py` in both cases. On first boot the app creates its schema and loads `seed.json` into empty tables; later boots change nothing.

## How to use it

**Requester** (any BRASA board member or team lead, no account needed):
1. On the home page, choose "Um vídeo". Regular editorial-calendar posts belong to the Comunicação ClickUp flow, not here.
2. Fill in the briefing. Pick the type first: the questions adapt to it, and some only appear when an answer makes them relevant (tick Instagram and you must choose the publishing account; choose the tone "Outro" and you describe it). The bar at the top shows how complete the briefing is, and the deadline notice says whether the date gives enough notice.
3. Submit, then **keep the tracking link**: it is the only way back to the request. If the AV team asks for more information, the same page shows a form to complete and resubmit. When a cut is ready for review, the same page shows a "Sua vez de revisar" button that opens it on Frame.io, where you comment on the exact frame.
4. After delivery you receive a feedback link (copied or e-mailed by the AV manager). Your answer closes the request, or sends it back to production if you ask for major changes.

**AV manager** (`/admin`, shared password):
1. The inbox lists every request with deadline, rush flag, status and briefing score, plus each person's open workload. Filter by status, type, diretoria or person.
2. On a request, the available actions follow its status: accept (choose who produces; creates the ClickUp task), ask for information or decline (with a message to the requester), start production, send to review (with the Frame.io review link), request changes, deliver (with the Drive link), close, reopen, cancel. Actions that need information open their own form when clicked. "Desfazer" undoes the last change when that is safe.
3. After delivery, copy each feedback link or use the prepared e-mail link. The "copy Slack message" and Markdown export buttons help share the briefing.
4. `/admin/metricas` shows rush share, turnaround, on-time rate, response rate, ratings by type and diretoria, and briefing score by outcome.

**Reviewer** (named by the requester under "avaliadores"): open the link, rate four aspects from 1 to 5, choose an outcome, optionally comment. Each link works once and expires after 30 days.

## Configuration

Every setting is an environment variable with a default. No `.env` file is needed.

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `8000` | HTTP port; the app always binds `0.0.0.0` |
| `DATA_DIR` | `data` (`/data` in the container) | Directory of the SQLite file |
| `ADMIN_PASSWORD` | `avdesk-dev` (logged as insecure) | Shared password for the admin area |
| `SECRET_KEY` | derived from `ADMIN_PASSWORD` | Signs the session cookie; changing the password logs everyone out |
| `FEEDBACK_TTL_DAYS` | `30` | Days a feedback link stays valid |
| `WORKLOAD_WARN_THRESHOLD` | `3` | Open requests per person before the inbox warns |
| `COO_REVIEW_BUFFER_DAYS` | `3` | Extra business days reserved for the COO review of conference content |
| `CLICKUP_API_TOKEN` | empty | ClickUp personal token; with `CLICKUP_LIST_ID` enables task creation |
| `CLICKUP_LIST_ID` | empty | ClickUp list that receives one task per accepted request |

**SQLite path:** `$DATA_DIR/avdesk.sqlite3`.

ClickUp is optional: without both ClickUp variables, accepting a request simply creates no task, and the app needs no network access.

## Project structure

```
app.py                     the single start command
seed.json                  reference data: diretorias, analysts, request types, briefing questions
requirements.txt           five pinned dependencies
Dockerfile                 course template, only TODO 3 written (explicit source list)
ADR.md, AI_USAGE.md        decision records and AI usage log
avdesk/                    the application                         → avdesk/README.md
├── composition.py         composition root: builds and connects everything
├── config.py              settings from env vars (Singleton)
├── clock.py, tokens.py, task_tracker.py   adapters over time, randomness, ClickUp
├── db.py                  connections, schema, migrations, reference data
├── requests_domain/       asking for and producing a video        → its README
├── feedback_domain/       feedback after delivery                 → its README
├── services/              the only code that knows both domains   → its README
└── web/                   routes, templates, CSS, JS              → its README
tests/                     unit, integration, end-to-end           → tests/README.md
docs/                      guide, design notes, assignment brief   → docs/README.md
container/                 the course's Dockerfile template and contract checker (unchanged)
```

## Architecture

```
web/  →  RequestsFacade  ─┐                       ┌─  FeedbackFacade  ←  web/
         requests_domain  │   services/seam.py    │   feedback_domain
         (own tables)     ├─ StatusChanged ──────▶│   (own tables, no FK to requests)
                          │◀────── ResponseReceived┤
                          └── services/metrics.py ┘   (reads both)
```

Full diagrams: [architecture](docs/diagrams/architecture.svg) and [database schema](docs/diagrams/database.svg). Two domains, each with its own tables and one Facade, never importing each other. They cooperate through events: delivery creates feedback invites; the requester's feedback closes or reopens the request; metrics read both. All cross-domain code is in `avdesk/services/`, and the seam itself is `services/seam.py`. In Assignment 2 the events become Pub/Sub messages and the facades become HTTP APIs.

## Design patterns and principles

| Pattern | Where | Business reason |
|---|---|---|
| Singleton | `config.Config` | One consistent set of settings, created safely under waitress's threads |
| Factory Method | `StatusCommandFactory` | An admin button sends an action name; the right status command is built from one map |
| Builder | `BriefingBuilder`, `BriefingDirector` | A briefing has many optional parts; presets make tests short |
| Adapter | `SystemClock`, `SecureTokenGenerator`, `ClickUpTaskTracker`, SQLite repositories | Rules talk to our contracts; outside tools are swappable and fakeable |
| Proxy | `AdminOnly` | One object enforces the admin login for every admin call |
| Facade | `RequestsFacade`, `FeedbackFacade` | One front door per domain, the future service APIs |
| Observer | Status-change and response subjects + listeners in `services/` | Delivery creates feedback and acceptance creates a ClickUp task without the domains knowing each other |
| Strategy | `StandardLeadTime`, `ConferenceLeadTime` | Conference content needs extra notice for the COO review |
| Command | `StatusChange`, `AcceptRequest`, `DeliverRequest`, `Lifecycle` | Every status change is audited and a wrong click can be undone |

SOLID shows up as: one job per class (SRP), questions and actions as data (OCP), substitutable subclasses and fakes (LSP), reader/writer splits (ISP), contracts plus one composition root (DIP). Full reasoning and trade-offs: [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md). Decisions: [ADR.md](ADR.md).

## Project conventions

Each convention exists because of something in the business:

- **Business rules never touch Flask or SQL.** The rules that decide rush, validity or link expiry are the heart of the product and are tested without a server or database. Only `repository.py` files contain SQL; only `web/` imports Flask.
- **The briefing is data.** Request types, questions and follow-up questions (a question with `depends_on`/`depends_value` appears only after a given answer) live in `seed.json`. Lead times are confirmed; the question set is still validated with the team. The question set will keep changing as the team learns what context it needs, so it must change without code edits, and it reaches existing databases on the next start.
- **Reference data has two lifetimes.** Request types and questions follow `seed.json` on every boot; diretorias and analysts are seeded once, because requests point at them by id.
- **Schema changes are migrations.** `schema.sql` always describes today's shape; every change to an existing table is also appended to `MIGRATIONS` in `db.py`, so databases already in use are upgraded on start instead of being recreated.
- **Every status change goes through the action table** (`ACTIONS` in `lifecycle.py`). The status is the audited core of the triage process; no code updates it any other way, and every change writes a timeline row the requester can see.
- **Reviews happen on Frame.io.** "Enviar para revisão" requires the Frame.io link, and the requester reviews there; the app links to it because Frame.io cannot be embedded.
- **Changes that left the domain can't be undone.** Moves into or out of accepted (ClickUp task), delivered (feedback links) and closed are final; undo is for wrong clicks, not for rewriting history.
- **Domains exchange copies, never references.** Events carry frozen snapshots, and feedback tables keep their own copy of the delivered request instead of a foreign key, so each domain can live in its own service later.
- **Links are the authorisation.** Requesters and reviewers have no accounts (about 40 board members, a few hundred requests a year); an unguessable token in the URL grants access to exactly one request or one feedback form.
- **Too little notice is flagged, not blocked.** Real deadlines sometimes can't move; the app asks why, shows the earliest realistic date, and makes rush visible in the inbox and metrics.
- **Business days only.** Lead time counts Monday to Friday; holidays are deliberately not modelled.
- **Only the requester's feedback moves the request.** Reviewers' answers count in metrics but never close or reopen anything.
- **Placeholders are explicit.** Unknown BRASA data is marked `[A CONFIRMAR]` and never invented. Seeded analysts have generic names ("Analista AV 1"), never real people.
- **Language.** UI text, URLs and business codes (`redes_sociais`, `objetivo`, `/pedido/novo`) are Brazilian Portuguese and follow BRASA's language rules ("a BRASA", "estudante", "conferência", product names in full). Code identifiers, comments and docs are English.
- **Visual identity.** Colours and type follow the Manual de ID Visual BRASA 2025 (text colour per background, palette never as text, Lato only, nothing from a CDN).
- **Comments explain why, never what.** Each pattern is named in its class or module docstring.
- **Time is UTC and injected.** Rules get "now" from a `Clock`; timestamps are stored as ISO text.
- **Commits describe what changed and why**; test-first work shows as "(TDD red)" commits followed by the implementation.

## Tests and coverage

```bash
.venv/bin/python -m pytest --cov=avdesk --cov-report=term-missing
```

Latest result: **208 tests passed, 97% line coverage of `avdesk/`.** Core business logic: `leadtime.py` 100%, `lifecycle.py` 99%, `requests_domain/facade.py` 100%, `validators.py` 93%, `feedback_domain/rules.py` 100%, `feedback_domain/facade.py` 96%, `services/seam.py` 100%, `services/metrics.py` 100%.

Pyramid: 128 unit tests (62%), 59 integration tests (28%, real SQLite in a temp dir), 21 end-to-end tests (10%, Flask test client). Unit tests sit below the 70–80% the testing slides recommend because the repositories and the two-domain seam are tested against a real database; see ADR-4 and [tests/README.md](tests/README.md).

## Container contract evidence (`container/run.sh`)

Run on 2026-10-18 with the provided, unmodified `container/run.sh`, after the schema migrations and the briefing-catalog sync were added (a second boot still changes no row counts):

```text
=== SDD Assignment 1 contract check ===
Repository: /c/Users/loren/Documents/IE-University-Files/y3/devops/sdd-assignment-1

==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)

==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 53 MB

==> Start on PORT=8000 and reach it from the host
  PASS  HTTP 200 from http://localhost:8000/

==> SQLite file under DATA_DIR
  PASS  found in /data: avdesk.sqlite3 

==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  PASS  row counts unchanged across restart: analysts=3
 briefing_questions=31
 diretorias=8
 feedback_invites=0
 feedback_responses=0
 request_events=0
 request_types=4
 requests=0 

==> PORT override is honoured (not hardcoded)
  PASS  HTTP 200 from http://localhost:9123/

=== ALL CHECKS PASSED ===
Paste this output into your README as the §7 evidence.
```

Note for Windows (Git Bash): the script calls `mktemp -t sdd-check`, which GNU `mktemp` rejects because the template has no `XXX`, and `python3` is only the Microsoft Store placeholder there. It was run with two tiny wrappers placed first on `PATH`, one adding `.XXXXXX` to the template and one pointing `python3` at the installed Python. The script itself was not changed. On macOS or Linux it runs as is.

## Out of scope (deliberately)

- Outbound e-mail or Slack posting: the admin page has copy buttons and a `mailto:` link instead.
- Google Drive integration and file uploads: deliveries are Drive links.
- Holidays in the lead-time rule: only weekends are non-working days.
- Per-user accounts: requesters and reviewers are authorised by unguessable links, the admin by one shared password.
- Background workers and message brokers (forbidden by §1c; Pub/Sub is Assignment 2).
- Embedding Frame.io: Frame.io does not support being shown inside other sites, so the review opens on Frame.io itself.

## Documentation map

| Document | What it gives you |
|---|---|
| [docs/REPORT.md](docs/REPORT.md) | The assignment report: SDLC and goals, diagrams, testing, AI disclosure |
| [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md) | Problem, reason and trade-off for every pattern and principle |
| [ADR.md](ADR.md) | Formal architecture decision records |
| [AI_USAGE.md](AI_USAGE.md) | How AI was used, prompt by prompt |
| `avdesk/README.md`, `avdesk/*/README.md`, `tests/README.md` | Directory-level detail: files, decisions, problems, how to extend |
| [docs/ASSIGNMENT_BRIEF.md](docs/ASSIGNMENT_BRIEF.md) | The original course brief |
