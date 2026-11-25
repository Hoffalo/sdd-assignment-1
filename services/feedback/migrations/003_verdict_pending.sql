-- The requester's verdict travels to the requests service over HTTP. If
-- that call fails the answer is still stored; this flag tells the AV
-- manager the request did not move yet and offers a resend (ADR-8).
-- A named default so a later migration can drop or change it by name.
ALTER TABLE feedback_responses ADD verdict_pending BIT NOT NULL
    CONSTRAINT df_feedback_responses_verdict_pending DEFAULT 0;
