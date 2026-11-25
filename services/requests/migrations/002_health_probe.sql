-- One-row table that GET /health updates, so the check proves this
-- service's login can write to its own database and not only read it.
-- The CHECK keeps it a single row however often the probe runs.
CREATE TABLE health_probe (
    id          INT       NOT NULL PRIMARY KEY CHECK (id = 1),
    checked_at  DATETIME2 NOT NULL
);

INSERT INTO health_probe (id, checked_at) VALUES (1, SYSUTCDATETIME());
