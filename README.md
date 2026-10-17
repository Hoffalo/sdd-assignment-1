# AV Desk

Intake and feedback tool for video requests to the Audiovisual team of BRASA, the association of Brazilian students abroad.

A board member fills a structured briefing whose questions depend on the type of video. The request lands in the AV manager's inbox, moves through a lifecycle (submitted → accepted → in production → in review → delivered → closed), creates a ClickUp task when accepted, and on delivery issues single-use feedback links. The answers feed a metrics page (turnaround, on-time rate, ratings by type and diretoria).

The UI is in Brazilian Portuguese; code and documentation are in English.

## Run it

Python 3.12 or newer.

### Directly on a machine

```bash
python -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

(On Windows: `.venv\Scripts\pip install -r requirements.txt`.)

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

## Tests and coverage

```bash
.venv/bin/python -m pytest --cov=avdesk --cov-report=term-missing
```

Latest result: **183 tests passed, 97% line coverage of `avdesk/`.** Core business logic: `leadtime.py` 100%, `lifecycle.py` 99%, `requests_domain/facade.py` 100%, `validators.py` 93%, `feedback_domain/rules.py` 100%, `feedback_domain/facade.py` 96%, `services/seam.py` 100%, `services/metrics.py` 100%.

Pyramid: 114 unit tests (62%), 50 integration tests (27%, real SQLite in a temp dir), 19 end-to-end tests (10%, Flask test client). Unit tests sit below the 70–80% the testing slides recommend because the repositories and the two-domain seam are tested against a real database; see ADR-4.

## Container contract evidence (`container/run.sh`)

Run on 2026-10-17 with the provided, unmodified `container/run.sh`:

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

## Architecture

```
web/  →  RequestsFacade  ─┐                       ┌─  FeedbackFacade  ←  web/
         requests_domain  │   services/seam.py    │   feedback_domain
         (own tables)     ├─ StatusChanged ──────▶│   (own tables, no FK to requests)
                          │◀────── ResponseReceived┤
                          └── services/metrics.py ┘   (reads both)
```

- `avdesk/requests_domain/`: briefing, lead time, lifecycle, request storage.
- `avdesk/feedback_domain/`: invites, responses, feedback rules.
- `avdesk/services/`: the only code that knows both domains. The seam is `services/seam.py`.
- `avdesk/composition.py`: the only place concrete classes are chosen and observers are attached.

The reasoning for each pattern and principle is in [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md); the five formal decisions are in [ADR.md](ADR.md).

## Out of scope (deliberately)

- Outbound e-mail or Slack posting: the admin page has copy buttons and a `mailto:` link instead.
- Google Drive integration and file uploads: deliveries are Drive links.
- Holidays in the lead-time rule: only weekends are non-working days.
- Per-user accounts: requesters and reviewers are authorised by unguessable links, the admin by one shared password.
- Background workers and message brokers (forbidden by §1c; Pub/Sub is Assignment 2).
