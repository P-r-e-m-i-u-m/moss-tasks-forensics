# F06 — Two fields called cost, and they disagree

**Severity:** S2 — the number a client reads at completion is not the number it is billed
**Status:** confirmed on every finished task in every run
**Where:** `usage.cost_usd` and `usage.cost.total_usd` on `GET /v1/tasks/{id}`
**Request id:** `9f77835d7c92482aafb29f158c12027a`

## Expected

One total, or two fields that are documented as different things. The reference says:

> Each task reports its cost in `usage.cost`.

and lists `usage.cost_usd` as a field with no definition. The natural reading is that
`cost_usd` is the task's cost.

## Observed

On a 12-second task:

```json
"usage": {
  "cost": {
    "model_usd":   0.003755,
    "browser_usd": 0.0003333333333333333,
    "traffic_usd": null,
    "total_usd":   0.004088
  },
  "cost_usd": 0.003755
}
```

`usage.cost_usd` equals `model_usd`. `usage.cost.total_usd` equals `model_usd +
browser_usd`. The two differ by the browser charge, which is small on a short task and
larger on a long one:

| task | `cost_usd` | `total_usd` | understatement |
|---|---:|---:|---:|
| 12 s, 3 model calls | 0.003755 | 0.004088 | 8.9% |
| 109 s, 15 model calls | 0.021088 | 0.021755 | 3.2% |

`traffic_usd` is `null` on all 18 finished tasks, so `total_usd` is not final either. The
reference does warn that traffic fields "can be `null` until a few hours after the task
ends", so the null itself is documented. What is missing is any way to tell whether a
given response is settled: no `settled_at`, no `is_final`, no `estimated` flag. A client
that stores `total_usd` at completion stores a number that may change later, and a client
that stores `cost_usd` stores a number that was never the total.

I re-read all 18 tasks 14 minutes after the runs: `traffic_usd` was still `null` and no
`total_usd` had changed. That is consistent with the documented "few hours" delay and does
not prove the settlement works. It does show that the delay is long enough to matter to a
dashboard.

## Why it matters

This is a metering API. Two fields whose names both mean "cost" and whose values differ by
a real charge will be read differently by different clients. A per-task cost report built on
`cost_usd` understates the bill; a budget check built on `total_usd` compares a provisional
number to a cap. Neither field is wrong on its own. The pair is the problem.

## Fix

Pick one:

1. Define `cost_usd` as model-only and rename it `model_usd` (it already exists inside
   `cost`), so there is exactly one total.
2. Make `cost_usd` an alias for `total_usd` and deprecate the duplicate.
3. Keep both and document the difference in the field table, in one sentence each.

For settlement, add `cost.settled_at` or `cost.is_final` and return `traffic_usd: 0` with
`estimated: true` until the real number arrives. A nullable field with no state flag forces
every client to invent its own polling policy.

## Evidence

- `evidence/20261125T112920Z-deep/`, probe `M1`, checks `two_totals_agree` and
  `traffic_settled_at_completion`.
- `evidence/20261125T112920Z-deep/`, probe `M2`, the same split on a 109-second task.
- `cost-followup-20261125T114258Z.json` and `cost-followup-20261125T114251Z.json`: 0 of 18
  tasks changed cost after completion, all `traffic_usd` still `null`.
- Docs: `docs/api-reference/v1/inference/tasks.md`, the `usage` row; `docs/inference/pricing.md`,
  "Each task reports its cost in `usage.cost`".
