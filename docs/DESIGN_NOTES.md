# Design notes

How the class material (SOLID and code smells, the nine design patterns, the testing fundamentals) shows up in AV Desk, and why each choice was made. ADR.md holds the five formal decisions; this file holds the rest of the reasoning.

The "In my own words" column is mine to write. Rows marked **TO FILL** still need it.

## 1. Layers

```
web/            Flask glue: parse a form, call a facade, render a template
services/       the only code that knows both domains (seam, metrics, admin proxy)
requests_domain/  feedback_domain/   rules and data, no Flask, no cross-imports
clock.py  tokens.py  task_tracker.py  db.py   adapters over the outside world
composition.py  the one place where concrete classes are chosen and observers attached
```

A rule never imports Flask or runs SQL. That is what lets about 75% of the tests run without a database or a web server.

## 2. Patterns: problem, why this pattern, trade-off

| Pattern | Where | Problem in this app | Why this pattern | Trade-off | In my own words |
|---|---|---|---|---|---|
| Singleton | `config.Config`, `get_config()` | Every part needs the same settings, read once from env vars. | One shared, consistent instance. | Global state and thread-safety (waitress is multi-threaded), so creation sits behind a lock and tests call `reset_config()`. The database connection is deliberately *not* a Singleton: one connection shared by threads would break. | **TO FILL** |
| Factory Method | `lifecycle.StatusCommandFactory` (`_factory_map`) | An admin form posts an action name ("accept", "deliver"); the right command class must be built without `if action == ...` chains. | Creation is decided in one place from a map, as in the slides' `factory_map`. A new action is one new `Action` row. | One more level of indirection to read through. | **TO FILL** |
| Builder | `briefing.BriefingBuilder`, `BriefingDirector` | A briefing has about 12 core fields plus a type-dependent set of answers, most optional: a telescoping-constructor Bloater. | Step-by-step assembly; the Director gives ready-made presets used throughout the tests. | Two extra classes; only worth it because of the field count. | **TO FILL** |
| Adapter | `SystemClock`, `SecureTokenGenerator`, `ClickUpTaskTracker`, `SqliteRequestRepository`, `SqliteFeedbackRepository` | Domain code should talk to our own contracts, not to `datetime`, `secrets`, `sqlite3` or ClickUp's REST API. | Each adapter translates an outside API into our interface, so tests swap in fakes and the outside thing can change. | Thin extra files. | **TO FILL** |
| Proxy | `services.admin_guard.AdminOnly` | Admin-only pages and actions; a per-route `if admin` check can be forgotten. | Protection proxy with the same methods as the facade it wraps; every call is checked before it is forwarded. | `__getattr__` forwarding is less explicit than spelled-out methods. | **TO FILL** |
| Facade | `RequestsFacade`, `FeedbackFacade` | Routes and services would otherwise need to know intake, lifecycle, repositories and events. | One entry point per domain makes the seam visible and maps directly to the service APIs of Assignment 2. | Risk of a god object; each facade only delegates, the rules live elsewhere. | **TO FILL** |
| Observer | `RequestEventSubject` → `FeedbackInviteObserver`, `TaskTrackerObserver`; `FeedbackEventSubject` → `FeedbackOutcomeApplier` | Delivering must create invites and accepting must create a ClickUp task, without the requests domain knowing either exists. | The subject announces a status change; listeners are attached in the composition root. | In-process and synchronous: a slow listener (ClickUp) slows the click, and it cannot cross services. One failing observer is logged and does not stop the others. Assignment 2 replaces it with Pub/Sub. | **TO FILL** |
| Strategy | `leadtime.LeadTimePolicy`: `StandardLeadTime`, `ConferenceLeadTime` | The deadline rule differs for conference content (COO review buffer and an earlier internal deadline). | Interchangeable policies behind `assess()`; callers never branch on the policy. | Two classes for a small rule today; justified because lead-time rules are expected to change per type. | **TO FILL** |
| Command | `lifecycle.StatusChange` (+ `AcceptRequest`, `SendToReview`, `DeliverRequest`), `Lifecycle` invoker | Status changes are the audited core action, and a wrong click should be reversible. | Each change is an object with `execute()`/`undo()`; the repository is the receiver and writes the timeline row in the same transaction. | Undo is refused into or out of accepted, delivered and closed, because those already triggered work outside the domain (ClickUp task, feedback invites). The undo history lives in memory and is lost on restart. | **TO FILL** |

Also present without being extra classes: the Repository idea (reader/writer ABCs) and Dependency Injection through constructors.

### Considered and not used

- **Caching proxy over metrics:** at a few hundred requests a year the dashboard query is instant, so caching would only add stale numbers.
- **A Strategy family for metrics calculators:** they are plain functions; wrapping each in a class would be a pattern for its own sake.
- **Singleton database connection:** unsafe with waitress's threads (see the Singleton row).

## 3. SOLID and the smells they prevent

| Principle | Smell | Where to point |
|---|---|---|
| SRP | Bloaters | `BriefingValidator`, `BriefingScorer`, `LeadTimePolicy`, repositories and facades each have one job; `BriefingIntake` only orchestrates them. |
| OCP | Change Preventers | Required questions and follow-ups come from `seed.json`, answer checks from the `ANSWER_CHECKS` table, actions from `ACTIONS`, schema changes from `MIGRATIONS`: a new type, question, follow-up, action or column needs no new `if`. |
| LSP | OO Abusers | `AcceptRequest` and `DeliverRequest` keep `StatusChange`'s contract; both policies return the same `LeadTimeAssessment`; test fakes honour the real interfaces. |
| ISP | Dispensables | `RequestReader` vs `RequestWriter`, `FeedbackReader` vs `FeedbackWriter`, `CatalogReader`. |
| DIP | Couplers | Domains depend on `Clock`, `TokenGenerator`, `TaskTracker` and repository ABCs; concrete classes are chosen only in `composition.py`. |

## 4. Product decisions made in chat (2026-10-10)

- Request types are teaser, institucional, redes sociais (plus free text for which format) and outro (plus free text). Campanha is a free-text field. Requesters never pick the analyst; the AV manager assigns at acceptance.
- Questions are "the briefing deconstructed": stored as seed data per type, so the form changes without code changes.
- Accepting a request creates a ClickUp task automatically. Allowed by §7.6 as a public API the use case needs, but never *required*: without `CLICKUP_API_TOKEN` and `CLICKUP_LIST_ID` the app uses `DisabledTaskTracker` and works offline. The call is synchronous with a 5-second timeout because §1c forbids background workers, and a ClickUp failure is logged without blocking the acceptance.
- The UI follows the Manual de ID Visual BRASA 2025: Lato only (Hagrid is not licensed for the repo and nothing loads from a CDN), text in Cinza Escuro on light backgrounds and Cinza Claro on dark blue/green, and palette colours never used as text.

## 5. Product decisions from testing (2026-10-18)

- Choosing the tone "Outro" asks for a description; ticking Instagram asks for the publishing account (required) and collab accounts (optional), from @gobrasa, @brasasummitamericas, @brasasummiteuropa, @brasasummitinnovation, @brasaemcasa and @redegobrasa. Built as follow-up questions in data (`depends_on`, `depends_value`), not as special cases in code.
- The planned publication date, "quem publica" and the Design-approval question were removed: the due date is the only date the team plans against.
- Reviews happen on Frame.io. "Enviar para revisão" requires the review link and the requester's tracking page shows it. Embedding Frame.io was considered and rejected: Frame.io does not support embeds and comments fail inside them.
- The admin page opens a separate form per action, replacing two identical message boxes.
- Because these changes had to reach a database already in use, request types and questions now sync from `seed.json` on every start, and new columns arrive through numbered migrations (`db.MIGRATIONS`, tracked in `PRAGMA user_version`).

## 6. Open items `[A CONFIRMAR]`

1. Real minimum lead time per type (`seed.json`, `request_types`). Placeholders: teaser 10, institucional 20, redes sociais 7, outro 10 business days.
2. COO review buffer (`COO_REVIEW_BUFFER_DAYS`, default 3).
3. The question set per type (`seed.json`, `briefing_questions`), drafted from the handoff.
4. Diretorias: 8 were given, the handoff mentioned 9.
5. Whether "Vídeo para redes sociais" means only videos *outside* the editorial calendar (the landing page currently says so and sends calendar posts to ClickUp).
6. ClickUp field mapping (priority, tags, assignee) once the real list exists.
