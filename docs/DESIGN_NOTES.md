# Design notes

How the class material (SOLID and code smells, the nine design patterns, the testing fundamentals) shows up in AV Desk, and why each choice was made. ADR.md holds the five formal decisions; this file holds the rest of the reasoning.

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

| Pattern | Where | Problem in this app | Why this pattern | Trade-off |
|---|---|---|---|---|
| Singleton | `config.Config`, `get_config()` | Every part needs the same settings, read once from env vars. | One shared, consistent instance. | Global state and thread-safety (waitress is multi-threaded), so creation sits behind a lock and tests call `reset_config()`. The database connection is deliberately *not* a Singleton: one connection shared by threads would break. |
| Factory Method | `lifecycle.StatusCommandFactory` (`_factory_map`) | An admin form posts an action name ("accept", "deliver"); the right command class must be built without `if action == ...` chains. | Creation is decided in one place from a map, as in the slides' `factory_map`. A new action is one new `Action` row. | One more level of indirection to read through. |
| Builder | `briefing.BriefingBuilder`, `BriefingDirector` | A briefing has about 12 core fields plus a type-dependent set of answers, most optional: a telescoping-constructor Bloater. | Step-by-step assembly; the Director gives ready-made presets used throughout the tests. | Two extra classes; only worth it because of the field count. |
| Adapter | `SystemClock`, `SecureTokenGenerator`, `ClickUpTaskTracker`, `SqliteRequestRepository`, `SqliteFeedbackRepository` | Domain code should talk to our own contracts, not to `datetime`, `secrets`, `sqlite3` or ClickUp's REST API. | Each adapter translates an outside API into our interface, so tests swap in fakes and the outside thing can change. | Thin extra files. |
| Proxy | `services.admin_guard.AdminOnly` | Admin-only pages and actions; a per-route `if admin` check can be forgotten. | Protection proxy with the same methods as the facade it wraps; every call is checked before it is forwarded. | `__getattr__` forwarding is less explicit than spelled-out methods. |
| Facade | `RequestsFacade`, `FeedbackFacade` | Routes and services would otherwise need to know intake, lifecycle, repositories and events. | One entry point per domain makes the seam visible and maps directly to the service APIs of Assignment 2. | Risk of a god object; each facade only delegates, the rules live elsewhere. |
| Observer | `RequestEventSubject` → `FeedbackInviteObserver`, `TaskTrackerObserver`; `FeedbackEventSubject` → `FeedbackOutcomeApplier` | Delivering must create invites and accepting must create a ClickUp task, without the requests domain knowing either exists. | The subject announces a status change; listeners are attached in the composition root. | In-process and synchronous: a slow listener (ClickUp) slows the click, and it cannot cross services. One failing observer is logged and does not stop the others. Assignment 2 replaces it with Pub/Sub. |
| Strategy | `leadtime.LeadTimePolicy`: `StandardLeadTime`, `ConferenceLeadTime` | The deadline rule differs for conference content (COO review buffer and an earlier internal deadline). | Interchangeable policies behind `assess()`; callers never branch on the policy. | Two classes for a small rule today; justified because lead-time rules are expected to change per type. |
| Command | `lifecycle.StatusChange` (+ `AcceptRequest`, `SendToReview`, `DeliverRequest`), `Lifecycle` invoker | Status changes are the audited core action, and a wrong click should be reversible. | Each change is an object with `execute()`/`undo()`; the repository is the receiver and writes the timeline row in the same transaction. | Undo is refused into or out of accepted, delivered and closed, because those already triggered work outside the domain (ClickUp task, feedback invites). The undo history lives in memory and is lost on restart. |

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

## 6. Confirmed by the AV manager (2026-10-18)

- Minimum lead times: teaser 10, institucional 7, redes sociais 5, outro 10 business days.
- COO review buffer for conference content: 3 business days.
- "Vídeo para redes sociais" means social videos **outside** the editorial calendar; calendar posts keep their ClickUp flow, as the landing page says.

## 7. Open items

1. The question set below is a draft built from the handoff and user testing; it still needs the AV team's validation.
2. Diretorias: 8 are seeded (Comunicação, Tech, Gente e Gestão, Conferências, Rede, Impacto Social, Administrativo, Relações Corporativas); the handoff mentioned 9, so one may be missing.
3. ClickUp field mapping (priority, tags, assignee) and real credentials, postponed.

## 8. The current question set

Every request asks for the fixed fields first: name, `@gobrasa.org` e-mail, diretoria, type (and, for redes sociais or outro, a free-text detail), title, campanha, whether it is conference content, due date and its reason, and a reason when the deadline is short. Then the questions below. "Follow-up" means the question appears only after the answer named.

**Every type**

| Section | Question | Kind | Required |
|---|---|---|---|
| Objetivo e mensagem | Depois de assistir, o que a pessoa deve sentir ou fazer? | long text | yes |
| | Qual é a mensagem principal do vídeo? | long text | yes |
| | Existe uma chamada para ação? | text | no |
| Público e tom | Para quem é o vídeo? (pré-universitários, universitários no exterior, bolsistas e alumni, parceiros e doadores) | multi-select | yes |
| | Qual é o tom do vídeo? (Inspirador, Didático, Institucional, Outro) | choice | yes |
| | Descreva o tom que você imagina (follow-up: tom = Outro) | long text | yes |
| | Mande pelo menos uma referência do tom que você imagina | long text | yes |
| Onde e como | Onde o vídeo será usado? (Portal BRASA, YouTube, Instagram, TikTok, LinkedIn, exibido em conferência, uso interno) | multi-select | yes |
| | Em qual conta do Instagram o vídeo será publicado? (follow-up: Instagram) | choice of 6 handles | yes |
| | Contas convidadas para collab (follow-up: Instagram) | multi-select of 6 handles | no |
| | Em quais formatos? (16:9, 9:16, 1:1) | multi-select | yes |
| | Duração estimada | text | no |
| Material existente | Já existe roteiro? Cole o link | link | no |
| | Link da pasta com imagens e vídeos que já existem | link | no |
| | Quem aparece em câmera? (nome completo — cargo, para as legendas) | long text | no |
| | Alguma preferência de música? | text | no |
| | Logos ou materiais de parceiros que precisam aparecer | long text | no |
| Aprovações e avaliação | Quem precisa aprovar o vídeo? | text | yes |
| | Uma agência externa está envolvida? | yes/no | no |
| | Além de você, quem deve avaliar a entrega? (one name per line; each gets a feedback link) | long text | no |
| | Algo mais que a gente precisa saber? | long text | no |

**Per type**

| Type | Question | Kind | Required |
|---|---|---|---|
| Teaser | O que o teaser anuncia? | text | yes |
| | Quando acontece a revelação ou o lançamento? | date | no |
| | O que pode e o que não pode ser revelado ainda? | long text | no |
| Institucional | Que história ou jornada o vídeo deve contar? | long text | yes |
| | Precisa de animação ou motion graphics? | yes/no | no |
| | Quem faz a locução? | text | no |
| Redes sociais | Qual é o gancho dos primeiros segundos? | text | no |
| | Faz parte de uma série? | yes/no | no |
| | Rascunho da legenda do post | long text | no |
| Outro | Por que esse pedido não se encaixa nos outros tipos? | long text | yes |
