# `avdesk/`: the application package

Everything the running app needs lives in this package. `app.py` at the repository root only starts it.

## Layout

```
avdesk/
├── composition.py       composition root: builds and connects everything
├── config.py            settings from environment variables (Singleton)
├── clock.py             Clock contract + SystemClock adapter
├── tokens.py            TokenGenerator contract + SecureTokenGenerator adapter
├── task_tracker.py      TaskTracker contract + ClickUp and disabled adapters
├── db.py                SQLite connections, schema, migrations, reference data
├── requests_domain/     asking for and producing a video      → see its README
├── feedback_domain/     feedback after delivery                → see its README
├── services/            the only code that knows both domains  → see its README
└── web/                 Flask routes, templates, CSS, JS       → see its README
```

## The dependency rule

Arrows mean "may import":

```
web ──▶ services ──▶ requests_domain
  │          └──────▶ feedback_domain
  └──▶ (facades of both domains)

requests_domain ─╳─ feedback_domain        never import each other
both domains ──▶ clock, tokens, db          (contracts and shared infrastructure)
composition ──▶ everything                  the only module naming concrete classes
```

Two consequences matter for the business:

- **The domains are separable.** Requests (asking and producing) and feedback (learning from the result) can become separate services in Assignment 2 without rewriting either. The only crossings are in `services/seam.py`.
- **Rules are framework-free.** Nothing under `requests_domain/` or `feedback_domain/` imports Flask, and only their `repository.py` files contain SQL. The rules that decide whether a request is rush or a link has expired can be tested in microseconds.

## The top-level modules

### `config.py`: settings (Singleton)

`Config.from_env(env)` turns a mapping of environment variables into a frozen `Config`; every field has a default, because the container contract forbids required configuration. `get_config()` returns the single shared instance, created under a lock because waitress serves requests on several threads. `reset_config()` exists for tests, where global state would otherwise leak between cases.

`from_env` takes the mapping as an argument instead of reading `os.environ` itself, so tests pass a plain dictionary and need no environment tricks.

If `ADMIN_PASSWORD` is missing, the app uses `avdesk-dev` and logs a warning rather than crashing: the container must start without interactive setup, but the risk must be visible.

### `clock.py` and `tokens.py`: adapters over time and randomness

Business rules depend on "now" (deadlines, link expiry) and on random secrets (private links). Calling `datetime.now()` or `secrets` directly would make tests depend on the day they run. These files define the contracts (`Clock.now()`, `TokenGenerator.new_token()`) and the production adapters. Tests use `FixedClock` and `SequentialTokens` from `tests/doubles.py`.

All times are UTC. A link token is 32 random bytes encoded for URLs (~43 characters): holding the link *is* the authorisation, so it must be unguessable.

### `task_tracker.py`: where accepted work goes (ClickUp)

`TaskTracker.create_task(TaskDraft)` returns the created task's URL, or `None` when no tracker is configured.

- `ClickUpTaskTracker` posts to ClickUp's REST API using only the standard library (`urllib`), so it adds no dependency. Its `opener` parameter lets tests replace the network call.
- `DisabledTaskTracker` does nothing and logs it. The composition root uses it unless both `CLICKUP_API_TOKEN` and `CLICKUP_LIST_ID` are set.

Why it is built this way:

- The brief allows "a public API your use case genuinely needs" (§7.6) but forbids *requiring* one, so the app must work fully offline.
- It also forbids background workers (§1c), so the call happens during the manager's click, with a 5-second timeout so a slow ClickUp cannot freeze the page.

The field mapping (priority, tags, assignee) is a first draft marked `[A CONFIRMAR]` until the real ClickUp list exists.

It sits at the top level, next to `clock.py` and `tokens.py`, because it is the same kind of thing: an adapter over something outside the program. It originally lived in an `integrations/` package of its own; it was moved to reduce file count and to group adapters together.

### `db.py`: connections, schema, migrations, reference data

- `Database.connect()` gives one connection per unit of work: foreign keys on, rows readable by column name, commit on success, rollback on any error. It is deliberately not a Singleton, because sqlite3 connections must not be shared between waitress's threads.
- `create_schema()` runs each domain's `schema.sql` (always today's shape, `CREATE TABLE IF NOT EXISTS`), then brings an older database up to date with `MIGRATIONS`, an append-only list of changes such as "add column `review_url`". SQLite's `PRAGMA user_version` stores how many steps a database has had; only the missing ones run. A new database is stamped at the latest number, since `schema.sql` already has every column.
- `load_reference_data()` loads `seed.json` in two ways. Tables in `SYNCED_TABLES` (request types and briefing questions) follow the file on every boot, matched by natural key; questions missing from the file are removed, types never are. Every other table (diretorias, analysts) is filled only when empty, because requests point at those rows by id. Keys starting with `_` (like `_nota`) are comments and are skipped; list values become JSON text; unknown table names raise an error (table names cannot be SQL parameters, so they are checked against the real schema); a synced row must list every column, so a forgotten field can't silently keep a stale value.

Booting twice changes nothing (idempotent), which is what the brief's checker verifies by restarting the container and comparing row counts.

**Why it changed after the first version.** Seeding originally filled only empty tables, and the schema had no migrations. Testing against a real local database showed that edited questions and new columns never reached it. The upgrade was tested on a copy of that database before use: version 0 to 3, existing requests untouched.

### `composition.py`: the composition root

The only module that names concrete classes. In order:

1. `build_requests_domain(database, clock, tokens, coo_buffer_days)` assembles the requests domain.
2. `build_feedback_domain(database, clock, tokens, ttl_days)` assembles the feedback domain.
3. `build_task_tracker(config)` picks ClickUp or the disabled tracker.
4. `build_services(...)` attaches the observers that connect the domains (delivery → invites, acceptance → ClickUp task, feedback outcome → close/reopen) and creates the metrics service.
5. `create_app(config, clock=None, tokens=None, tracker=None)` creates the schema and seed, builds the Flask app, stores the services in `app.extensions["avdesk"]`, installs CSRF checks and registers the blueprints.

The optional parameters of `create_app` exist for tests: they inject a fixed clock, predictable tokens or a recording tracker while keeping the real wiring.

## Conventions in this package

- **Name the pattern where it lives.** The module or class docstring says which pattern a class implements and why, so it can be pointed at during the comprehension check.
- **Comment the why, never the what.** Code should read on its own; comments explain decisions (why a lock, why no foreign key, why a timeout).
- **Contracts are ABCs; implementations are adapters; choices happen only in `composition.py`.**
- **Code, comments and docs in English; user-facing text in Brazilian Portuguese.**
