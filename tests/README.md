# `tests/`: how we know it works

208 tests, 97% line coverage of `avdesk/`, about 15 seconds for the whole suite.

```bash
.venv/bin/python -m pytest --cov=avdesk --cov-report=term-missing
```

`pytest.ini` at the root points pytest at this folder.

## Stack

- **pytest**: finds functions named `test_*` and runs them; plain `assert` statements.
- **pytest-cov**: measures which lines the tests execute (coverage).
- **pytest-mock**: the `mocker` fixture, for mocks and stubs.
- **Flask's test client**: a fake browser inside Python, for end-to-end tests.

## The pyramid

| Folder | Tests | Share | Scope | Database |
|---|---|---|---|---|
| `unit/` | 128 | 62% | One rule or class in isolation | None |
| `integration/` | 59 | 28% | Repositories, seeding, migrations, facades, the real observer wiring | Real SQLite file in a temp folder |
| `e2e/` | 21 | 10% | Whole journeys over HTTP | Real SQLite, via the full app |

The class slides recommend 70–80% unit tests. We sit below on purpose (ADR-4): the riskiest code (atomic status transitions, idempotent seeding, single-use links, the missing cross-domain foreign key) only proves anything against a real database. Mocking SQLite to inflate the unit share would test the mocks, not the code.

## What each file covers

**Unit** (`unit/`)

| File | Covers |
|---|---|
| `test_config.py` | Defaults, env overrides, SQLite path, insecure-password fallback, ClickUp enablement, Singleton reset |
| `test_clock_and_tokens.py` | UTC clock, token length and uniqueness, `FixedClock` behaviour |
| `test_leadtime.py` | Business-day counting (including weekends), both lead-time policies, policy choice |
| `test_briefing.py` | Builder and Director, every validation rule, the completeness score, follow-up questions (shown, required, scored only when their trigger is chosen) |
| `test_lifecycle.py` | The full transition table, terminal states, factory rules, required inputs (analyst, note, review link, delivery link), undo rules, invoker history |
| `test_request_events.py` | Subject notifies all observers, detach works, a failing observer does not stop others |
| `test_feedback_rules.py` | Rating range, required fields, outcomes, comment length, the four link states at their boundaries |
| `test_services.py` | Seam observers, outcome rules, ClickUp observer and adapter (no network), the admin Proxy |
| `test_metrics.py` | Turnaround, medians, on-time rate, rush share, response rate, rating averages, score by outcome |

**Integration** (`integration/`)

| File | Covers |
|---|---|
| `test_database.py` | Schema on an empty dir, idempotent schema and seed, unknown seed table rejected, no FK from feedback into requests, FKs enforced, migrations on an old database (once, then harmless), catalog sync (edited and removed questions), seed-once tables untouched, incomplete synced rows rejected |
| `test_request_repository.py` | Round-trips, public code, timeline, status guard (`StaleTransition`), allowed transition fields (including the review link), filters |
| `test_requests_facade.py` | Submit valid/invalid, answer cleaning (other types and hidden follow-ups), rush, conference notice, perform + events, resubmit, undo, workload, Markdown export |
| `test_feedback_facade.py` | One token per recipient, snapshot stored, single use, invalid answers, expiry, events, response listing |
| `test_seam_wiring.py` | The composition root's real wiring: acceptance → ClickUp, delivery → invites, approval closes, major changes reopen, reviewers don't move status, metrics combine both |

**End-to-end** (`e2e/`)

| File | Covers |
|---|---|
| `test_smoke.py` | `/` answers 200 without login (the contract checker hits it); `/healthz` |
| `test_journeys.py` | Submit → tracking; invalid briefing (422); Instagram without a primary account (422); Frame.io link on the tracking page while in review; live deadline JSON; full happy path to closed; major changes reopen; single-use and expired links; bad rating; resubmission; admin redirects; wrong password; CSRF rejection; inbox and metrics; missing note; unknown token (404) |

## Shared helpers

- **`conftest.py`**: the fixtures. `clock` (`FixedClock`), `tokens` (`SequentialTokens`), `migrated_db` (schema in a temp folder, built with `yield`), `seeded_db` (built on `migrated_db` plus `seed.json`), `app` and `client` (the full app with injected clock and tokens, admin password `test-admin`).
- **`doubles.py`**: `FixedClock` (9 Oct 2026, 12:00 UTC; `advance(days=…)` moves it) and `SequentialTokens` (`token-1`, `token-2`…).
- **`factories.py`**: `make_catalog()`, a small hand-made catalog, so unit tests never depend on the contents of `seed.json`.

## Conventions

- **Arrange, Act, Assert**, separated by blank lines.
- **Names describe behaviour**: `test_rush_request_without_reason_is_rejected`, not `test_validator_3`.
- **One behaviour per test, ideally one assertion.** Tables of cases use `@pytest.mark.parametrize`. When a behaviour has several observable values, they are usually compared as one tuple; a few journey tests keep two asserts where splitting them would repeat a long setup.
- **Test behaviour through public interfaces.** No test reaches into private attributes; one that did was removed.
- **Mocks and stubs in unit tests, fakes in integration tests**, as in the class slides: `mocker.Mock()` to assert an observer was called or to stub a facade; a real temp database and `FixedClock` for integration.
- **No real time, randomness or network**, which keeps the suite FIRST: fast, independent, repeatable, self-validating, timely.
- **TDD.** Core rules (config, lead time, briefing, lifecycle, feedback rules) were written red then green, in separate commits; the failing-test commits are marked "(TDD red)" in their messages, and the implementation follows in the next commit.

## Problems met here

- **A wrong expectation** (50% score instead of 25%) was caught by its own red run; the test was fixed, the code was right.
- **A test reaching into `facade._commands`** was deleted; the repository test already covered the race it targeted.
- **The pyramid share**: see above and ADR-4.
