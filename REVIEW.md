# Moss Inference: Portal, Inference API, Tasks API

I spent $0.085 and ran 20 browser tasks to find out how far Moss's documented contract
holds. The primitives are good. The edges are where it drifts.

Code, logs and screenshots are in this repo. Live findings carry an `X-Moss-Request-Id` Moss
can look up; the two source-only ones cite file and line.

## Portal

**Good.** Auth is fast and clear: GitHub, Google or email, no card, and the semantic-search
pitch is on the page.

**Weak.** Signup sells semantic search while the link carries `?next=%2Finference`. Nothing
explains how Inference and Tasks relate, and there is no code sample.

**Fix.** Route the referral to the product it names, add a curl example and a search-vs-task
fork, and show the credit balance before the first call.

**Tested.** Public login and signup only (`portal/`); the dashboard, settings, keys and usage
views need a session I did not have.

## Inference API

**Good.** `/v1/responses` is OpenAI-shaped: `object`, `output[]`, token usage,
`response.output_text.delta` streaming. Unknown models get `400 model_not_found` naming
`moss/fastlane-1`. Body `indexes` gets a precise `400 unsupported_parameter`.

**Weak.** A mistyped `X-Moss-Indexes` returns `403 permission_error` ("outside this
project"), not `404`, so a typo sends you to check credentials. `/v1/models` is public, lists
19 models, and none are accepted by the Tasks API. `/health` is public and exposes the
deployed commit, tenant count and live trace counters.

**Fix.** 404 for an unknown index; auth on `/models`; a `capabilities` field separating task
from inference models; `/health` reduced to `{"status":"ok"}`.

**Tested.** 5 calls at `moss/fastlane-1`: response shape, usage, rate-limit headers, body vs
header `indexes`, unknown model, SSE. No index was created, so retrieval quality is not
assessed.

## Tasks API

**Good.** Idempotency is the strongest part: replays return `Idempotent-Replayed: true`,
reordered keys dedupe, concurrent creates with one key produce one task, 255-character keys
work and 256 is a clean `400`. Cancellation and files are correct, including nested paths and
traversal refusal. `max_runtime_seconds` is a real stop (`failed`, `time_limit`, "Stopped
after 60 s"). The trace and video routes are the best debugging surface in the product and
both are undocumented: timeline, screenshots, and an mp4 of the session.

**Weak.** `GET /v1/tasks` exists, paginates and is undocumented; `before` is accepted but
ignored, returning page one with `has_more: true`, so backward pagination loops forever.
`cost_usd` is model-only while `total_usd` adds the browser charge (8.9% apart on a
12-second task), and `traffic_usd` is null at completion with no settlement flag. A $0.02
`max_cost_usd` produced $0.021088 of model spend, completed, and never emitted
`budget_exceeded`. `verification.passed` is shape-only: a page with no book returned
`{"isbn":"Not found","author":"Not found"}` and passed. DNS failure, a 404 page and an
impossible company all ended `completed`; `no_answer` never fired. Polling is a flat
2-second loop: four concurrent tasks use the entire 120 req/min sustained limit.

**Fix.** Document the list route and fix or reject `before`; make `cost_usd` the total;
enforce the budget cap; return `no_answer` when the agent could not answer; document
`/trace` and `/video`; back off on the rate-limit headers.

**Tested.** 20 tasks across the seven paid suites: idempotency (including a concurrent race),
lifecycle, cost arithmetic, schema, failures, files, SDK polling; plus trace/video readback.

**Where it broke.** The `before` loop, the cost-field split, the soft cap, the shape-only
pass, completed-on-failure, and 403-for-a-typo, each with expected/observed/impact/repro in
`findings/`.

## Confirmed vs unverified

`F01`–`F10` are confirmed. Five guesses were falsified: the schema being missed, idempotency
under reordered keys, concurrent creates duplicating, body `indexes` being ignored, and the
list route being absent; `HYPOTHESES.md` records each. `traffic_usd` was still null 14
minutes after the runs; the docs say a few hours, so settlement is unverified.

**Not tested:** the logged-in Portal, 7-day file expiry, the 20-queued-task ceiling,
bring-your-own-key, and retrieval quality with a real index.

Every live finding has an `X-Moss-Request-Id`; Moss can look up the exact exchange.
