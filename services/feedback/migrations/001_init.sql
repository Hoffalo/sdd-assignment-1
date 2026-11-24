-- Feedback service, first schema: post-delivery invites and responses.
-- The Assignment 1 SQLite schema ported to SQL Server (see the requests
-- service's 001_init.sql for the type mapping). Never edit it once applied.
--
-- request_id is a soft reference with NO foreign key: the request lives in
-- the requests service's own database, where no constraint can reach
-- (ADR-3). Each invite stores a snapshot of the delivered request instead,
-- so this service never reads the requests database.

CREATE TABLE feedback_invites (
    id               INT IDENTITY(1, 1) PRIMARY KEY,
    token            NVARCHAR(100)  NOT NULL UNIQUE,
    request_id       INT            NOT NULL,
    public_code      NVARCHAR(20)   NOT NULL,
    request_title    NVARCHAR(300)  NOT NULL,
    type_label       NVARCHAR(200)  NOT NULL,
    diretoria        NVARCHAR(200)  NOT NULL,
    delivery_url     NVARCHAR(2000) NOT NULL,
    needed_by        DATE           NOT NULL,
    delivered_at     DATETIME2      NOT NULL,
    recipient_label  NVARCHAR(200)  NOT NULL,
    is_requester     BIT            NOT NULL,
    expires_at       DATETIME2      NOT NULL,
    used_at          DATETIME2      NULL,
    created_at       DATETIME2      NOT NULL
);

CREATE INDEX idx_feedback_invites_request ON feedback_invites (request_id);

CREATE TABLE feedback_responses (
    id                 INT IDENTITY(1, 1) PRIMARY KEY,
    invite_id          INT            NOT NULL UNIQUE REFERENCES feedback_invites (id),
    rating_tone        INT            NOT NULL CHECK (rating_tone BETWEEN 1 AND 5),
    rating_quality     INT            NOT NULL CHECK (rating_quality BETWEEN 1 AND 5),
    rating_process     INT            NOT NULL CHECK (rating_process BETWEEN 1 AND 5),
    rating_usefulness  INT            NOT NULL CHECK (rating_usefulness BETWEEN 1 AND 5),
    outcome            NVARCHAR(20)   NOT NULL CHECK (outcome IN ('approved', 'minor_tweaks', 'major_changes')),
    comment            NVARCHAR(MAX)  NOT NULL DEFAULT N'',
    created_at         DATETIME2      NOT NULL
);
