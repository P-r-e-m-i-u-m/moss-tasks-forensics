# F05 — There is a task list route, it is undocumented, and its backward cursor does nothing

**Severity:** S2 — a working route with a trap in it
**Status:** confirmed against 18 real tasks, three runs
**Route:** `GET https://inference.moss.dev/v1/tasks`
**Request ids:** `b4ad49ac387d40afbcd428bfe27fe2d6` (page 1),
`f7fa3adf12494b0ca2fecc4866e42179` (`before`),
`b0856b0eb9f6473c85d1df3956b3d78a` (`before` with an unknown id)

## Expected

The API reference documents five task routes: create, get, cancel, list files, download
file. A sixth route should return `404` or `405`, and probe `C` originally asserted exactly
that.

## Observed

`GET /v1/tasks` returns `200` with an OpenAI-shaped page:

```json
{
  "object": "list",
  "data": [ ... 18 tasks ... ],
  "first_id": "task_cf17fc31c9684822ace8141d270b0906",
  "last_id": "task_0a847b767dd24af18d8b2e8f637d0795",
  "has_more": true,
  "total": 18
}
```

Most of it is well built:

| parameter | behaviour |
|---|---|
| `limit` | 1 to 100. `0`, `101`, `abc` all return `400` with the same clear message. |
| `after` | works. Rejects `task_bogus` with `400 after must be the id of a task of this project`. |
| `status` | a real filter. 18 total → 14 completed, 1 failed, 3 cancelled. `queued` and `running` return 0. |
| `status=bogus` | `400`, and the message names all five valid values. |
| `goal`, `metadata` | accepted and silently ignored. Both return all 18. |

Then the backward cursor:

```
GET /v1/tasks?limit=5&before=task_cf17fc31c9684822ace8141d270b0906
200  total=18  has_more=true  first_id=task_cf17fc31c9684822ace8141d270b0906
```

`task_cf17...` is the newest task. There is nothing before it, so a correct cursor returns
an empty page. Instead the response is byte-for-byte page one. The same happens with
`before=task_bogus`, which is accepted without validation and returns all 18 rows. `after`
on the same route validates its id and moves the window; `before` does neither.

A client that pages backwards with `before` gets page one, sees `has_more: true`, asks for
the page before page one, and gets page one again. It loops until something else stops it.

## Why it matters

The route itself is the good news: losing a task id is currently unrecoverable, and this
fixes that. The problem is that the route is invisible to anyone not using a Moss SDK, and
the one cursor that is broken is the one that fails silently. A `400` would have been
obvious during integration. An infinite loop in a reconciliation job is not.

## Fix

1. Document the route, its parameters, its response shape and the valid `status` values.
2. Implement `before`, or reject it with the same `400` that `after` gives. Accepting a
   parameter and ignoring it is the worst of the three options.
3. Reject unknown query parameters. `goal=test` returning the entire project looks like a
   filter that matched everything.
4. If the route is intentionally private, return `404` and keep it private. If it is public,
   it is part of the contract and belongs in the reference.

## Evidence

- `evidence/20261125T113850Z-listing3/` is the run with 18 tasks in the project. Probe `R`,
  checks `before_moves_backward`, `before_rejects_unknown_id`, `after_moves_forward`,
  `status_*`, `filter_*_ignored`.
- `evidence/20261125T112549Z-contract/` is the first sighting: an empty project, `200` where
  the probe expected `404`.
- `evidence/20261125T113737Z-listing2/` reproduces the `before` behaviour on a second run.
