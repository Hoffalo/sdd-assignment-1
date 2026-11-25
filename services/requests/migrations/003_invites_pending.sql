-- Delivering creates feedback invites with an HTTP call to the feedback
-- service. If that call fails the delivery still stands; this flag tells
-- the AV manager the invites are missing and offers a retry (ADR-8).
-- A named default so a later migration can drop or change it by name.
ALTER TABLE requests ADD invites_pending BIT NOT NULL
    CONSTRAINT df_requests_invites_pending DEFAULT 0;
