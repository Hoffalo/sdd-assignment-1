# `requests_domain/`: asking for and producing a video

This domain owns everything from the moment someone asks for a video until it is delivered: the briefing, its validation and completeness score, the deadline rule, the status lifecycle, and request storage. It never imports `feedback_domain`, and nothing in it imports Flask.

## Files, in the order a request meets them

| File | Responsibility | Pattern / principle |
|---|---|---|
| `models.py` | Vocabulary: `Status`, `RequestType`, `Question`, `Catalog`, `Request`, `RequestEvent` | Value objects |
| `briefing.py` | The `Briefing` value object and how it is assembled | **Builder** + Director |
| `validators.py` | Field-by-field checks with pt-BR messages | SRP, OCP (`ANSWER_CHECKS` table) |
| `leadtime.py` | Calendar-day lead time and the rush rule | **Strategy** |
| `intake.py` | Clean → assess → validate → score, shared by submit and resubmit; also `BriefingScorer` | SRP |
| `repository.py` | Reader/writer contracts and the SQLite adapter | ISP, **Adapter**, DIP |
| `lifecycle.py` | The action table, status commands, the command factory, the undo history | **Command**, **Factory Method** |
| `events.py` | Status-change announcements and the snapshot outsiders receive | **Observer** |
| `summary.py` | Markdown briefing export and Slack one-liner | |
| `facade.py` | `RequestsFacade`, the domain's only public entry point | **Facade** |
| `schema.sql` | This domain's tables | |

## How the business rules map to code

### Request types and questions are data

The four types (teaser, institucional, redes sociais, outro) and the 31 briefing questions live in `seed.json`, loaded into `request_types` and `briefing_questions` and kept in sync with the file on every start. A question with `type_code: null` is asked for every type (21 of them); the other 10 belong to one type.

**Why:** the briefing is "the brief deconstructed", and it will change as the AV team learns what context it needs. Keeping it as data means a new question or type never requires new `if` branches (Open/Closed Principle). Types with a `detail_label` (redes sociais, outro) require a free-text description of what exactly is wanted.

### Follow-up questions

A question with `depends_on` and `depends_value` is a follow-up: `Question.is_shown(answers)` shows it only when the answer to `depends_on` equals `depends_value` (single choice) or contains it (multi-select). Today there are three: the description of an "Outro" tone, and, when Instagram is ticked, the publishing account (required) and collab accounts (optional, from the six BRASA handles).

`Catalog.questions_for(type_code, answers)` returns only the questions currently shown, and the validator, the scorer and the answer cleaning all use it. A hidden follow-up is therefore never required, never counted in the score, and its answer is dropped on submit. Only one level of dependency exists; a follow-up of a follow-up would need its trigger checked in order.

### Completeness is measured, not just required

`BriefingScorer` reports the percentage of applicable questions answered. Validation decides whether a briefing *may* be submitted; the score measures *how much context* it carries beyond the minimum. Both are stored so metrics can test whether fuller briefings lead to better outcomes, which addresses the "vague request" problem.

### Deadlines: calendar days, rush, and C-Level approval

`days_between` counts every calendar day after the start date, weekends included, because BRASA's AV team works weekends. Holidays are not modelled either. The minimum per type is stored as `min_lead_days`.

| Policy | Required notice | Internal work deadline |
|---|---|---|
| `StandardLeadTime(min_days)` | the type's minimum | the requester's date |
| `CLevelApprovalLeadTime(min_days, approval_buffer_days)` | minimum + approval buffer | requester's date minus the buffer |

The approval policy applies when the requester ticks "Precisa de aprovação C-Level" (`needs_c_level_approval`). Too little notice does **not** block a request. It flags it as rush, asks for a reason (the box only appears then, and `BriefingIntake.check` drops a reason sent with a normal deadline), and shows the earliest realistic date. The manager can still accept it, and the rush share appears in metrics. Minimum lead times, confirmed by the AV manager: teaser 10, institucional 7, redes sociais 5, outro 10 days; approval buffer 3 days.

### The lifecycle

`ACTIONS` in `lifecycle.py` is the single table of allowed moves. `TRANSITIONS` is derived from it, so rules and admin buttons cannot diverge. Each action names its command class:

- `StatusChange`: the general command; demands a note for `needs_info` and `declined`, because the requester must be told why.
- `AcceptRequest`: demands an analyst and records `analyst_id` and `accepted_at` (the start of turnaround).
- `SendToReview`: demands an http(s) review link (Frame.io) and records `review_url`, which the tracking page shows to the requester while the request is in review.
- `DeliverRequest`: demands an http(s) link to the final file and records `delivery_url` and `delivered_at`.

`StatusCommandFactory.create(action_name, request, actor, ...)` refuses unknown actions, actions not allowed from the current status, and actions performed by the wrong kind of actor. `resubmit` is requester-only; every other action is admin-only.

`Lifecycle` (the invoker) runs commands and remembers them per request for "undo last change". It refuses to undo any move into or out of **accepted, delivered or closed**, because those already caused effects outside this domain: a ClickUp task, feedback links, a closed feedback loop. The history is in memory, so it is lost on restart; the permanent record is `request_events`.

### Storage

- **Fixed columns versus `answers_json`.** Anything the rules, filters or metrics read is a real column. Type-dependent answers are JSON, because which answers exist depends on the type.
- **`public_code`** (`AV-2026-0001`) is derived from the row id at insert time: readable for humans, unique without a counter table.
- **`tracking_token`** is the requester's private key to the tracking page.
- **`apply_transition`** updates the status and writes the timeline row in one transaction, with `WHERE id = ? AND status = ?`. A concurrent second click finds no matching row and raises `StaleTransition` instead of applying the move twice. It only accepts the five fields a transition may set (`analyst_id`, `accepted_at`, `review_url`, `delivery_url`, `delivered_at`).

### Announcing changes

After every successful `perform` or `undo_last`, the facade reloads the request, builds a `RequestSnapshot` and notifies `RequestEventSubject`. Observers receive a frozen copy, never a live object or table access. If an observer raises, the subject logs it and continues: the change is already committed.

The snapshot includes `summary_markdown` so the ClickUp observer can describe the task without querying this domain.

## The facade's public surface

| Method | Used by |
|---|---|
| `catalog()`, `assess_deadline()` | Form rendering, live deadline check |
| `submit(briefing)` → `(CheckedBriefing, Request \| None)` | New-request form |
| `resubmit(token, briefing)` | Tracking page when information was requested |
| `by_token()`, `get()`, `timeline()` | Tracking page, admin detail |
| `inbox(filter)`, `workload()`, `all_requests()` | Admin inbox, metrics |
| `available_actions()`, `perform()`, `can_undo()`, `undo_last()` | Admin detail, outcome applier |
| `attach_task_url()` | ClickUp observer |
| `briefing_markdown()`, `slack_message()` | Admin copy buttons |

Errors are exceptions with business meaning: `RequestNotFound`, `TransitionNotAllowed`, `MissingInput(field, message)`, `NotUndoable`, `StaleTransition`. The web layer turns each into a page or a flash message.

## Problems met while building this domain

- **Race on status changes.** Two clicks could both apply "accept". Solved with the status guard in `apply_transition`.
- **Undo and side effects.** Undoing out of `accepted` would re-announce "accepted" and create a second ClickUp task. `accepted` is therefore in `IRREVERSIBLE` together with `delivered` and `closed`.
- **Answers from a previously chosen type** were being stored. `Briefing.keep_answers` now drops answers that do not apply to the final type.
- **A scorer test expected 50%** where 25% was right ("outro" has 3 common questions plus its own). The test was corrected; the code was right.
- **A requester-only check** first lived in a helper beside the facade. It moved into `StatusCommandFactory.create`, next to the action table it depends on.
- **The scorer** was originally its own ten-line module (`scoring.py`). It was merged into `intake.py`, its only user, to reduce file count.
- **Questions that only make sense after an answer** ("Outro" tone, Instagram accounts) came out of user testing. They became data (`depends_on`, `depends_value`) instead of special cases in code.
- **Question changes never reached a database already in use**, because seeding only filled empty tables. The catalog now syncs on every start, and new columns arrive through migrations (see `avdesk/README.md`).

## How to extend

- **New question or type:** edit `seed.json`, in the matching list. Each row must list every column of its table (use `null` for `depends_on`/`depends_value` when there is no trigger). The change reaches existing databases on the next start.
- **New follow-up question:** the same, with `depends_on` set to the trigger question's key and `depends_value` to the answer (or ticked option) that reveals it.
- **New column:** add it to `schema.sql` *and* append the matching `ALTER TABLE` to `MIGRATIONS` in `db.py`; never edit or reorder existing migrations.
- **New answer kind:** add it to the `kind` CHECK in `schema.sql`, add a checking function to `ANSWER_CHECKS`, and add its rendering to `web/templates/_macros.html`.
- **New action:** add one `Action` row; if it needs inputs, subclass `StatusChange` and override `check_inputs` and `fields`.
- **New deadline rule:** add a `LeadTimePolicy` subclass returning a `LeadTimeAssessment`, and choose it in `lead_time_policy_for`.
