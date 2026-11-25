# F03 — An entire debugging surface exists in both SDKs and in no documentation

**Severity:** S2 — capability is shipped, paid for, and undiscoverable
**Status:** confirmed from source and from the published docs
**Surface:** `GET /v1/tasks/{id}/trace`, `task.trace_available`, `task.live_url`,
`environment.live_view`

## What I found

Both first-party SDKs implement a trace route and a live browser view:

| | Python `moss` | JavaScript `@moss-js/moss` |
|---|---|---|
| `tasks.trace(task_id)` | `inference.py:1249` | `inference/index.ts:268`, `:395` |
| `GET .../trace` | `inference.py:1265` | `inference/index.ts:396` |
| `trace_available` | `inference.py:429` | `types.ts:386` |
| `live_url` | `inference.py:430` | `types.ts:388` |
| `environment.live_view` | `inference.py:345` | `types.ts:295` |

The SDK changelog describes it plainly: *"`trace` returns the agent's record"*, and
`files_expire_at` is *"when the gateway removes the trace and files"*.

Now the documentation. I downloaded both pages and searched them:

```
docs/api-reference/v1/inference/tasks.md   ->  0 matches for trace|live_url|live_view
docs/inference/tasks.md                    ->  0 matches for trace|live_url|live_view
```

The API reference documents exactly five routes: create, get, cancel, list files, download
file. `/trace` is a sixth, and it is not there. Neither is the field that tells you whether
it is ready, nor the flag that turns on a live view of the running browser.

## Why it matters

The trace is the only way to see what the agent actually did — which pages it opened, what it
clicked, why it gave up. For a product whose selling point is an autonomous browser agent,
that is the difference between a debuggable tool and a black box. A task that ends `completed`
with `verification.passed: false` is close to undiagnosable without it.

A developer not using a Moss SDK — curl, Go, the OpenAI-compatible path, a workflow tool —
has no way to learn this route exists. The docs are the contract, and the contract omits the
feature. Even inside the SDKs, `trace_available` is a field nobody was told to check, so the
common pattern is `create` → poll → read `result` → never look at the trace.

`live_view` is worse in one respect: it is a *request* flag that presumably makes the gateway
expose a live browser URL. Nothing in the docs says it exists, what it costs, whether the URL
is authenticated, or how long it lives. I am not going to enable a feature whose access model
is undocumented without knowing who can reach the URL.

## Fix

Add `/tasks/{id}/trace` to the API reference with its response shape, its `409`/`404`/`410`
behaviour, and a sample body. Document `trace_available`, `live_url` and `live_view` on the
task and environment objects. If `live_url` is a bearer-style URL, say whether it is
authenticated and how long it stays valid — that is the first question anyone will ask before
putting it in a dashboard.

## Open question I could not answer from the docs

Whether `/trace` is billed, and whether it is included in the 7-day file window or has its own
retention. The SDK says `files_expire_at` covers it; the reference says nothing.

## Evidence

- `mosslab/probes/lifecycle.py`, probe `L7` calls `GET /tasks/{id}/trace` and records the raw
  response, including the case before the task finishes.
- Source references above are line numbers in the published files at `usemoss/moss@main`.
- Doc search is reproducible: fetch both pages, `Select-String -Pattern "trace|live_url|live_view"`.
