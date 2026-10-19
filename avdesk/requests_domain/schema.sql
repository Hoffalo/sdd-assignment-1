-- Requests domain: intake, lifecycle and delivery.
-- Fixed columns hold what rules, filters and metrics read; the type-dependent
-- briefing answers live in answers_json because the question set changes per
-- request type and is edited as seed data, not as schema.
-- This file always describes the latest shape. Columns added after the first
-- release also appear in db.MIGRATIONS, which upgrades older databases.

CREATE TABLE IF NOT EXISTS diretorias (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS analysts (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS request_types (
    code                    TEXT PRIMARY KEY,
    label                   TEXT NOT NULL,
    min_lead_days           INTEGER NOT NULL CHECK (min_lead_days >= 0),
    detail_label            TEXT,
    position                INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS briefing_questions (
    key           TEXT PRIMARY KEY,
    type_code     TEXT REFERENCES request_types (code),
    section       TEXT NOT NULL,
    label         TEXT NOT NULL,
    help          TEXT NOT NULL DEFAULT '',
    kind          TEXT NOT NULL CHECK (kind IN ('text', 'textarea', 'url', 'date', 'choice', 'multichoice', 'yesno')),
    options_json  TEXT NOT NULL DEFAULT '[]',
    required      INTEGER NOT NULL DEFAULT 0 CHECK (required IN (0, 1)),
    position      INTEGER NOT NULL,
    depends_on    TEXT,
    depends_value TEXT
);

CREATE TABLE IF NOT EXISTS requests (
    id                INTEGER PRIMARY KEY,
    public_code       TEXT UNIQUE,
    tracking_token    TEXT NOT NULL UNIQUE,
    requester_name    TEXT NOT NULL,
    requester_email   TEXT NOT NULL,
    diretoria_id      INTEGER NOT NULL REFERENCES diretorias (id),
    type_code         TEXT NOT NULL REFERENCES request_types (code),
    type_detail       TEXT NOT NULL DEFAULT '',
    title             TEXT NOT NULL,
    campaign          TEXT NOT NULL DEFAULT '',
    needs_c_level_approval    INTEGER NOT NULL DEFAULT 0 CHECK (needs_c_level_approval IN (0, 1)),
    needed_by         TEXT NOT NULL,
    needed_by_reason  TEXT NOT NULL,
    rush              INTEGER NOT NULL DEFAULT 0 CHECK (rush IN (0, 1)),
    rush_reason       TEXT NOT NULL DEFAULT '',
    answers_json      TEXT NOT NULL DEFAULT '{}',
    briefing_score    INTEGER NOT NULL CHECK (briefing_score BETWEEN 0 AND 100),
    status            TEXT NOT NULL CHECK (status IN ('submitted', 'needs_info', 'accepted', 'in_production',
                                                      'in_review', 'delivered', 'closed', 'declined', 'cancelled')),
    analyst_id        INTEGER REFERENCES analysts (id),
    accepted_at       TEXT,
    review_url        TEXT,
    delivery_url      TEXT,
    delivered_at      TEXT,
    task_url          TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_requests_status ON requests (status);

CREATE TABLE IF NOT EXISTS request_events (
    id           INTEGER PRIMARY KEY,
    request_id   INTEGER NOT NULL REFERENCES requests (id),
    from_status  TEXT,
    to_status    TEXT NOT NULL,
    note         TEXT NOT NULL DEFAULT '',
    actor        TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_request_events_request ON request_events (request_id);
