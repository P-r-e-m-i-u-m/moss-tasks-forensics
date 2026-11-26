# F07 — `max_cost_usd` is a soft cap, and `budget_exceeded` never fired

**Severity:** S3 — the documented ceiling is not a ceiling
**Status:** confirmed
**Where:** `limits.max_cost_usd` on `POST /v1/tasks`
**Request id:** `5cf3841f50814fc7be2a1520f3fd8958`

## Expected

A task created with `"limits": {"max_cost_usd": 0.02}` stops at $0.02 of model spend and
ends `failed` with `error.code: "budget_exceeded"`. The reference lists `budget_exceeded`
as one of the four failure codes and says the limit "caps model calls only".

## Observed

The task ran to completion:

```
status:   completed
error:    null
model_usd: 0.021088
total_usd: 0.021755
cap:       0.020000
```

Model spend is 5.4% over the cap. There was no `budget_exceeded`, no warning field, and no
truncation of the answer. The task produced its full result.

The overshoot is small here because the last model call happened to cost about $0.001. The
mechanism is the issue: the cap is checked between calls, not against the projected cost of
the next call, so the final call can cross it by any amount up to the cost of one call. The
reference does not say the cap is soft, and a client reading "max" has no reason to expect
an overrun.

The contrast with `max_runtime_seconds` is sharp. That limit is enforced precisely: a
60-second cap ended `failed` with `error.code: "time_limit"` and `"Stopped after 60 s"`, and
the work already done was still billed. One limit is a hard stop with a code; the other is
a suggestion.

## Why it matters

The cap is the only cost control a caller has per task. If it can be exceeded silently, then
the number in `limits` is not a bound and cannot be used to size a batch, enforce a tenant
budget, or guarantee that a runaway task stops. The failure code exists in the docs, so a
client will write a handler for it and never see it.

## Fix

Either enforce it as a bound or document the bound:

1. Before each model call, compare spent + estimated next call to the cap. If the call would
   cross it, stop and fail with `budget_exceeded`. The estimate does not need to be exact;
   the point is to stop before the overshoot, not after it.
2. If a soft cap is deliberate, rename it (`max_model_cost_usd_soft`) and document the
   maximum overshoot. Add `budget_overshoot_usd` to `usage` so the caller can see it.
3. Always emit a structured signal when the cap is crossed, even if the task completes.
   `usage.budget_exceeded: true` would be enough.

## Evidence

- `evidence/20261125T112920Z-deep/`, probe `M2`, checks `budget_exceeded_reported` and
  `budget_respected`. The task is `task_06eaf6816add4da49f8067075e9b7e7a`.
- The same run, probe `M3`: `max_runtime_seconds: 60` → `failed`, `error.code: time_limit`,
  `"Stopped after 60 s"`, `total_usd: 0.012515`. Request id `005147c5698044c6904f2a2a35bfbfa8`.
- Docs: `docs/api-reference/v1/inference/tasks.md`, `limits.max_cost_usd` row and the
  failure-code list.
