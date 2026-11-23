-- Feedback domain: post-delivery invites and responses.
-- request_id is a soft reference with NO foreign key into the requests
-- domain. Each invite stores a snapshot of the delivered request instead, so
-- this domain can move to its own service and database in Assignment 2.

CREATE TABLE IF NOT EXISTS feedback_invites (
    id               INTEGER PRIMARY KEY,
    token            TEXT NOT NULL UNIQUE,
    request_id       INTEGER NOT NULL,
    public_code      TEXT NOT NULL,
    request_title    TEXT NOT NULL,
    type_label       TEXT NOT NULL,
    diretoria        TEXT NOT NULL,
    delivery_url     TEXT NOT NULL,
    needed_by        TEXT NOT NULL,
    delivered_at     TEXT NOT NULL,
    recipient_label  TEXT NOT NULL,
    is_requester     INTEGER NOT NULL CHECK (is_requester IN (0, 1)),
    expires_at       TEXT NOT NULL,
    used_at          TEXT,
    created_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feedback_invites_request ON feedback_invites (request_id);

CREATE TABLE IF NOT EXISTS feedback_responses (
    id                 INTEGER PRIMARY KEY,
    invite_id          INTEGER NOT NULL UNIQUE REFERENCES feedback_invites (id),
    rating_tone        INTEGER NOT NULL CHECK (rating_tone BETWEEN 1 AND 5),
    rating_quality     INTEGER NOT NULL CHECK (rating_quality BETWEEN 1 AND 5),
    rating_process     INTEGER NOT NULL CHECK (rating_process BETWEEN 1 AND 5),
    rating_usefulness  INTEGER NOT NULL CHECK (rating_usefulness BETWEEN 1 AND 5),
    outcome            TEXT NOT NULL CHECK (outcome IN ('approved', 'minor_tweaks', 'major_changes')),
    comment            TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL
);
