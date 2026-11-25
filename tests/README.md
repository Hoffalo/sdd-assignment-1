# `tests/`: the cross-seam test

Each service has its own suite under `services/<name>/tests`, where the other service is replaced by a stub. This folder holds the one test that runs **both real services together**: two databases, and two HTTP servers on free ports. Nothing is stubbed.

```bash
TEST_SQLSERVER_URL='mssql://sa:<password>@localhost:14330/master' .venv/bin/python -m pytest
```

Without `TEST_SQLSERVER_URL` the tests are skipped, not failed. CI always sets it.

| Journey | What it proves |
|---|---|
| Delivery creates invites | The requests service's `POST /invites` body and service token are what the feedback service expects. |
| The requester's approval closes the request | The verdict endpoint, its token and the close rule agree; the timeline shows `avaliação`. |
| Delivery while feedback is down | The delivery stands, `invites_pending` is set, and the admin retry creates the invites once feedback is back. |
| A verdict while requests is down | The answer is stored (201), `verdict_pending` is set, and the resend reopens the request. |

The outages are real: the test stops one HTTP server, so the other side sees a refused connection, as it would if a container were down.

Why only four tests: every rule is already tested once inside its own service. Cross-service tests are slow (about 6 s each, mostly creating databases), and they fail for reasons that are hard to locate, so they cover the contract only. This keeps the pyramid shape (ADR-9).
