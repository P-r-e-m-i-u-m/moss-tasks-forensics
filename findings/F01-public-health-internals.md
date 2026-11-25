# F01 — `/health` is public and reports the deployment's internals

**Severity:** S2 — information disclosure, no credentials required
**Status:** confirmed, reproduced twice
**Route:** `GET https://inference.moss.dev/health` (note: outside `/v1`)
**Request id:** `4ac255cc446542fca98307e4a127ff3d`

## Expected

Either no public health endpoint, or one that returns `{"status": "ok"}` and nothing else.
A health check exists to tell a load balancer whether to send traffic, not to describe the
deployment to whoever asks.

## Observed

```
200 OK
{
  "status": "ok",
  "revision": "e31376961340ebb5687775ae4a984f8424c444a0",
  "projects": 1,
  "indexes": 0,
  "models": 0,
  "decide": 0,
  "decide_projects": 0,
  "traces": {
    "queued": 0,
    "sent_spans": 2984,
    "dropped_spans": 0,
    "failed_spans": 0,
    "content_traces": 1493,
    "dropped_content": 0,
    "too_large_content": 0,
    "opted_out_content": 0,
    "unavailable_content": 0
  }
}
```

No `Authorization` header was sent. `curl https://inference.moss.dev/health` is the whole
reproduction.

## Why it matters

- **`revision` is the exact deployed commit.** Anyone who can map a commit to a release can
  tell which version is running before deciding whether a known bug applies.
- **`projects` counts tenants.** It returned `1` here, which says this gateway serves a single
  project. That is a fact about the business, published for free.
- **The `traces` block is a live telemetry feed.** `sent_spans` and `content_traces` climb as
  customers use the product. Polling this endpoint gives a rough usage curve for the whole
  deployment without an account.
- **`opted_out_content` and `unavailable_content` are named.** They disclose that content
  tracing exists, that customers can opt out, and roughly how often they do. Those are
  internal product decisions surfaced in a public counter.

## Fix

Return `{"status": "ok"}` from the public path. Put the counters behind the admin credential
that already exists, or behind a separate authenticated `/internal/health`. If an
unauthenticated liveness probe is required by the load balancer, keep it at a path that
returns a fixed body.

## Evidence

`evidence/20261125T111443Z-surface/wire.jsonl`, probe `P`, the `GET /health` exchange.
`evidence/20261125T111443Z-surface/results.json`, check `health_requires_auth`.
