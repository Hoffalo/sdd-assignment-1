# `web/`: what the browser talks to

Flask glue and nothing more. Every route does three things: parse HTTP input, call a facade, render a template (or redirect). No business rule lives here; if a route needs to *decide* something, the decision belongs in a domain.

## Stack

- **Flask 3**: maps URLs to Python functions, grouped into **blueprints** (`public`, `feedback`, `admin`).
- **Jinja**: HTML templates with placeholders, rendered on the server. Autoescaping is on, so user text cannot inject HTML.
- **Plain CSS and vanilla JavaScript**, served from `static/`. Nothing loads from a CDN, because the container must work offline.

## Files

| File | Role |
|---|---|
| `__init__.py` | `services()`: returns the `AppServices` the composition root stored in `app.extensions["avdesk"]` |
| `public.py` | Landing page, briefing form, live deadline check, tracking page, health check, app-wide 404 |
| `feedback.py` | The feedback form behind single-use links |
| `admin.py` | Login/logout, inbox, request detail, actions, undo, metrics; every facade reached through `AdminOnly` |
| `forms.py` | Form ⇄ domain translation: `briefing_from_form` (uses the Builder), `question_sections`, `parse_date`, `parse_int` |
| `security.py` | CSRF tokens, constant-time password check, admin session helpers |
| `templates/` | Jinja templates (below) |
| `static/css/avdesk.css` | All styling, built from the BRASA visual identity manual |
| `static/js/briefing.js` | Type-aware form, follow-up questions, live score, live deadline notice |
| `static/js/copy.js` | Copy-to-clipboard buttons |

## Routes

| Address | Method | Success | Failure |
|---|---|---|---|
| `/` | GET | Landing with scope gate | |
| `/healthz` | GET | `{"status": "ok"}` | |
| `/pedido/novo` | GET, POST | 302 to `/pedido/<token>` | 422, form redisplayed with messages |
| `/pedido/prazo` | GET | Lead-time JSON (`rush`, `available_days`, `required_days`, `earliest_date`, `work_deadline`) | `{}` when type or date is missing |
| `/pedido/<token>` | GET, POST | Tracking page; POST resubmits a briefing in `needs_info` | 404 unknown token; 422 invalid resubmission |
| `/feedback/<token>` | GET, POST | Form; thank-you page after a valid answer | 422 invalid answer; friendly page for used/expired (200) or unknown (404) |
| `/admin/login` | GET, POST | Session set, redirect to `/admin…` | 401 wrong password |
| `/admin/logout` | POST | Session cleared | |
| `/admin` | GET | Inbox; filters `status`, `type_code`, `diretoria_id`, `analyst_id` | 302 to login when logged out |
| `/admin/pedidos/<id>` | GET | Detail page | 404 unknown id |
| `/admin/pedidos/<id>/acao` | POST | Action performed, flash message | Flash with the missing input or "status changed meanwhile" |
| `/admin/pedidos/<id>/desfazer` | POST | Last change undone | Flash "nothing to undo" |
| `/admin/metricas` | GET | Dashboard | |

URLs are Portuguese because users see them. HTTP status codes follow their meaning: 422 for input the user must fix, 401 for a wrong password, 404 for unknown links, 400 for a forged POST.

## Business conventions in the web layer

- **The scope gate comes first.** The landing page sends regular editorial-calendar posts back to the Comunicação ClickUp flow. AV Desk must not replace that process.
- **Links are the authorisation.** Requesters and reviewers have no accounts; the token in the URL is the key. The admin page shows each link so the manager can share it.
- **The form follows the type and the answers.** `_briefing_fields.html` renders every section with `data-type` (empty for common sections), and every follow-up question with `data-depends-on`/`data-depends-value`. `briefing.js` hides the sections of other types, shows the type-detail field when the type has a `detail_label`, and shows a follow-up only when its trigger is chosen (mirroring `Question.is_shown`). The server never relies on this: it validates against the questions actually shown and drops every other answer.
- **The deadline rule exists once.** The live notice calls `/pedido/prazo`, which runs the same Python `LeadTimePolicy` as submission. JavaScript only displays the result.
- **The live score is a preview.** `briefing.js` counts answered visible questions; the stored score is computed by `BriefingScorer` on the server.
- **Answer field names** are `q_<question key>` (`ANSWER_PREFIX`), so they never clash with fixed fields like `title`. Multi-select answers arrive as repeated fields and become a tuple; yes/no answers are `sim`/`nao`.
- **Review on Frame.io, linked not embedded.** While a request is in review, `tracking.html` shows a "Sua vez de revisar" card whose button opens the Frame.io link in a new tab. Frame.io does not support being embedded in other sites, and commenting fails inside an embed, so a link is the reliable way for the requester to watch and comment.
- **One form per action.** On `admin_detail.html`, actions that need input (analyst, a message, a review or delivery link, an optional note) are collapsible `<details>` with their own fields and wording; actions that need nothing (start production, close) are single buttons. This replaced a layout where "Pedir mais informações" and "Recusar" each showed an identical "Mensagem para quem pediu" box.
- **Copy, not send.** The admin page offers "copy Slack message", copyable feedback links and a pre-filled `mailto:` link, because outbound e-mail and Slack were deliberately not built (no secrets, no background sending).
- **Language.** All visible text is Brazilian Portuguese and follows BRASA's language rules: "a BRASA" in capitals, "estudante" not "aluno", "conferência" for Summits, product names in full.

## Templates

| Template | Used for |
|---|---|
| `base.html` | Frame: header, nav (switches to admin links when logged in), flash messages |
| `_macros.html` | `question` (one field of any kind), `text_field`, `status_badge`, `error`, `csrf` |
| `_briefing_fields.html` | The briefing form; shared by the new-request page and resubmission, so both always match |
| `landing.html` | Scope gate |
| `briefing_form.html`, `tracking.html` | Requester pages; the tracking page also shows the Frame.io review card while in review |
| `feedback_form.html` | Reviewer page |
| `message.html` | Any single-message page: not found, link used/expired, thank you |
| `admin_login.html`, `admin_inbox.html`, `admin_detail.html`, `admin_metrics.html` | Manager pages |

Templates never call facades; routes pass everything they need.

## Styling (`static/css/avdesk.css`)

Colours are CSS variables named after the BRASA palette (`--azul-vivido`, `--noite-urbana`, `--luz-brasa`…). The manual's rules are applied literally:

- on light backgrounds, text is only Cinza Escuro (`--noite-urbana`);
- on dark blue or green, text is only Cinza Claro (`--luz-brasa`);
- palette colours are never used as text (links are dark text with a blue underline);
- buttons and section labels are uppercase.

Lato is the official typeface. Hagrid, the display face, is not licensed for this repository and cannot load from a CDN, so titles use Lato Bold with system fallbacks.

## Security (`security.py`)

| Threat | Defence |
|---|---|
| Another site makes a logged-in browser submit our forms (CSRF) | Random token in the session, hidden field in every form, checked on every POST; 400 otherwise |
| Guessing the admin password by timing responses | `hmac.compare_digest` takes the same time for any guess |
| Forged or stolen session | Cookie signed with `SECRET_KEY`, `HttpOnly`, `SameSite=Lax`; the session is cleared on login and logout |
| Login page used to bounce people to another site | After login, redirect only to paths starting with `/admin` |
| HTML or script injected through user text | Jinja autoescaping |
| SQL injection | Parameterised SQL in the repositories (not in this layer) |

## Problems met here

- **A text input without a `type` attribute** (the type-detail field) rendered narrow, because the CSS listed input types one by one. The selector now covers every input that isn't a checkbox or radio.
- **The empty dashboard showed "—%".** The percent sign is now appended only to real values.
- **Two message templates** (not found, feedback closed) were nearly identical. They became one `message.html`, and the admin blueprint reuses the public 404 handler instead of duplicating it.
- **Hard-coded URLs** (`/pedido/novo` in the landing page) were replaced by `url_for`, so routes can change in one place.
- **Two identical message boxes** on the admin page (request information, decline) confused testing; each action now opens its own form.
- **Embedding Frame.io** was the first idea for reviews; it is not supported by Frame.io, so the page links to the review instead.
