# moss-tasks-forensics

Evidence for a review of [Moss Inference](https://docs.moss.dev/docs/inference/overview):
the Portal, the Inference API and the Tasks API — what they promise, what they actually do,
and where the two drift apart.

This is the working record behind the one-page review in [`REVIEW.md`](REVIEW.md).
Every claim on that page points at something in here — the request that produced it,
the response that proves it, and the `X-Moss-Request-Id` Moss can look up on their side.

## Why raw HTTP

The Python SDK is well made, and it is also part of what is being tested. It retries,
it polls on a fixed cadence, and it attaches an `Idempotency-Key` you never see. A probe
that calls `tasks.run()` and asserts on the returned object cannot see any of that, and
cannot see the headers that decide most of the questions worth asking.

So the probes speak HTTP directly and record the wire. The SDK gets its own suite (`D`)
where the difference between the two is measured rather than assumed.

## Layout

```
mosslab/
  client.py        raw client: no retries, no backoff, evidence on every exchange
  model.py         result types
  preflight.py     credential and route check before spending anything
  run.py           suite runner, writes evidence/<stamp>/results.json + summary.md
  followup.py      re-reads finished tasks later and diffs their cost
  verify.py        pre-push check: no credentials in tracked files
  probes/
    surface.py     what the gateway exposes without credentials
    listing.py     the list route that is not in the reference
    inference.py   /v1/responses, the indexes header, streaming, rate-limit headers
    contract.py    what the gateway accepts and how it refuses
    idempotency.py replay semantics, including the concurrent case
    lifecycle.py   status transitions, cancellation, the trace route
    money.py       cost arithmetic and the two limit failures
    schema.py      output_schema and verification.passed
    failures.py    DNS failure, 404 page, impossible goal
    files.py       file listing, download, nested paths
    sdk.py         SDK poll cadence, counted at the transport
evidence/
  <stamp>-<label>/
    wire.jsonl     every exchange, credentials scrubbed at write time
    results.json   checks, expectations, observations, request ids
    summary.md     the same, rendered
findings/
  F01..F10       one file per confirmed finding: expected, observed, impact, fix
  HYPOTHESES.md  the questions asked before the tests, and how each one resolved
portal/
  *.png          the public login and signup pages, captured 2026-11-25
REVIEW.md        the one-page review this repo supports
```

## Running it

```bash
python -m venv .venv
.venv/Scripts/activate        # or: source .venv/bin/activate
pip install -r requirements.txt
pip install moss              # only needed for suite D

cp .env.example .env          # fill in MOSS_PROJECT_ID and MOSS_PROJECT_KEY
python -m mosslab.run --suites contract --label contract
```

Suites are independent and can be run one at a time:

| suite | what it costs | what it answers |
|---|---|---|
| `surface` | nothing | what answers without credentials; whether the model list matches the task models |
| `listing` | nothing | the undocumented list route; cursor semantics; which filters are real |
| `inference` | a few cents | `/v1/responses` shape, the `indexes` header, streaming events, rate-limit headers |
| `contract` | usually nothing | validation boundaries and error shape |
| `idempotency` | ~6 tasks | what "same body" means; what a concurrent replay does |
| `lifecycle` | ~4 tasks | transitions, cancellation at each state, the trace route |
| `money` | ~3 tasks, one slow | do the cost fields agree; what the caps actually cap |
| `schema` | ~3 tasks | does a schema miss still look like success |
| `failures` | ~3 tasks | what a broken page does to `error.code` |
| `files` | ~1 task | listing, download, nested paths, traversal |
| `sdk` | ~1 task | how many requests the SDK spends polling |

## Cost discipline

The client has a hard ceiling (`MOSS_MAX_USD`, default $3) and a task ceiling
(`MOSS_MAX_TASKS`, default 40). `create()` refuses before sending when either is
reached, so an accidental loop cannot run up a bill. Every task is created with an
explicit `max_cost_usd`; the default is never used.

The run's real spend is printed at the end and stored in `results.json`. If a probe
finds that a limit is not enforced, it cancels the task it created and says so.

The paid task runs spent **$0.0849**: 20 tasks across `core` and `deep`. The 5 inference
calls added well under a cent. The two paid runs had a $2.00 ceiling each and finished at
$0.0052 and $0.0797.

## What this does not cover

Stated up front, because a review that hides its edges is not useful:

- **7-day file expiry.** Verifying `410 files_expired` needs a week. The `files_expire_at`
  value is checked against `finished_at`; the expiry itself is not observed.
- **The 20-queued-task ceiling.** Reachable, but it would occupy the account for the
  length of the run and distort everything else. Left as a documented-only claim.
- **Bring-your-own-key.** Needs a second vendor account. Not tested.
- **Retrieval quality with a real index.** The inference probes use no index; they test the
  request surface, not whether the retrieved passages are good. Judging retrieval needs a
  corpus and a relevance standard, which is a different review.
- **The logged-in Portal.** The public login and signup pages were captured; the dashboard,
  project settings and usage views need a browser session, and I did not have one. The
  Portal section of `REVIEW.md` says exactly what was and was not seen.

## Evidence format

`wire.jsonl` is append-only, one JSON object per exchange:

```json
{"seq": 12, "probe": "I1", "request": {"method": "POST", "url": "...", "headers": {}},
 "response": {"status": 202, "body": {}, "bytes": 812}, "elapsed_ms": 143.2,
 "request_id": "..."}
```

`Authorization` is dropped and the project id and key are replaced with placeholders
**before** the line is written. A secret that never reaches disk cannot leak through a
forgotten `.gitignore`. `python -m mosslab.verify` re-checks the tracked tree anyway.
