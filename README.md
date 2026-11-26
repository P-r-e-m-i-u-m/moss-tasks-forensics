# moss-tasks-forensics

**A wire-level review of the Moss Inference Portal, Inference API and Tasks API.**
Real tasks, real spend, real request ids — including what held up.

I ran 20 browser tasks and 5 inference calls against Moss, spent **$0.0849**, and wrote
each question down before testing it. Ten findings are confirmed. Five of my guesses were
wrong, and they are in here too, because a review that only lists defects is not measuring
anything.

**[Read the one-page review →](REVIEW.md)**

| metric | value |
|---|---|
| tasks | 20, across seven paid suites |
| inference | 5 calls at `moss/fastlane-1` |
| spend | $0.0849 in tasks, under a cent in tokens |
| evidence | 8 runs, 320 recorded exchanges, credentials scrubbed at write time |
| outcome | 10 confirmed findings, 5 falsified hypotheses |

## What held up

Idempotency is the strongest thing in the product. Replays return
`Idempotent-Replayed: true`, a reordered JSON body still dedupes, two concurrent creates
with the same key produce one task, 255-character keys work and 256 is a clean `400`.
Cancellation behaves at every state. Files list, download, and refuse traversal.
`max_runtime_seconds` is a real stop: `failed`, `time_limit`, "Stopped after 60 s".

The rest of the review is measured against it.

## What broke

| id | finding | severity |
|---|---|---|
| F01 | [`/health`](findings/F01-public-health-internals.md) is public and reports the deployed commit, tenant count and live trace counters | S2 |
| F02 | [`/v1/models`](findings/F02-models-catalog-mismatch.md) is public, lists 19 models, and the Tasks API accepts none of them | S3 |
| F03 | [The trace and video routes](findings/F03-undocumented-trace-surface.md) are in both SDKs and in no documentation | S2 |
| F04 | [SDK polling](findings/F04-polling-saturates-rate-limit.md) is a flat 2-second loop; four tasks use the whole 120 req/min budget | S2 |
| F05 | [`GET /v1/tasks`](findings/F05-undocumented-list-route.md) exists, paginates, and its `before` cursor is ignored | S2 |
| F06 | [`cost_usd` and `total_usd`](findings/F06-cost-fields-disagree.md) disagree; the first is model-only | S2 |
| F07 | [`max_cost_usd`](findings/F07-soft-budget-cap.md) is a soft cap, and `budget_exceeded` never fired | S3 |
| F08 | [`verification.passed`](findings/F08-verification-is-shape-only.md) checks that the JSON fits the schema, not that the answer is right | S3 |
| F09 | [DNS failure, a 404 page and an impossible company](findings/F09-failures-complete.md) all end `completed`; `no_answer` never fires | S2 |
| F10 | [A mistyped index](findings/F10-missing-index-403.md) returns `403 permission_error`, sending you to check credentials | S3 |

One of them, in full:

```
POST /v1/tasks   limits: {"max_cost_usd": 0.02}
status:           completed
model_usd:        0.021088
budget_exceeded:  never emitted
```

Each finding has expected, observed, impact and a repro, plus the `X-Moss-Request-Id` Moss
can look up.

## Why raw HTTP

The Python SDK is well made, and it is also part of what is being tested. It retries, it
polls on a fixed cadence, and it attaches an `Idempotency-Key` you never see. A probe that
calls `tasks.run()` and asserts on the returned object cannot see any of that, and cannot
see the headers that decide most of the questions worth asking.

So the probes speak HTTP directly and record the wire. The SDK gets its own suite (`sdk`),
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
  probes/          one file per suite (surface, listing, inference, contract,
                   idempotency, lifecycle, money, schema, failures, files, sdk)
evidence/
  <stamp>-<label>/
    wire.jsonl     every exchange, credentials scrubbed at write time
    results.json   checks, expectations, observations, request ids
    summary.md     the same, rendered
findings/          F01..F10, one file each, plus HYPOTHESES.md
portal/            public login and signup pages, captured 2026-11-25
REVIEW.md          the one-page review this repo supports
```

## Run it

```bash
python -m venv .venv
.venv/Scripts/activate        # or: source .venv/bin/activate
pip install -r requirements.txt
pip install moss              # only needed for suite sdk

cp .env.example .env          # fill in MOSS_PROJECT_ID and MOSS_PROJECT_KEY
python -m mosslab.run --suites contract --label contract
```

Suites are independent; start with the ones that cost nothing:

| suite | what it costs | what it answers |
|---|---|---|
| `surface` | nothing | what answers without credentials; whether the model list matches the task models |
| `listing` | nothing | the undocumented list route; cursor semantics; which filters are real |
| `contract` | usually nothing | validation boundaries and error shape |
| `inference` | a few cents | `/v1/responses` shape, the `indexes` header, streaming events, rate-limit headers |
| `idempotency` | ~6 tasks | what "same body" means; what a concurrent replay does |
| `lifecycle` | ~4 tasks | transitions, cancellation at each state, the trace route |
| `money` | ~3 tasks, one slow | do the cost fields agree; what the caps actually cap |
| `schema` | ~3 tasks | does a schema miss still look like success |
| `failures` | ~3 tasks | what a broken page does to `error.code` |
| `files` | ~1 task | listing, download, nested paths, traversal |
| `sdk` | ~1 task | how many requests the SDK spends polling |

## Cost discipline

The client has a hard ceiling (`MOSS_MAX_USD`, default $3) and a task ceiling
(`MOSS_MAX_TASKS`, default 40). `create()` refuses before sending when either is reached,
so an accidental loop cannot run up a bill. Every task is created with an explicit
`max_cost_usd`; the default is never used.

The run's real spend is printed at the end and stored in `results.json`. If a probe finds
that a limit is not enforced, it cancels the task it created and says so.

The paid runs spent **$0.0849**: 20 tasks across `core` and `deep`, each with a $2.00
ceiling, finishing at $0.0052 and $0.0797; the 5 inference calls added under a cent.

## What this does not cover

A review that hides its edges is not useful:

- **7-day file expiry.** Verifying `410 files_expired` needs a week, so only the
  `files_expire_at` value is checked against `finished_at`.
- **The 20-queued-task ceiling.** Reachable, but it would occupy the account for the run and
  distort everything else.
- **Bring-your-own-key.** Needs a second vendor account.
- **Retrieval quality with a real index.** The inference probes use no index; they test the
  request surface, not whether the retrieved passages are good. That needs a corpus and a
  relevance standard, which is a different review.
- **The logged-in Portal.** Only the public login and signup pages were captured. The
  dashboard, project settings and usage views need a browser session I did not have, and
  `REVIEW.md` says so.

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

MIT licensed. The evidence is real; the account it ran against is mine.
