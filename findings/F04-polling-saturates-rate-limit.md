# F04 — Polling is a flat 2-second loop with no shared budget, and it eats the rate limit

**Severity:** S2 — the default integration pattern breaks itself under concurrency
**Status:** confirmed from source and from the published limits
**Where:** `MossInference.tasks.wait()` / `run()` in both SDKs

## The numbers

The SDKs poll on a fixed interval:

- Python: `_POLL_INTERVAL = 2.0` (`inference.py:85`), used as the default of `wait` and `run`.
- JavaScript: `const DEFAULT_POLL = 2000` (`inference/index.ts`).

The documented rate limit is **120 requests per minute sustained, burst 10**
(`docs/inference/errors-and-limits.md`, the free tier column).

One task at defaults is `60 / 2 = 30` GETs per minute. The loop is per-call, so the total is
linear in the number of tasks being awaited:

| concurrent tasks | poll requests/min | share of sustained limit |
|---:|---:|---:|
| 1 | 30 | 25% |
| 2 | 60 | 50% |
| 4 | 120 | **100%** |
| 8 | 240 | 200% |

Four concurrent tasks — a completely ordinary number — saturate the sustained request budget
with polling alone, before a single `responses.create` call or any other API traffic. The
default `max_runtime_seconds` is 20 minutes, so this is the state the client sits in for
twenty minutes per task.

A single 20-minute task spends about **600 GETs** on `GET /v1/tasks/{id}`.

## What the loop does not do

Read the wait loop (`inference.py:1210-1247`):

```python
while True:
    ...
    task = await self.retrieve(task_id, ...)
    if task.status not in _WAITING:
        return task
    ...
    await asyncio.sleep(min(interval, left))
```

- **No jitter.** Every client that starts a task at the same moment polls at the same offset,
  so a fleet synchronises onto the same two-second ticks.
- **No backoff between successful polls.** The interval never widens as a task runs long,
  even though the probability of a state change in the next two seconds drops sharply after
  the first minute.
- **The rate-limit headers are never read.** The docs say the gateway returns
  `x-ratelimit-remaining-requests` and `x-ratelimit-reset-requests`. Neither SDK references
  them anywhere — I searched both files for `ratelimit` and got zero matches. The client can
  be one request from a `429` and will still poll on schedule.
- **`Retry-After` is honoured only on failure.** `_retry()` reads it when a poll is retried
  (`inference.py:1817-1840`), which is correct, but that is recovery, not pacing. Nothing
  slows down *before* the limit is hit.

## Why it matters

The failure this produces is confusing rather than obvious. Four tasks poll happily, the
project hits `429 rate_limit_exceeded`, and the error surfaces on whatever call happens to be
in flight — possibly a `responses.create` in a different part of the application that has
nothing to do with the tasks. The SDK will retry it with backoff, so it usually recovers, and
the user never learns that their task polling is the cause. Under load it becomes a
self-inflicted outage that looks like a Moss capacity problem.

## Fix, in order of payoff

1. **Have `wait` read `x-ratelimit-remaining-requests` and stretch the interval when it is
   low.** The information is already on the wire and already paid for.
2. **Back off geometrically after the first 30 seconds** — 2s, 4s, 8s, capped at 15s. A task
   that runs four minutes does not need 120 polls; it needs to notice the end within a few
   seconds of it happening.
3. **Add jitter** (a random 0-500ms) so concurrent clients do not align.
4. **Expose a shared limiter** on the client so N concurrent `wait()` calls draw from one
   budget rather than N independent loops.
5. Alternatively, a `Retry-After`-style hint on the task object — `retry_after_ms` — would let
   every client, SDK or not, poll correctly without guessing.

## Evidence

- `mosslab/probes/sdk.py`, probe `D` counts GETs at the transport for one real task and
  compares the count to the elapsed time.
- Source line numbers above are from `usemoss/moss@main`.
- Rate limits: `docs/inference/errors-and-limits.md`, "Limits" table.
