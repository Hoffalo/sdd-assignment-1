## Individual Assignment 1
**Topic:** Build a Simple Application to Serve as the Basis for DevOps Work

**Deadline:** 2026-10-12 23:59

**Written Comprehension Check:** in class, at/after the deadline session (date announced separately)

### Assignment Philosophy
AI use is allowed and expected. That changes what counts as evidence of effort: a working app no longer proves you made real design decisions, since AI makes "working" cheap. Grading weights the things AI can't do for you: the decisions you made along the way, and your ability to explain your own code cold, on paper, with no notes.

Keep it real, not academic. Build something you could plausibly ship to a real user. You can invent stakeholders, users, or scale requirements to justify design choices (e.g., "10,000 daily users, so..."). Stakeholders are people or organizations, not tools like Git, Azure, or Blackboard.

### Objective
Design and build a **minimal, monolithic application** that is **fully self-contained and runs locally in a single Docker container**. Everything it needs lives inside that one container: no cloud account, no external database, no second service.

**Assignment 1 ends at "it runs locally in a container."** Assignment 2 is where you break this app into separate services and deploy them to Azure. That's why §3 asks you to design two feature domains that are *logically* separable now: you're drawing the seam in Assignment 1 and cutting along it in Assignment 2.

You do not design any Docker or cloud tooling here. A **Dockerfile template** and a **contract checker** (`run.sh`) are provided to everyone in `container/`. You copy the template to your repo root and fill in the four `TODO` lines it marks, nothing else. Your real job is §7: making your *application* behave so that template runs it.

### 1. Scope & Architecture Constraints
This assignment caps *how many processes/containers it runs in*, not what technology you use. Some constraints below are hard requirements, needed so the shared Dockerfile template and checker work on everyone's app. Everything else is your choice, as long as you can justify it.

**1a. Hard requirements (container homogeneity, not a complexity judgment):**
- Single process, single container. No microservices, multiple repos, or separately deployed services. Splitting comes in Assignment 2.
- **Storage: SQLite**, as a file inside the container at one documented path. Mandatory: every app needs the same storage shape for the provided tooling and for Assignment 2.
- One dependency manifest at the repo root (`requirements.txt`, `package.json` + lockfile, etc). No per-folder manifests.
- **Do not author your own Dockerfile from scratch**, and no `docker-compose.yml` or CI workflow (`.github/workflows/`) at all. Use the provided template in `container/`: fill its four `TODO` lines, leave the rest. Designing images and pipelines yourself is Assignment 2 content.
- No Terraform/Bicep/ARM or other IaC you author.
- **No cloud deployment of any kind** (Azure, AWS, Render, Heroku, custom domain). Assignment 1 is local only: `docker build`, `docker run`, done. Cloud is Assignment 2.
- No external managed database, cache, or second container. Everything lives inside your one container.

**1b. Free choices, justify each in `ADR.md`:**
- **Backend language/framework**: explain why you chose it and what it buys you. Example: using Django when nothing needs it over Flask/FastAPI is graded down as poor judgment, not banned.
- Whether to add authentication/login.
- Any pattern beyond the basics (GraphQL, WebSockets, in-process background task, heavier ORM), as long as it fits the single-process constraint.
- Frontend approach: plain HTML/CSS/JS, templates, or heavier, served by the same process.
- Dependency count: soft cap ~12 third-party packages.
- File count: rough guidance ~15-50 files (excluding lockfiles/venvs/node_modules).

**1c. Out of scope, regardless of justification:** message brokers (Redis/RabbitMQ), background job runners (Celery, cron containers), or an actual multi-service split. These all assume more than one process, which §7's single-container contract doesn't support. If your use case wants them, treat that as a signal, not a blocker: design your two feature domains (§3) to be *logically* separable now (that's the second required `ADR.md` entry, §5), and leave the physical split and anything it needs to Assignment 2.

**1d. Use a stack you're already comfortable in.** For most students that's Python. Anything works if you can write and explain the code yourself, cold, at the comprehension check (§6). Picking an unfamiliar language because AI can generate it too is the fastest way to fail that check.

New ideas for the app can be proposed to the professor, but still need to comply with this section.

### 2. Application Scope
Propose your own use case and get it pre-approved before you start building. It needs enough substance for two genuinely distinct backend feature domains (§3) plus SQLite persistence; a single-entity CRUD toy ("add and remove a task, nothing else") is probably too thin. Most ideas need a second feature domain with real purpose: tasks + tags, posts + comments, links + click analytics, weather dashboard + saved locations/alerts. Bring your specific plan to the professor before writing code.

### 3. Required Features
- **SQLite persistence** (required): underlies both domains. Neither domain counts as "working" unless it reads/writes through SQLite.
- **At least 2 distinct backend feature domains** (required): each with its own responsibility and data, coupled as little as possible. Each one should be something you could lift out into its own service in Assignment 2 without rewriting it. You're not building that split now (§1c), but you must be able to point at where the seam goes and name what crosses it.
- A third domain, or extra polish on the two above, is optional and worth a small amount folded into Code Quality. Don't spend hours here instead of on §4/§5.

### 4. Testing
Automated unit tests (pytest/unittest, Jest/Mocha, or your language's equivalent) covering the **core business logic** of your two domains, not framework glue or routing, at **≥70% coverage**, measured with a standard tool (pytest-cov, coverage.py, nyc, jest --coverage). Report the coverage command and result in your README.

### 5. Process Deliverables
The core of the assignment: artifacts that make your design thinking visible over time, not just a snapshot at the deadline.

**`ADR.md`**, a lightweight Architecture Decision Record log at the repo root. Exactly 5 entries, this format:
```
## [N]. <Title>
Date: YYYY-MM-DD
Status: Decided
Context: 1-3 sentences, what forced this decision
Decision: 1-2 sentences, what you chose
Alternatives considered: at least one real alternative, and why you rejected it
Consequences: 1-2 sentences, what this costs or enables later
```
One entry required for each:
1. **Backend language/framework choice**: the justification from §1b (what it buys you, what you rejected).
2. **How you scoped your two feature domains to be independently modularizable**.
3. **A data-model/schema decision in SQLite**: e.g. how the two domains' data relates. Should visually match the database diagram in §8.
4. **Your testing approach**: what you prioritized toward the 70% bar, what you left thinner, and why.
5. **One thing you deliberately chose not to build**, and why.

Add entries as you make the decisions, not all at once. Your 5 entries must span at least **3 distinct commit dates**; landing them all in one commit defeats the point of the log.

**`AI_USAGE.md`**, a structured AI usage log. One row per meaningful interaction:

| Date/commit | Tool | Prompt | Disposition (Accepted/Modified/Rejected) | What changed & why (if modified) | In my own words, how this works |
|---|---|---|---|---|---|

The last column matters most: explain, using your own function/variable names, how the accepted code actually works. Vague explanations are exactly what §6 is designed to catch. Disclosure is grade-neutral: you're graded on accuracy and specificity, never on the fact that you used AI.

**Commit history**: at least **12 commits** across at least **6 distinct calendar days**, no single day over 40% of total commits. Push to a remote (GitHub); we check push timestamps, not local dates. "Initial commit", "WIP", "update", "fix" don't count as meaningful messages; describe what changed and why. Fabricated or backdated history is an academic integrity violation.

### 6. Written Comprehension Check (a multiplier, not a normal rubric line)
In class, at or after the deadline, you'll answer 6 short-answer questions about your own project: on paper, closed-book, no notes/device/AI. Answers are graded against your actual repo, report, ADR log, and AI usage log.

**How it affects your grade:** §3-§5 and §7-§9 are scored normally and summed to a subtotal out of 100. The check is scored separately, out of 100, and **multiplies** the subtotal (it isn't added). Example: subtotal 88/100, check 60% gives a final grade of 88 × 0.60 = **52.8/100**. A great subtotal can't buy out of a bad check, and a great check can't inflate a thin submission.

Easy to ace if you know your project. If your ADR log, AI usage log, and commits reflect real work and understanding, this should be straightforward. You're graded on accuracy and specificity, not handwriting or prose.

### 7. Local Container Contract
The provided `container/Dockerfile` template defines an output contract: whatever you fill into its TODOs, the image it produces has to behave in a fixed way. That contract is what we run and what we grade. It is also what makes Assignment 2's split and Azure deployment possible later, so it's worth getting right now.

Your app must:
1. Run as a single process, started by one documented command (`python app.py`, `npm start`).
2. Bind to `0.0.0.0`, not `localhost`/`127.0.0.1`. Binding to localhost makes the app unreachable from outside the container, which is the single most common failure here.
3. Read its port from one environment variable (e.g. `PORT`), with a sane default.
4. Need no interactive setup at startup (no `input()`, wizard, manual migration step). Run cleanly after clone + install + start, and create its own schema on first boot against an **empty** data directory.
5. Write its SQLite file to one documented path, under a configurable directory (e.g. `DATA_DIR`), so the container can mount a volume there.
6. Have no required external runtime dependency beyond a public API your use case genuinely needs. No external managed DB/cache/queue, no second container.
7. Expose exactly one dependency manifest at the repo root.
8. Not depend on a Dockerfile, `docker-compose.yml`, or CI workflow *of your own* to run. Your app must start the same way inside the provided container and on your laptop.
9. Be configurable entirely via environment variables. No editing source to reconfigure, no hard dependency on a `.env` file existing.
10. Start and be ready within a few seconds, no manual warm-up.
11. **Ship seed data as code, not as a database file.** If your app needs reference data to be useful (a country list, a product catalogue, starter categories, a demo account), commit it as a readable text file (`seed.sql`, `seed.json`, `seed.csv`) and load it on first boot when the target table is empty. Do not commit a prebuilt `.db`/`.sqlite` file.

**Why this rule exists.** The tempting shortcut is to build your database locally, commit `app.db`, and copy it into the image. That appears to work, which is exactly the problem. Docker copies an image's files into a named volume *only when that volume is empty*, so a baked-in `.db` shows up on a completely fresh volume and never again:

| Situation | What happens to your baked-in `.db` |
|---|---|
| First run, brand new empty volume | Copied in. Looks like it works. |
| Every later run, once your app has written anything | Ignored. Rebuild the image with corrected seed data and nobody ever sees it. |
| Bind mount (`-v ./data:/data`) | Never visible at all. The mount hides it completely. |
| Assignment 2, mounted Azure file share | Same as a bind mount. Your app starts with an empty database. |

So the failure is silent and arrives later, which is the worst kind. Three more reasons on top: a binary `.db` in Git gives unreadable diffs and unmergeable conflicts, it hides the schema decisions ADR-3 asks you to defend, and seeding from a text file is the same "database creation and migration" problem Assignment 2 grades directly. Do it now and Assignment 2 gets easier.

Make the load **idempotent**: booting twice must not change your data. Guard on the target table being empty, or use `INSERT OR IGNORE` against a unique key. The checker starts your app twice on the same volume and compares row counts, so an unguarded seed shows up immediately as doubled rows.

The other way to get this wrong is to `DROP TABLE` and rebuild on every boot. Row counts stay constant, so the checker will not catch it, but it throws away everything your users entered every time the container restarts. We look for it when reading your code, and it is a fair target for a comprehension-check question. Your startup path should create what is missing and touch nothing that already exists.

**Verification:** before you submit, run the provided checker against your repo:

```
./container/run.sh /path/to/your/repo
```

It builds your image, starts it, and tests each point above, including the two that silently pass on a laptop and fail in a container: binding `0.0.0.0` rather than `127.0.0.1`, and actually reading `$PORT` instead of hardcoding 8000. Paste its output into your README as your §7 evidence. If you can't produce a passing run, your app doesn't meet §7 and Working Features is graded down.

### 8. Documentation
A short report (4-5 pages):
- SDLC model chosen and justification (SMART goals; how you did or didn't follow it in practice)
- **Architecture overview diagram**, must match what you actually built. Mark where the seam between your two feature domains (§3) falls, i.e. where you'd cut if you had to split them into separate services.
- **Database model/schema diagram** (tables, columns, relationships), must match ADR-3 and your actual schema
- README with setup instructions clear enough for someone else to run the project, covering both ways to run it: directly on a machine, and with `docker build` + `docker run`. Include every environment variable you read with its default, the SQLite path, the coverage command from §4, and the passing `run.sh` output from §7.
- The AI-disclosure statement required by the course syllabus: "I acknowledge the use of [AI system] to [how you used it]. The prompts used include [...]. The output of these prompts was used to [...]." This is a report-level summary; the detailed log lives in `AI_USAGE.md`.

### 9. Version Control
- Individual Git repository.
- Commit requirements per §5 (12+ commits, 6+ distinct days, pushed to a remote).

### Deliverables
- Git repository with code, `ADR.md`, and `AI_USAGE.md` at the root
- Report (4-5 pages) per §8, including the README and the §7 container-run evidence
- Attendance at the written comprehension check (§6)

The Dockerfile in your repo is the provided template with its TODOs filled in, nothing more. Not deliverables for Assignment 1: a Dockerfile you designed yourself, a `docker-compose.yml`, a CI pipeline, a cloud deployment, or a live URL. Those are Assignment 2.

### Grading Criteria
Each category below is scored normally and summed to a subtotal out of 100. The written comprehension check (§6) isn't one of these categories: it's scored separately, out of 100, and multiplies the subtotal (example in §6).

| Category | Weight | Breakdown |
|---|---|---|
| Working Features | 20% | Feature domain 1: 10% · Feature domain 2: 10% (both must use SQLite to count, and `container/run.sh` must pass per §7) |
| Testing | 15% | ≥70% coverage on core logic (§4); sliding scale below threshold, 0 if tests absent |
| Code Quality & Version Control | 20% | 10% code quality (justified tech choices per §1b, modularity between domains) · 10% commit cadence & hygiene (§5) |
| Documentation & Report | 15% | 5% SDLC explanation · 5% diagrams (must match repo) · 5% README/setup |
| Process Evidence | 30% | 15% `ADR.md` · 15% `AI_USAGE.md` |
| **Subtotal** | **100%** | |
| **× Written Comprehension Check (§6)** | **0-100%** | Multiplies the subtotal (worked example in §6) |

Process Evidence carries the largest share of the subtotal: it's the record of decisions made over time, not a snapshot at the deadline. Working features and code quality still matter (you need a genuinely working, well-built app), but AI makes "working" cheap and says little on its own about whether you understand what you shipped. None of this matters if you can't explain your project cold: the comprehension check sits outside the rubric, as a multiplier, because it's the one part that's closed-book, in person, and checked directly against your code.
