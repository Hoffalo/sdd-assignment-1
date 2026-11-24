-- Requests service, first schema: intake, lifecycle and delivery.
-- This is the Assignment 1 SQLite schema (with its five in-code migrations
-- already folded in) ported to SQL Server. Never edit it once applied;
-- every later change is a new numbered file.
--
-- Port notes: INTEGER PRIMARY KEY -> INT IDENTITY; TEXT -> NVARCHAR, sized
-- where the column is a key or indexed (an index key is limited to 900
-- bytes, so NVARCHAR(MAX) cannot be one); 0/1 flags -> BIT; ISO date
-- strings -> DATE and DATETIME2, always holding UTC.
-- Fixed columns hold what rules, filters and metrics read; the type-dependent
-- briefing answers live in answers_json because the question set changes per
-- request type and is edited as seed data, not as schema.

CREATE TABLE diretorias (
    id    INT IDENTITY(1, 1) PRIMARY KEY,
    name  NVARCHAR(200) NOT NULL UNIQUE
);

CREATE TABLE analysts (
    id    INT IDENTITY(1, 1) PRIMARY KEY,
    name  NVARCHAR(200) NOT NULL UNIQUE
);

CREATE TABLE request_types (
    code           NVARCHAR(50)  NOT NULL PRIMARY KEY,
    label          NVARCHAR(200) NOT NULL,
    min_lead_days  INT           NOT NULL CHECK (min_lead_days >= 0),
    detail_label   NVARCHAR(200) NULL,
    position       INT           NOT NULL
);

-- id exists only to keep a stable order between questions that share a
-- position (SQLite used its implicit rowid for this; SQL Server has none).
CREATE TABLE briefing_questions (
    id             INT IDENTITY(1, 1) NOT NULL UNIQUE,
    [key]          NVARCHAR(100) NOT NULL PRIMARY KEY,
    type_code      NVARCHAR(50)  NULL REFERENCES request_types (code),
    section        NVARCHAR(200) NOT NULL,
    label          NVARCHAR(500) NOT NULL,
    help           NVARCHAR(1000) NOT NULL DEFAULT N'',
    kind           NVARCHAR(20)  NOT NULL
                   CHECK (kind IN ('text', 'textarea', 'url', 'date', 'choice', 'multichoice', 'yesno')),
    options_json   NVARCHAR(MAX) NOT NULL DEFAULT N'[]',
    required       BIT           NOT NULL DEFAULT 0,
    position       INT           NOT NULL,
    depends_on     NVARCHAR(100) NULL,
    depends_value  NVARCHAR(200) NULL
);

CREATE TABLE requests (
    id                      INT IDENTITY(1, 1) PRIMARY KEY,
    public_code             NVARCHAR(20)   NULL,
    tracking_token          NVARCHAR(100)  NOT NULL UNIQUE,
    requester_name          NVARCHAR(200)  NOT NULL,
    requester_email         NVARCHAR(320)  NOT NULL,
    diretoria_id            INT            NOT NULL REFERENCES diretorias (id),
    type_code               NVARCHAR(50)   NOT NULL REFERENCES request_types (code),
    type_detail             NVARCHAR(500)  NOT NULL DEFAULT N'',
    title                   NVARCHAR(300)  NOT NULL,
    campaign                NVARCHAR(300)  NOT NULL DEFAULT N'',
    needs_c_level_approval  BIT            NOT NULL DEFAULT 0,
    needed_by               DATE           NOT NULL,
    needed_by_reason        NVARCHAR(MAX)  NOT NULL,
    rush                    BIT            NOT NULL DEFAULT 0,
    rush_reason             NVARCHAR(MAX)  NOT NULL DEFAULT N'',
    answers_json            NVARCHAR(MAX)  NOT NULL DEFAULT N'{}',
    briefing_score          INT            NOT NULL CHECK (briefing_score BETWEEN 0 AND 100),
    status                  NVARCHAR(20)   NOT NULL
                            CHECK (status IN ('submitted', 'needs_info', 'accepted', 'in_production',
                                              'in_review', 'delivered', 'closed', 'declined', 'cancelled')),
    analyst_id              INT            NULL REFERENCES analysts (id),
    accepted_at             DATETIME2      NULL,
    review_url              NVARCHAR(2000) NULL,
    delivery_url            NVARCHAR(2000) NULL,
    delivered_at            DATETIME2      NULL,
    task_url                NVARCHAR(2000) NULL,
    created_at              DATETIME2      NOT NULL,
    updated_at              DATETIME2      NOT NULL
);

-- public_code is set right after the insert, so it is briefly NULL; a plain
-- UNIQUE constraint in SQL Server allows only one NULL, a filtered index does not.
CREATE UNIQUE INDEX ux_requests_public_code ON requests (public_code) WHERE public_code IS NOT NULL;
CREATE INDEX idx_requests_status ON requests (status);

CREATE TABLE request_events (
    id           INT IDENTITY(1, 1) PRIMARY KEY,
    request_id   INT            NOT NULL REFERENCES requests (id),
    from_status  NVARCHAR(20)   NULL,
    to_status    NVARCHAR(20)   NOT NULL,
    note         NVARCHAR(MAX)  NOT NULL DEFAULT N'',
    actor        NVARCHAR(200)  NOT NULL,
    created_at   DATETIME2      NOT NULL
);

CREATE INDEX idx_request_events_request ON request_events (request_id);
