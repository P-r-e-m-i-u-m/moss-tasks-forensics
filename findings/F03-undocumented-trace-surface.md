# F03 — An entire debugging surface exists in both SDKs and in no documentation

**Severity:** S2 — capability is shipped, paid for, and undiscoverable
**Status:** confirmed from source and from the published docs
**Surface:** `GET /v1/tasks/{id}/trace`, `GET /v1/tasks/{id}/video`,
`GET /v1/tasks/{id}/video/{filename}`, `task.trace_available`, `task.video_available`,
`task.video_state`, `task.live_url`, `environment.live_view`

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
docs/api-reference/v1/inference/tasks.md   ->  0 matches for trace|live_url|live_view|video
docs/inference/tasks.md                    ->  0 matches for trace|live_url|live_view|video
```

The API reference documents exactly five routes: create, get, cancel, list files, download
file. `/trace` is a sixth, and it is not there. Neither is the field that tells you whether
it is ready, nor the flag that turns on a live view of the running browser.

## The video route is a third undocumented surface

The trace response includes a `video` field. On a task that has just finished it is `null`;
the task body says `video_state: "pending"`. Minutes later the same trace returns:

```json
"video": {
  "path": "session-1.mp4",
  "bytes": 97630,
  "started_at": "2026-11-25T11:29:20.061000+00:00"
}
```

The mp4 is not in `GET /tasks/{id}/files`, and `GET /tasks/{id}/files/session-1.mp4`
returns `404 No such file for this task`. It is served from a separate route:

```
GET /v1/tasks/{id}/video           -> {"url": "<signed GCS URL>", "expires_at": "..."}
GET /v1/tasks/{id}/video/session-1.mp4 -> 200 video/mp4
```

The signed URL expires in 15 minutes. The proxy route streams the same file. Neither route
appears in the reference, and neither SDK has a method for the video: the Python SDK exposes
`tasks.trace()` but no `tasks.video()`, and the JavaScript types do not mention `video` at
all. So the only way to discover a recording of the agent's browser session is to read the
trace response and guess the route.

The timing is also undocumented. On a 17-second task, `video_state` was `pending` at
completion and `ready` about eight minutes later. A client that polls the task until
`completed` and then reads the trace once will get `video: null` and no explanation.

## Why it matters

The trace is the only way to see what the agent actually did — which pages it opened, what it
clicked, why it gave up. For a product whose selling point is an autonomous browser agent,
that is the difference between a debuggable tool and a black box. A task that ends `completed`
with `verification.passed: false` is close to undiagnosable without it.

A developer not using a Moss SDK — curl, Go, the OpenAI-compatible path, a workflow tool —
has no way to learn this route exists. The docs are the contract, and the contract omits the
feature. Even inside the SDKs, `trace_available` is a field nobody was told to check, so the
common pattern is `create` → poll → read `result` → never look at the trace.

The video is the same problem one level deeper. It is the most persuasive artifact the
product produces — a replay of the agent working — and it is reachable only by guessing a
route that is not in the reference and not in either SDK.

`live_view` is worse in one respect: it is a *request* flag that presumably makes the gateway
expose a live browser URL. Nothing in the docs says it exists, what it costs, whether the URL
is authenticated, or how long it lives. I am not going to enable a feature whose access model
is undocumented without knowing who can reach the URL.

## Fix

Add the debugging surface to the API reference:

1. `GET /tasks/{id}/trace` with its response shape, its `404`/`409`/`410` behaviour, and a
   sample body. Document that `steps` is a count, `timeline` is the event list, and
   `screenshots` are paths under `/files`.
2. `GET /tasks/{id}/video` and `GET /tasks/{id}/video/{filename}`, including the signed URL,
   its 15-minute expiry, and the fact that the mp4 is not part of the `/files` listing.
3. `trace_available`, `video_available`, `video_state`, `live_url` and `live_view` on the task
   and environment objects, with the state transitions and the delay before the video is
   ready.
4. If `live_url` is a bearer-style URL, say whether it is authenticated and how long it stays
   valid. That is the first question anyone will ask before putting it in a dashboard.

## Open questions I could not answer from the docs

Whether `/trace` and `/video` are billed, and whether they share the 7-day file window or
have their own retention. The SDK says `files_expire_at` covers the trace; the reference says
nothing about either route.

## Evidence

- `mosslab/probes/lifecycle.py`, probe `L7` calls `GET /tasks/{id}/trace` and records the raw
  response, including the case before the task finishes.
- `evidence/20261125T112814Z-core/`, task `task_c506d2b1736e41b78fd5923c5e2a474e`: trace at
  completion has `video: null`; the same trace re-read at 11:37 has the populated video
  object; `video_state` on the task goes `pending` → `ready`.
- Live probes against `task_10a6cb484c3a4b118e861d43b3accdbc`: `/video` returns a signed URL
  with `expires_at` 15 minutes out; `/video/session-1.mp4` returns `200 video/mp4`; the same
  filename under `/files` returns `404`.
- Source references above are line numbers in the published files at `usemoss/moss@main`.
- Doc search is reproducible: fetch both pages, `Select-String -Pattern
  "trace|live_url|live_view|video"`.
