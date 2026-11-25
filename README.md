# moss-tasks-forensics

Evidence for a review of the Tasks API in [Moss Inference](https://docs.moss.dev/docs/inference/overview):
what it promises, what it actually does, and where the two drift apart.

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
  run.py           suite runner, writes evidence/<stamp>/results.json + summary.md
  followup.py      re-reads finished tasks later and diffs their cost
  verify.py        pre-push check: no credentials in tracked files
  probes/
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
| `contract` | usually nothing | validation boundaries, error shape, whether a list route exists |
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

## What this does not cover

Stated up front, because a review that hides its edges is not useful:

- **7-day file expiry.** Verifying `410 files_expired` needs a week. The `files_expire_at`
  value is checked against `finished_at`; the expiry itself is not observed.
- **The 20-queued-task ceiling.** Reachable, but it would occupy the account for the
  length of the run and distort everything else. Left as a documented-only claim.
- **Bring-your-own-key.** Needs a second vendor account. Not tested.
- **Inference (`/v1/responses`) beyond what the Tasks path touches.** Reviewed from the
  docs and SDK source, not exercised at volume.
