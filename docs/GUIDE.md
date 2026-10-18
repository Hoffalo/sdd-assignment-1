# AV Desk: the complete guide

This guide explains the whole project from top to bottom. It assumes no prior knowledge: every term is explained the first time it appears, and each part builds on the one before it. Read it in order the first time; afterwards, the table of contents works as a reference.

1. [The problem](#1-the-problem)
2. [What the app does: one request's life](#2-what-the-app-does-one-requests-life)
3. [The rules the assignment imposes](#3-the-rules-the-assignment-imposes)
4. [The stack: which tools, and why](#4-the-stack-which-tools-and-why)
5. [The shape of the code: layers and domains](#5-the-shape-of-the-code-layers-and-domains)
6. [Three ideas that hold everything together](#6-three-ideas-that-hold-everything-together)
7. [Startup: how the program assembles itself](#7-startup-how-the-program-assembles-itself)
8. [The requests domain in practice](#8-the-requests-domain-in-practice)
9. [The feedback domain in practice](#9-the-feedback-domain-in-practice)
10. [The seam: how two domains cooperate without knowing each other](#10-the-seam-how-two-domains-cooperate-without-knowing-each-other)
11. [The web layer: what the browser actually talks to](#11-the-web-layer-what-the-browser-actually-talks-to)
12. [The data: every table and why it looks that way](#12-the-data-every-table-and-why-it-looks-that-way)
13. [Tests: how we know it works](#13-tests-how-we-know-it-works)
14. [Running it, configuring it, shipping it](#14-running-it-configuring-it-shipping-it)
15. [Problems we ran into, and what we did about them](#15-problems-we-ran-into-and-what-we-did-about-them)
16. [Where Assignment 2 cuts](#16-where-assignment-2-cuts)
17. [Quick reference](#17-quick-reference)

---

## 1. The problem

BRASA's Audiovisual team (the AV *gerência*, inside the Comunicação *diretoria*) produces videos for the rest of the association: teasers for conferences, institutional videos, social media videos outside the regular editorial calendar, and one-off pieces. Before AV Desk, requests for these videos arrived through Slack threads, direct messages and hallway conversations. Five problems kept repeating:

| Problem | What it cost |
|---|---|
| The request was vague ("can you make a video?") | The AV manager had to interview the requester before any work started |
| The deadline appeared too late | No realistic time for script, edit and review |
| The tone was wrong, and nobody noticed until delivery | Whole videos redone |
| Nobody could see where a request stood | Constant "when is my video coming?" messages |
| Nobody gave structured feedback afterwards | The team never learned which requests went well |

Every feature in AV Desk is the answer to one of these five rows. Keep the table in mind: when a design choice later seems arbitrary, it almost always traces back to one of them.

## 2. What the app does: one request's life

Follow one invented request from start to end. Ana, from the Conferências diretoria, needs a teaser for the BRASA Summit Europa.

1. **She opens the app.** The landing page asks what she needs. Regular editorial posts (feed, stories, calendar reels) are sent back to the existing ClickUp briefing flow, because AV Desk must not replace it. A video goes forward.
2. **She fills in the briefing.** She picks the type *Teaser*. The form shows the questions every video needs (objective, message, audience, tone, formats, approvers…) plus the teaser-specific ones (what does it announce?). Some questions only appear when an earlier answer makes them relevant: ticking Instagram asks which BRASA account publishes the post and which accounts join as collaborators; choosing the tone "Outro" asks her to describe it. As she types, a bar shows how complete the briefing is. When she picks a deadline, the form tells her whether it gives enough notice. Too little notice does not block her; it marks the request as **rush** and asks her to explain why the date cannot move.
3. **She submits.** The app checks everything again on the server, saves the request with a readable code (`AV-2026-0001`) and sends her to a private tracking page whose address contains a long random string. That address is her only key: no account, no password.
4. **The AV manager triages.** In the admin inbox, the manager (Lorenzo) sees the request with its deadline, rush flag and completeness score. He can ask for more information (Ana gets a form to complete and resubmit), decline it, or accept it and choose who produces it.
5. **Accepting creates a ClickUp task**, if ClickUp is configured, so the work appears in the team's tracker without retyping.
6. **Production and review.** The request moves to *in production*. When a cut is ready, the manager sends it *to review* with its **Frame.io** link (Frame.io is the video review tool the team uses: reviewers comment on the exact frame). Ana's tracking page then shows a "Sua vez de revisar" card with a button to that review. The manager can ask for changes (back to production) or mark it *delivered*, which requires the Google Drive link of the final file.
7. **Delivery creates feedback links**: one for Ana and one for each extra reviewer she named in the briefing. The manager copies them or sends them by e-mail with a prepared link.
8. **Feedback.** Each person rates four things from 1 to 5 and says whether the video is approved, approved with small tweaks, or needs major changes. Ana's answer decides what happens: approved means the request is **closed**; major changes sends it back to **production**. Other reviewers' answers are recorded but never move the request.
9. **Metrics.** The manager's metrics page combines everything: how many requests are rush, how long production takes, how often deadlines are met, average ratings by type and diretoria, and whether fuller briefings lead to better outcomes.

Steps 1–6 are about *asking for and producing* a video. Steps 7–9 are about *learning from the result*. That split is the most important structural fact in the project; section 5 builds on it.

## 3. The rules the assignment imposes

The course assignment (full text in [ASSIGNMENT_BRIEF.md](ASSIGNMENT_BRIEF.md)) fixes several things before any design choice is made. Two words first:

- A **process** is one running program. A **container** is a sealed package containing a program and everything it needs (Python, libraries, files), so it runs the same on any machine. Docker builds containers from a recipe called a **Dockerfile**; the built package is an **image**; a **volume** is a folder that lives outside the container so data survives when the container is deleted.
- A **database** stores information so it survives restarts. **SQLite** is a database that is a single file, with no separate server.

The hard rules, and what each one forced in AV Desk:

| Rule (brief section) | Consequence in the code |
|---|---|
| One process, one container, SQLite only (§1a) | No separate database server; one `avdesk.sqlite3` file |
| Use the provided Dockerfile, fill only 4 TODO lines (§1a) | `Dockerfile` at the root is the template; only the source-copy line was written |
| Bind `0.0.0.0` and read the port from `PORT` (§7.2–7.3) | `app.py` reads `PORT`, binds all interfaces |
| Configuration only through environment variables, no `.env` required (§7.9) | `config.py`, every setting has a default |
| Create the schema on first boot; seed from a text file without duplicating rows; never drop tables (§7.4, §7.11) | `db.py` and `seed.json`; startup is idempotent, and existing databases are upgraded in place |
| No background workers or message brokers (§1c) | ClickUp is called during the click, with a short timeout |
| Two backend domains that could be split into separate services later (§3) | `requests_domain` and `feedback_domain`, connected only through `services/` |
| ≥70% test coverage of core logic (§4) | 208 tests, 97% coverage |
| `ADR.md`, `AI_USAGE.md`, meaningful commits over several days (§5) | Decision log, AI log, small commits with "what and why" messages |

And one course rule that shapes everything else: the code must visibly apply what was taught in class, namely SOLID and code smells, nine design patterns, and the testing fundamentals. Each pattern had to *earn its place*: be the answer to a real problem in this app, with its trade-off stated.

## 4. The stack: which tools, and why

A few words before the list. A **web app** works by exchanging messages over **HTTP**: the browser sends a **request** (for example "GET /pedido/novo", meaning "give me the page at that address", or "POST /pedido/novo" with form data, meaning "here is something to save") and the server sends back a **response**: a status code (200 = fine, 302 = go elsewhere, 404 = not found, 422 = your input has problems) and usually an HTML page. A **route** is the mapping from an address to the Python function that answers it.

| Tool | What it is | Why it was chosen | What was rejected |
|---|---|---|---|
| **Python 3.12** | The programming language | The language the course and the author are comfortable in, which matters because the code must be explained on paper | Anything unfamiliar |
| **Flask** | A small library that maps routes to Python functions | Exactly what an app made of HTML forms needs, nothing more | Django: brings an admin site, an ORM and a project structure this app doesn't need (the brief grades that down). FastAPI: its strengths (async, automatic JSON APIs) don't help an app that renders forms |
| **Jinja** | Flask's template language: HTML files with blanks filled from Python | Pages are generated on the server, so the browser needs almost no JavaScript | A JavaScript front-end framework: a second app to build and explain |
| **waitress** | A production web server that runs the Flask app | Flask's built-in server is for development only; waitress is pure Python and starts with one command | gunicorn: doesn't run on Windows, where the app is developed |
| **sqlite3** (standard library) | Python's built-in way to talk to SQLite | Required storage; hand-written SQL behind small classes is easy to explain | An **ORM** (a library that hides SQL behind objects, like SQLAlchemy): more to learn, and it would hide the boundary between rules and storage that the design wants to show |
| **pytest**, **pytest-cov**, **pytest-mock** | Test runner, coverage measurement, mocking helper | The course's testing toolset | unittest: more boilerplate |
| **Vanilla JavaScript** | Plain browser JavaScript, no framework | Only small enhancements are needed (show the right questions, live score) | Any framework |

That is five third-party packages in total ([requirements.txt](../requirements.txt)), each **pinned** to an exact version (`flask==3.1.3`), so the image built later is the same as the one built today. The brief's soft cap is about twelve.

No fonts, scripts or styles load from the internet: the container must work offline. That is why the BRASA display font (Hagrid) is not used; titles fall back to Lato and then the system font.

## 5. The shape of the code: layers and domains

### 5.1 Layers

A **layer** is a group of code with one kind of responsibility. AV Desk's application code lives in the `avdesk/` folder (a Python **package**: a folder of modules importable as `avdesk.something`), arranged in layers:

```
web/                 HTTP: reads forms, renders pages              (outermost)
services/            the only code that knows both business areas
requests_domain/     rules for asking for and producing a video
feedback_domain/     rules for feedback after delivery
clock.py tokens.py   wrappers around the outside world:
task_tracker.py db.py   time, randomness, ClickUp, SQLite
config.py            settings
composition.py       builds and connects everything at startup
```

The single most important rule: **business rules never touch HTTP or SQL directly.** The rule "is this request rush?" is plain Python that receives dates and returns an answer. Three benefits follow, and you will see them again and again:

1. **Testing is cheap.** A rule can be tested in microseconds with no website and no database.
2. **Change is local.** Replacing Flask or SQLite would not touch the rules.
3. **The split in Assignment 2 is already drawn.**

### 5.2 Domains

A **domain** is one area of the business with its own data and rules. Section 2 ended with a split, and the code follows it exactly:

- **`requests_domain`**: steps 1–6. Briefing, deadline rule, statuses, request storage.
- **`feedback_domain`**: steps 7–9. Feedback links, answers, their rules.

The strict rule between them: **neither domain imports the other.** If the feedback code could read the requests table directly, the two would be welded together and could never be separated. How they still cooperate is section 10.

## 6. Three ideas that hold everything together

Almost every file uses these three ideas, so they come before the files.

### 6.1 Contracts (abstract base classes)

An **abstract base class** (ABC) declares *which methods must exist* without saying how they work. For example:

```python
class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...
```

Any class that inherits from `Clock` must provide `now()`. Code that asks for "a `Clock`" works with any of them.

### 6.2 Dependency injection

A class does not create the things it needs; it **receives** them in its constructor (`__init__`). The briefing intake does not create a clock; it is handed one. This is **Dependency Inversion**, the D in **SOLID** (five class-design principles from the course): important code depends on contracts, not on concrete tools. The code smell it prevents is called **Couplers**: classes welded to specific other classes.

### 6.3 Adapters and the composition root

An **Adapter** (a design pattern) is a small class that wraps an outside tool so it fits our contract, like a travel plug adapter. `SystemClock` wraps Python's `datetime` to fit `Clock`.

If every class receives its parts, somebody must choose the real parts and plug them together. That happens in exactly one place, the **composition root**, [composition.py](../avdesk/composition.py). It is the only module that names concrete classes. Everything else names only contracts.

The practical payoff shows up in tests: they plug in a `FixedClock` that always says "9 October 2026, 12:00 UTC", so a test about deadlines gives the same answer every day it runs.

## 7. Startup: how the program assembles itself

Everything in this section happens in the first second after `python app.py`.

### 7.1 `app.py`: the single start command

[app.py](../app.py) configures logging, reads the settings, builds the app and hands it to **waitress**, which listens on `0.0.0.0` (every network interface; `localhost` would be unreachable from outside a container) at the configured port.

### 7.2 Settings: `Config`, a Singleton

An **environment variable** is a named value given to a program when it starts (`PORT=8000`). [config.py](../avdesk/config.py) reads all of them once into a frozen `Config` object (a **dataclass**: a class that mainly holds named fields; **frozen** means its fields cannot change after creation). Every setting has a default, so the app runs with none set.

Everyone must see the same settings, so `Config` is a **Singleton**, a pattern meaning "only one instance ever exists". `get_config()` creates it on first use and returns the same object afterwards.

The course slides warn that naïve Singletons break with threads. A **thread** is one of several lines of work running at the same time inside one process; waitress answers several browser requests at once on different threads. Two threads could both see "no instance yet" and create two. So creation is wrapped in a **lock**, which lets only one thread through at a time. Tests call `reset_config()` to throw the instance away, because otherwise a setting changed by one test would leak into the next.

Two settings deserve a note:

- If `ADMIN_PASSWORD` is not set, the app uses the insecure default `avdesk-dev` and **logs a warning**. Crashing would violate the "no interactive setup, start within seconds" rule; silently accepting a default would hide the risk.
- If `SECRET_KEY` (used to sign the login cookie, section 11.5) is not set, it is derived from the admin password. One variable is enough, at the cost that changing the password logs everyone out.

### 7.3 The adapters: time, tokens, ClickUp, database

Four things come from outside the program, and each sits behind a contract:

| Outside thing | Contract | Real adapter | Test replacement |
|---|---|---|---|
| The current time | `Clock` ([clock.py](../avdesk/clock.py)) | `SystemClock` (UTC) | `FixedClock` (advanceable) |
| Random link secrets | `TokenGenerator` ([tokens.py](../avdesk/tokens.py)) | `SecureTokenGenerator` (`secrets.token_urlsafe(32)`, ~43 characters) | `SequentialTokens` (`token-1`, `token-2`…) |
| ClickUp | `TaskTracker` ([task_tracker.py](../avdesk/task_tracker.py)) | `ClickUpTaskTracker`, or `DisabledTaskTracker` when not configured | a recording fake |
| SQLite | (used through repositories, section 8.5) | `Database` ([db.py](../avdesk/db.py)) | a real SQLite file in a temporary folder |

A **token** here is that long random string in a link. Because it cannot be guessed, possessing the link *is* the permission to see the request or answer the feedback. That is why requesters and reviewers need no accounts.

`Database.connect()` opens one **connection** (a live channel to the database file) per unit of work, turns on foreign-key checking (section 12), and wraps the work in a **transaction**: a group of changes that is saved all together (**commit**) or not at all (**rollback**) if anything fails. It is deliberately *not* a Singleton: one connection shared by waitress's threads would break.

### 7.4 Tables, upgrades and reference data, safely, on every boot

A **table** is like a spreadsheet: columns define the fields, each row is one record. **SQL** is the language for creating tables and reading or writing rows.

Startup does three things to the database, and each is safe to repeat.

**1. Create what is missing.** Each domain owns a `schema.sql` file describing its tables as they look *today*. `create_schema` runs those files, which use `CREATE TABLE IF NOT EXISTS`: missing tables are created, existing ones are untouched.

**2. Upgrade what is old.** `CREATE TABLE IF NOT EXISTS` never changes a table that already exists, so a database created last week would never receive a column added this week. That is what **migrations** are for: numbered, ordered changes to an existing database. `MIGRATIONS` in `db.py` is an append-only list of such changes (for example "add the column `review_url` to `requests`"). SQLite keeps a counter called `PRAGMA user_version` inside the file; startup runs only the steps after that number and then raises it. A brand-new database is created directly in today's shape, so it is stamped with the latest number and runs no step at all.

**3. Load reference data.** [seed.json](../seed.json) holds the reference data, and it is treated in two different ways, because of who points at it:

- **Request types and briefing questions** are configuration that the AV manager will keep refining (the question set is still a draft). They follow `seed.json` on every boot: each row is matched by its natural key (`code`, `key`) and updated, and questions that disappeared from the file are removed. Nothing stores a reference to a question row, so removing one is safe; types are never removed, because requests point at them.
- **Diretorias and analysts** are seeded once, into empty tables, and never rewritten: requests point at them by id, so renaming or deleting them from a file could break existing requests.

Booting twice therefore changes nothing. That property is called **idempotent**, and the brief's checker tests it by restarting the container and comparing row counts. The opposite mistakes, both explicitly warned against in the brief, would be inserting the seed on every boot (rows double) or dropping tables and recreating them (every user's data wiped on restart).

Two safety details: table names cannot be passed to SQL as parameters, so only names that exist in the schema are accepted from `seed.json`; and a synced row must list *every* column, because a missing one would silently keep a stale value.

### 7.5 The composition root wires everything

[composition.py](../avdesk/composition.py) then builds the rest:

1. `build_requests_domain` assembles the requests domain and returns its front door plus its event announcer.
2. `build_feedback_domain` does the same for feedback.
3. `build_task_tracker` picks ClickUp or the disabled tracker, depending on whether both ClickUp variables are set.
4. `build_services` connects the domains by attaching listeners (section 10) and creates the metrics service.
5. `create_app` creates the Flask app, stores the assembled services in `app.extensions["avdesk"]`, installs the security checks and registers the three groups of pages.

Tests call the same `build_*` functions with fakes plugged in, so they exercise the real wiring.

## 8. The requests domain in practice

Folder: [avdesk/requests_domain/](../avdesk/requests_domain/). We follow Ana's request through it.

### 8.1 The vocabulary: `models.py`

These are the nouns the domain talks about:

- **`Status`**: an **enum** (a fixed list of named values) of the nine statuses, each with a Portuguese label for the UI: `submitted` (Recebido), `needs_info`, `accepted`, `in_production`, `in_review`, `delivered`, `closed`, `declined`, `cancelled`.
- **`RequestType`**: code, label, minimum lead time in business days, and `detail_label`. When a type has a detail label (redes sociais: "Qual formato?"; outro: "Descreva o que você precisa"), the requester must answer it in free text.
- **`Question`**: one briefing question: key, the type it belongs to (`None` = asked for every type), section, label, kind (`text`, `textarea`, `url`, `date`, `choice`, `multichoice`, `yesno`), options, required or not, and an optional **trigger** (`depends_on`, `depends_value`). A question with a trigger is a follow-up: `is_shown(answers)` says it appears only when the answer to `depends_on` equals `depends_value` (for a single choice) or contains it (for a multi-select). The "Outro" tone description and the two Instagram account questions work this way.
- **`Catalog`**: all reference data together, with lookups like `questions_for("teaser")` (the 21 common questions plus the teaser's 3) and `questions_for("teaser", answers)`, which keeps only the questions currently shown.
- **`Request`** and **`RequestEvent`**: a stored request and one line of its timeline.

**Design choice: questions are data, not code.** They live in `seed.json`. Adding a question, a follow-up or a whole new request type means editing that file, never writing `if type == "teaser"` branches. That is the **Open/Closed Principle** (the O in SOLID): code open to new behavior without editing what already works. The smell it prevents is **Change Preventers**: one change forcing edits in many places.

### 8.2 Assembling the briefing: `briefing.py`

A `Briefing` holds a dozen fixed fields (name, e-mail, diretoria, type and detail, title, campanha, conference flag, deadline and its reason, rush reason) and a dictionary of `answers` keyed by question. It is frozen.

Building it through one constructor with that many parameters is the **Bloater** smell known as a telescoping constructor. So it uses the **Builder** pattern: `BriefingBuilder` collects pieces step by step, and each step returns the builder so calls can be chained:

```python
briefing = (BriefingBuilder()
            .requester("Ana", "ana@gobrasa.org", diretoria_id=4)
            .request_type("teaser")
            .deadline(date(2026, 12, 1), "Abertura das inscrições")
            .answer("tom", "Institucional")
            .build())
```

`build()` returns the finished briefing and resets the builder for the next one. The **Director**, `BriefingDirector`, holds presets: `director.teaser(needed_by=...)` produces a complete valid briefing, and any field can be overridden by name (`director.teaser(..., requester_email="x@gmail.com")`). The web layer uses the builder to turn a submitted form into a briefing (section 11.4); the tests use the director everywhere.

### 8.3 Checking the briefing: `intake.py` and `validators.py`

`BriefingIntake.check()` runs four steps, in an order where each step depends on the previous:

1. **Clean the answers.** `keep_answers` drops answers to questions she can no longer see: questions of other types (if Ana filled in teaser questions and then switched to "Outro", the teaser answers are not stored) and follow-ups whose trigger changed (if she picked an Instagram account and then unticked Instagram, the account is not stored).
2. **Assess the deadline** with the lead-time rule (8.4).
3. **Validate.** `BriefingValidator.validate()` returns a dictionary of field → message in Portuguese; empty means valid. It checks the `@gobrasa.org` e-mail, the diretoria, the type and its detail, the title, a future deadline with a reason, a rush reason when needed, text length caps, and then every question currently shown. A hidden follow-up is never required, even if it is marked required: the Instagram account is mandatory only when Instagram is ticked. Which questions are required comes from the data. How an answer is checked depends on its kind, through one lookup table, `ANSWER_CHECKS`: a `url` must start with `http://` or `https://`, a `date` must be a real date, a `choice` must be one of its options, and so on.
4. **Score.** `BriefingScorer` computes the percentage of shown questions answered, so hidden follow-ups neither lower nor raise it.

The result is a `CheckedBriefing`: the cleaned briefing, the errors, the deadline assessment and the score.

Validation and scoring are separate classes because they answer different questions: *may this be submitted?* versus *how much context does it carry?* That is the **Single Responsibility Principle** (the S): one reason to change per class. The smell it prevents is the Bloater. `BriefingIntake` itself only orchestrates the four steps, which lets both `submit` and `resubmit` share one path.

### 8.4 The deadline rule: `leadtime.py`

`business_days_between(start, end)` counts Monday-to-Friday days after `start` up to and including `end`. Holidays are deliberately ignored, which keeps the rule explainable to requesters.

A request is **rush** when it gives fewer business days than required. The answer is a `LeadTimeAssessment` with four values: days available, days required, earliest realistic date, and the team's internal work deadline.

Conference content is different, because the COO reviews it with non-negotiable rules. That difference uses the **Strategy** pattern: a family of interchangeable rules behind one method.

| Policy | Days required | Work deadline |
|---|---|---|
| `StandardLeadTime` | the type's minimum | the requester's date |
| `ConferenceLeadTime` | minimum + COO buffer (default 3) | the requester's date minus the buffer, so the cut reaches the COO in time |

`lead_time_policy_for` picks one; callers just call `assess()` and never branch. Both policies return the same kind of result, which is the **Liskov Substitution Principle** (the L): any version of a contract must work wherever the contract is expected. The smell it prevents is **Object-Orientation Abusers** (the slides' penguin that is a bird but crashes when asked to fly).

In practice, with today = Friday 9 October and a teaser needing 10 business days (the confirmed minimums are teaser 10, institucional 7, redes sociais 5, outro 10; COO buffer 3): a deadline of Friday 16 October gives 5 days, so it is rush and the earliest realistic date is Friday 23 October.

### 8.5 Saving: `repository.py`

A **repository** is a class whose only job is saving and loading one kind of thing. The contracts are split by need:

- `CatalogReader`: load the reference data.
- `RequestReader`: get one request, find many by filter, read a timeline.
- `RequestWriter`: add a request, replace its briefing, apply a status change, store the ClickUp link.

Splitting readers from writers is the **Interface Segregation Principle** (the I): don't make code depend on abilities it doesn't need. Code that only reads, like metrics, *cannot* write by accident. The smell it prevents is **Dispensables**: fat interfaces full of unused methods.

`SqliteRequestRepository` is the Adapter that fulfils both contracts. Four details matter in practice:

- **Parameterised SQL.** Values travel as `?` placeholders, never pasted into the SQL text, which blocks the attack called SQL injection.
- **Two kinds of columns.** Fields that rules, filters and metrics read (status, type, diretoria, deadline, rush, score, the review and delivery links…) are real columns. The type-dependent answers are stored together as JSON text in `answers_json`, because which answers exist varies by type.
- **The public code** `AV-2026-0001` is built from the row's id right after insertion, so codes are unique without a counter table.
- **The status guard.** `apply_transition` updates the status *and* writes the timeline row in one transaction, with `WHERE status = ?` set to the status the caller expected. If the manager double-clicks, or two tabs race, only the first update finds a matching row; the second changes nothing and raises `StaleTransition`. The page then says the request changed while you were looking.

### 8.6 Moving through statuses: `lifecycle.py`

This file combines three patterns, so take it in pieces.

**The table.** `ACTIONS` lists every possible move once:

| Action | Button (pt-BR) | Allowed from | Leads to | Extra requirement |
|---|---|---|---|---|
| `accept` | Aceitar | submitted | accepted | an analyst |
| `request_info` | Pedir mais informações | submitted | needs_info | a note to the requester |
| `resubmit` | (requester only) | needs_info | submitted | |
| `decline` | Recusar | submitted, needs_info | declined | a note |
| `start_production` | Iniciar produção | accepted | in_production | |
| `send_to_review` | Enviar para revisão | in_production | in_review | an http Frame.io review link |
| `request_changes` | Pedir ajustes | in_review | in_production | |
| `deliver` | Marcar como entregue | in_production, in_review | delivered | an http Drive link |
| `close` | Concluir | delivered | closed | |
| `reopen` | Reabrir para ajustes | delivered | in_production | |
| `cancel` | Cancelar | submitted, needs_info, accepted, in_production | cancelled | |

`TRANSITIONS`, the map of which status may move to which, is *derived* from this table. Rules and buttons therefore cannot disagree. Closed, declined and cancelled have no way out.

**Command.** Each status change is an object with `execute()` and `undo()`. `StatusChange` is the general version (it demands a note for `needs_info` and `declined`). `AcceptRequest` adds "an analyst is required" and records who and when; `SendToReview` adds "a review link is required" and records it; `DeliverRequest` adds "a valid link is required" and records the link and time. The subclasses keep the same contract (LSP). The **receiver**, the object that really applies the change, is the repository.

**Factory Method.** `StatusCommandFactory.create("accept", request, ...)` looks the action up in its **factory map** (a dictionary from name to action), checks that the request's current status is allowed, checks the actor (only the requester may `resubmit`, and the requester may do nothing else), and builds the right command class. The admin page only ever sends an action name.

**The invoker.** `Lifecycle` runs commands and keeps a per-request history for "undo last change". The history lives in memory, protected by a lock because of threads, and is lost on restart. That is acceptable: undo is for "I clicked the wrong button", and the permanent record is the timeline in the database.

**What cannot be undone, and why.** Moves into or out of **accepted, delivered or closed** are refused. They already caused work outside the domain: undoing a delivery would leave feedback links pointing at nothing; undoing *out of* accepted would announce "accepted" again and create a second ClickUp task. Undo itself writes a timeline row ("Mudança desfeita"), so nothing disappears silently.

### 8.7 Announcing changes: `events.py`

When a status changes, other parts of the system may care, but the requests domain may not know they exist. The **Observer** pattern solves exactly this: a **subject** keeps a list of **observers** and notifies each one when something happens, without knowing what they are.

The announcement, `StatusChanged`, carries the old status, the new status and a `RequestSnapshot`: a frozen *copy* of what outsiders may know (code, title, type label, diretoria, campanha, requester, reviewers, deadline, rush flag, delivery link, and a Markdown summary of the briefing). Outsiders get a copy, never access to the requests tables.

If one observer fails, `RequestEventSubject.notify` logs the error and still notifies the rest. The status change is already saved; a broken listener must not undo it or silence the others.

### 8.8 The front door: `facade.py`

Without a single entry point, every web page would juggle the intake, repository, factory, lifecycle and subject itself. The **Facade** pattern gives callers one simple object, `RequestsFacade`:

| Group | Methods |
|---|---|
| Intake | `catalog`, `assess_deadline`, `submit`, `resubmit` |
| Reading | `by_token`, `get`, `timeline`, `inbox`, `all_requests`, `workload`, `briefing_markdown`, `slack_message` |
| Lifecycle | `available_actions`, `can_undo`, `perform`, `undo_last`, `attach_task_url` |

The facade **coordinates but never decides**: every rule lives in the classes behind it. That keeps the slides' warning about facades growing into "god objects" from coming true. `perform` shows the pattern in miniature: load the request, ask the factory for a command, have the lifecycle run it, then `_announce`, which reloads the request, builds the snapshot and notifies the observers.

[summary.py](../avdesk/requests_domain/summary.py) renders a request as Markdown (used for the ClickUp task description and the admin's copy button) and as a one-line Slack message in the casual lowercase style the team uses.

## 9. The feedback domain in practice

Folder: [avdesk/feedback_domain/](../avdesk/feedback_domain/). It mirrors the requests domain on purpose, so it reads quickly.

- **Models** (`models.py`): `Outcome` (approved, minor tweaks, major changes), the four rating dimensions (tone and brand fit, quality, process and communication, usefulness), and **`DeliveredWork`**, this domain's own copy of the delivered request. A `FeedbackInvite` is one person's link, with expiry and a "used at" time. `ResponseReceived` is the event this domain announces.
- **Rules** (`rules.py`): `parse_answer` turns a submitted form into a valid answer or a dictionary of errors (each rating an integer from 1 to 5, one of the three outcomes, comment under 3000 characters). `invite_state` says whether a link is open, used, expired or not found. "Used" is checked *before* "expired", so someone who answered in time is told the truth instead of "expired".
- **Repository** (`repository.py`): the same reader/writer split. `record_response` marks the invite used and stores the answer in one transaction, guarded by `WHERE used_at IS NULL`, so a double submit cannot store two answers.
- **Events** (`events.py`): its own subject and observer contract, deliberately *not* shared with requests, so either domain can be moved out alone.
- **Facade** (`facade.py`): `create_invites` (one token per person, expiring after `FEEDBACK_TTL_DAYS`), `open_invite`, `submit` (validate, store, then announce), and read methods for the admin page and metrics.

## 10. The seam: how two domains cooperate without knowing each other

The **seam** is the boundary between the domains. Only the [services/](../avdesk/services/) folder may import both, and exactly three things cross:

1. **Delivery → feedback links.** `FeedbackInviteObserver` ([seam.py](../avdesk/services/seam.py)) listens to the requests subject. On "delivered", it translates the `RequestSnapshot` into feedback's own `DeliveredWork` and asks `FeedbackFacade.create_invites` for one link for the requester and one per reviewer named in the briefing's *avaliadores* question.
2. **Feedback → close or reopen.** `FeedbackOutcomeApplier` listens to the feedback subject. It ignores reviewers; for the requester, "major changes" runs the `reopen` action and anything else runs `close`. If the manager already moved the request by hand, it does nothing.
3. **Metrics read both.** [metrics.py](../avdesk/services/metrics.py) holds plain functions over lists (rush share, turnaround, on-time rate, response rate, rating averages per group, score by outcome); `MetricsService` collects rows from both facades and only reads.

The same Observer mechanism carries one more listener that is not a domain: `TaskTrackerObserver` ([task_observer.py](../avdesk/services/task_observer.py)) hears "accepted", builds a `TaskDraft` (`[AV-2026-0001] Teaser…`, the Markdown briefing, the deadline, high priority if rush), hands it to the tracker and stores the returned link on the request.

All listeners are attached in `build_services`, in the composition root. That is the moment the domains become connected.

**The trade-off** (ADR-2): this is the in-process Observer from class. The subject calls its listeners directly, in the same process, inside the manager's click. That is why ClickUp has a 5-second timeout, and why a failing listener is logged rather than allowed to break the click. It also cannot work across two services, which is why Assignment 2 replaces it with **Pub/Sub**: a broker (a separate system that carries messages) between publisher and subscribers.

The last file of `services/`, [admin_guard.py](../avdesk/services/admin_guard.py), holds `AdminOnly`, a **Proxy**: an object that stands in front of another, offers the same methods, and checks before forwarding. Admin pages never receive a facade directly, only `AdminOnly(facade)`, which checks the login on every call. The rule lives in one place, so a new admin page cannot forget it.

## 11. The web layer: what the browser actually talks to

Folder: [avdesk/web/](../avdesk/web/). The web code only parses input, calls a facade and renders a template.

### 11.1 Routes

Flask groups related routes into **blueprints**:

| Address | Method | What happens | Blueprint |
|---|---|---|---|
| `/` | GET | Landing page with the scope gate | public |
| `/healthz` | GET | `{"status": "ok"}` | public |
| `/pedido/novo` | GET | Empty briefing form | public |
| `/pedido/novo` | POST | Submit; 302 to the tracking page, or 422 with the form and messages | public |
| `/pedido/prazo?type_code=…&needed_by=…&for_conference=sim` | GET | Lead-time result as **JSON** (a text format for data), used by the form's live notice | public |
| `/pedido/<token>` | GET / POST | Tracking page; POST resubmits when information was requested | public |
| `/feedback/<token>` | GET / POST | Feedback form; used, expired or unknown links get a friendly page | feedback |
| `/admin/login`, `/admin/logout` | GET / POST | Shared-password login and logout | admin |
| `/admin` | GET | Inbox with filters and workload per person | admin |
| `/admin/pedidos/<id>` | GET | Request detail, actions, undo, feedback links, copy buttons | admin |
| `/admin/pedidos/<id>/acao` | POST | Perform an action | admin |
| `/admin/pedidos/<id>/desfazer` | POST | Undo the last change | admin |
| `/admin/metricas` | GET | Metrics dashboard | admin |

URLs are in Portuguese because they are part of what Portuguese-speaking users see.

### 11.2 Templates and styling

Templates live in `web/templates/`. `base.html` is the shared frame; `_macros.html` holds reusable pieces (one question field of any kind, a status badge, the hidden security field); `_briefing_fields.html` is the briefing form, shared by the new-request page and the resubmission on the tracking page, so both always show the same questions.

All text follows BRASA's language rules ("a BRASA", "estudante", "conferência"). Colours follow the Manual de ID Visual BRASA 2025: on light backgrounds text is only Cinza Escuro, on dark blue or green only Cinza Claro, and palette colours are never used as text.

### 11.3 Review on Frame.io, and the admin actions panel

The team reviews cuts on Frame.io. Embedding Frame.io inside AV Desk was the first idea, but Frame.io does not support being shown inside other sites: its staff call iframe embeds unsupported and liable to break, and users report that commenting inside an embed fails. So while a request is *in review*, the tracking page shows a "Sua vez de revisar" card whose button opens the review in a new tab, where commenting works.

On the admin detail page, actions that need input (accept, ask for information, decline, send to review, deliver, cancel, reopen, request changes) open their own small form when clicked, with wording specific to the action ("O que falta no briefing?" versus "Por que o pedido foi recusado?"). Actions that need nothing (start production, close) are one-click buttons.

### 11.4 From form to briefing

[forms.py](../avdesk/web/forms.py) does the translation in both directions. `briefing_from_form` uses the Builder: fixed fields by name, then every question by the name `q_<key>` (the prefix avoids clashes with fixed fields), multi-select answers as a tuple, yes/no as `"sim"`/`"nao"`. Follow-up fields carry their trigger as `data-depends-on`/`data-depends-value` attributes for the JavaScript. `question_sections` groups questions for display: common sections first, then one block per type, in the order set by `seed.json`.

### 11.5 Security

[security.py](../avdesk/web/security.py) handles four things:

- **CSRF protection.** CSRF (cross-site request forgery) is when another website makes your logged-in browser submit one of *our* forms. Every form carries a random token stored in your session; every POST must send it back, or the server answers 400.
- **The admin password** is compared with `hmac.compare_digest`, which takes the same time whether a guess is close or not, so response timing reveals nothing.
- **The login** is remembered in a **session cookie**: a small piece of data the browser stores and sends back, **signed** with the secret key so it cannot be forged. It is marked `HttpOnly` (scripts cannot read it) and `SameSite=Lax` (other sites cannot send it along with their requests).
- **After login**, the app only redirects to paths starting with `/admin`, so the login page cannot be used to bounce people to another site.

### 11.6 JavaScript, only as an enhancement

[briefing.js](../avdesk/web/static/js/briefing.js) shows only the sections of the chosen type, reveals the detail field when needed, reveals follow-up questions when their trigger is chosen (mirroring `Question.is_shown`), previews the completeness score and calls `/pedido/prazo` to explain the deadline rule live. That endpoint runs the *same Python policy* as the real submission, so the rule exists in one place only. [copy.js](../avdesk/web/static/js/copy.js) powers the copy buttons. Without JavaScript every section shows and the server still validates everything.

## 12. The data: every table and why it looks that way

A **foreign key** is a database rule saying "this column must point at an existing row in that table". With foreign keys enabled, SQLite refuses rows that point at nothing.

**Requests domain** ([schema.sql](../avdesk/requests_domain/schema.sql)):

| Table | Holds | Notes |
|---|---|---|
| `diretorias` | The 8 diretorias | Seeded |
| `analysts` | People who produce videos | Seeded with generic names, never real people |
| `request_types` | The 4 types and their lead times | Synced from `seed.json` on every boot (never deleted); lead times confirmed: teaser 10, institucional 7, redes sociais 5, outro 10 business days |
| `briefing_questions` | The 31 questions | Synced from `seed.json` on every boot; options stored as JSON; `depends_on`/`depends_value` hold a follow-up's trigger |
| `requests` | One row per request | Fixed columns for what rules and metrics read (including `review_url` and `delivery_url`); `answers_json` for the rest; `CHECK` constraints keep status, score and booleans in range |
| `request_events` | The timeline | Foreign key to `requests` |

**Feedback domain** ([schema.sql](../avdesk/feedback_domain/schema.sql)):

| Table | Holds | Notes |
|---|---|---|
| `feedback_invites` | One row per link | `request_id` with **no foreign key**, plus a snapshot of the delivered work |
| `feedback_responses` | One row per answer | Foreign key to its invite, `UNIQUE` so an invite has at most one answer |

Foreign keys exist *inside* each domain and never *across* (ADR-3). In Assignment 2 the feedback tables move to their own database, where a key into another database cannot exist. The cost: if a request is edited after delivery, the snapshot does not follow. That is acceptable, because the snapshot records what was delivered.

Dates and times are stored as ISO text (`2026-10-09T12:00:00+00:00`), in UTC. The database file also records its migration number in `PRAGMA user_version` (section 7.4).

## 13. Tests: how we know it works

Folder: [tests/](../tests/). The course slides describe a **testing pyramid**: many small fast tests at the bottom, fewer slower ones on top.

| Layer | Count | What it tests | How |
|---|---|---|---|
| Unit (`tests/unit/`) | 128 | One rule at a time | No database; `FixedClock`, `SequentialTokens`, `mocker` mocks |
| Integration (`tests/integration/`) | 59 | Repositories, seeding, migrations, facades, the seam wiring | A real SQLite file in a temporary folder |
| End-to-end (`tests/e2e/`) | 21 | Whole journeys over HTTP | Flask's **test client**, a fake browser inside Python |

The vocabulary from class, as used here:

- **Mock**: a stand-in that records how it was called, so a test can assert "the observer was called once with this snapshot".
- **Stub**: a stand-in that returns fixed answers ("pretend this request is delivered").
- **Fake**: a simple working replacement (`FixedClock`, the temporary database).
- **Fixture**: reusable setup that pytest hands to tests by parameter name (`clock`, `seeded_db`, `client`), defined in `tests/conftest.py`. Fixtures build on each other: `seeded_db` starts from `migrated_db`.
- **TDD** (test-driven development): write a failing test (red), make it pass (green), then clean up. The git history shows red/green commit pairs for configuration, lead time, the briefing, the lifecycle, the feedback rules, follow-up questions, database upgrades and the review link.
- **AAA**: every test is Arrange (set up), Act (do one thing), Assert (check).
- **FIRST**: Fast, Independent, Repeatable, Self-validating, Timely. The injected clock is what makes the date-based tests repeatable.

Coverage (the share of code lines executed by tests) is 97% across 208 tests. Unit tests make up 62% of the suite, below the slides' 70–80%. That is deliberate (ADR-4): the riskiest code (atomic transitions, idempotent seeding, the missing cross-domain foreign key) only proves anything against a real database.

```bash
.venv/bin/python -m pytest --cov=avdesk --cov-report=term-missing
```

## 14. Running it, configuring it, shipping it

The root [README](../README.md) has the exact commands and the table of every environment variable. In short:

- **Directly:** create a virtual environment (an isolated folder of Python packages), install `requirements.txt`, run `python app.py`.
- **In a container:** `docker build -t avdesk .` then `docker run -p 8000:8000 -v avdesk-data:/data avdesk`.
- **The Dockerfile** is the course template with only TODO 3 written: an explicit list (`app.py`, `seed.json`, `avdesk/`) instead of `COPY . .`, which would copy the `.git` history, the virtual environment and any `.env` secrets into the image. Dependencies are installed *before* the source is copied, so editing a source file doesn't reinstall every package (Docker reuses unchanged steps, called **layer caching**).
- **The contract checker**, `container/run.sh`, builds the image and verifies every container rule. Its passing output is pasted in the README.

## 15. Problems we ran into, and what we did about them

| Problem | Where it showed up | What we did |
|---|---|---|
| Concurrent clicks could apply the same status change twice | Two tabs, or a double-click on "Aceitar" | The `WHERE status = ?` guard in `apply_transition`; the loser gets a friendly "it changed while you were looking" |
| Undoing out of "accepted" would create a second ClickUp task | Thinking through Command + Observer together | Moves into or out of accepted, delivered and closed are not undoable |
| Waitress runs several threads | `Config` creation, `Lifecycle` history, DB connections | Lock in `get_config()` and in `Lifecycle`; one connection per unit of work, never a shared one |
| ClickUp is an external service, but the brief forbids required external dependencies and background workers | The "create a task on accept" request | Optional adapter (disabled without both env vars), synchronous call with a 5 s timeout, failures logged without blocking acceptance |
| The BRASA title font (Hagrid) is not available offline | Applying the visual identity manual | Lato and system fonts only; colour rules applied from the manual |
| A double-submitted feedback form could store two answers | Single-use links | `WHERE used_at IS NULL` guard plus a `UNIQUE` invite column |
| Seed keys didn't match column names (`options` vs `options_json`) | First seeding test | Renamed in `seed.json`; convention: seed keys always equal column names |
| A test expected a 50% score where 25% was correct | Scorer tests | The test was wrong ("outro" has four applicable questions, not two); the test was fixed, not the code |
| A requester-only check lived in a loose helper | Facade review | Moved into `StatusCommandFactory.create`, next to the action table it belongs to |
| A test reached into a private attribute | Facade tests | Removed; the behaviour was already covered at the repository level |
| 68 files against the brief's ~15–50 guidance | File count check | `task_tracker.py` moved beside the other adapters, the scorer merged into `intake.py`, two message templates merged |
| An input without a `type` attribute rendered narrow; an empty dashboard showed "—%" | Clicking through the running app | CSS selector covers every text-like input; the % sign only shows with a value |
| Windows line endings could break shell scripts in the container | Git on Windows | `.gitattributes` forces LF for `*.sh` and the Dockerfile |
| Docker Desktop doesn't start from a script | First `run.sh` attempt | Started by hand, then the check was run |
| `run.sh` fails on Windows Git Bash (`mktemp` template without `XXX`; `python3` is a Store placeholder) | Producing the §7 evidence | Two tiny wrappers placed first on `PATH`; the script itself was not modified (note in the README) |
| Unit tests below the slides' share | Coverage report | Kept, and justified in ADR-4 rather than padded with low-value mocks |
| Question changes never reached an existing database, because seeding only filled empty tables | Testing the app with a real local database | Request types and questions now sync from `seed.json` on every boot; diretorias and analysts stay seed-once |
| New columns (follow-up triggers, review link) could not reach an existing database, because `CREATE TABLE IF NOT EXISTS` never alters a table | Same test | Append-only `MIGRATIONS` tracked in `PRAGMA user_version`, checked on a copy of the real database before use |
| Some questions only make sense after a specific answer ("Outro" tone, Instagram accounts) | User testing | Follow-up questions as data (`depends_on`, `depends_value`); hidden ones are never required, scored or stored |
| Frame.io cannot be embedded, and comments fail inside an embed | Designing the review step | The review opens on Frame.io in a new tab, from a card on the tracking page |
| The admin page showed two identical "Mensagem para quem pediu" boxes | User testing | Each action that needs input opens its own form, with its own wording |
| A preview server started for testing ignored its `DATA_DIR` and opened the real local database | Checking the admin panel in the browser | Stopped before any click; the scratch server now sets its variables inside Python. The only effect was the planned upgrade, already tested on a copy |

## 16. Where Assignment 2 cuts

Cut between the two domain folders. The line runs through [services/seam.py](../avdesk/services/seam.py):

- `StatusChanged` (delivered) and `ResponseReceived` become messages on a Pub/Sub topic instead of direct observer calls.
- Facade calls become HTTP calls to each service.
- The feedback tables move to their own database unchanged; nothing in them points into the requests tables.
- The metrics service becomes a reader of both services' APIs.

## 17. Quick reference

### Patterns

| Pattern | Class(es) | One-line reason |
|---|---|---|
| Singleton | `Config` / `get_config()` | One consistent set of settings, created safely under threads |
| Factory Method | `StatusCommandFactory` | Turn an action name into the right command without `if` chains |
| Builder | `BriefingBuilder`, `BriefingDirector` | Many optional fields, built step by step; presets for tests |
| Adapter | `SystemClock`, `SecureTokenGenerator`, `ClickUpTaskTracker`, `Sqlite…Repository` | Outside tools fit our contracts and can be swapped in tests |
| Proxy | `AdminOnly` | One place enforces the admin login for every admin call |
| Facade | `RequestsFacade`, `FeedbackFacade` | One front door per domain |
| Observer | `RequestEventSubject`, `FeedbackEventSubject` + listeners in `services/` | Domains react to each other without importing each other |
| Strategy | `StandardLeadTime`, `ConferenceLeadTime` | Interchangeable deadline rules behind `assess()` |
| Command | `StatusChange`, `AcceptRequest`, `SendToReview`, `DeliverRequest`, `Lifecycle` | Status changes as objects with execute/undo and an audit trail |

### SOLID

| Principle | Smell prevented | Where to point |
|---|---|---|
| Single Responsibility | Bloaters | Validator, scorer, policy, repository, facade each do one job |
| Open/Closed | Change Preventers | Questions, follow-ups and types in `seed.json`, `ANSWER_CHECKS`, `ACTIONS`, `MIGRATIONS` |
| Liskov Substitution | OO Abusers | Command subclasses and both policies keep their contract; fakes honour real interfaces |
| Interface Segregation | Dispensables | Reader/writer splits |
| Dependency Inversion | Couplers | Contracts + constructor injection + one composition root |

### Further reading in this repo

- [ADR.md](../ADR.md): the formal decision records.
- [DESIGN_NOTES.md](DESIGN_NOTES.md): pattern-by-pattern problem, reason and trade-off.
- [AI_USAGE.md](../AI_USAGE.md): how AI was used, prompt by prompt.
- A README inside each code directory explains that directory in detail.
