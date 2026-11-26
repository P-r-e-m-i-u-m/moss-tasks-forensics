# Hypotheses, not findings

Nothing in this file is a claim. Each item is a specific question with a specific
test, written down before the test so the result cannot be rationalised afterwards.
Confirmed results move to a numbered `F` file with its evidence attached.

## H1 — `traffic_usd` arrives after the task ends

**Claim to test:** the cost block returned at `completed` is not the final bill.

The pricing page bills browser time, model tokens and traffic, but the Tasks reference
describes `usage.cost.traffic_usd` as possibly `null` for a while after a task ends. If that
is true, `total_usd` at completion understates the bill and the only way to learn the real
number is to re-poll hours later.

**Test:** `mosslab/followup.py` snapshots every finished task's cost, then re-reads the same
tasks after a delay and prints the delta per task.

**Falsified if:** no task's `total_usd` changes after completion.

## H2 — the cost fields disagree

**Claim to test:** `usage.cost_usd` and `usage.cost.total_usd` are the same number, or one of
them excludes traffic.

Two fields with the same meaning is a bug waiting to happen: whichever one a client reads
becomes "the cost", and two clients on the same task can report different bills.

**Test:** probe `M1` compares them on the same task and fails if they differ by more than
1e-9. It also checks that `model_usd + browser_usd + traffic_usd == total_usd`.

## H3 — a schema miss still looks like success

**Claim to test:** a task whose output fails its `output_schema` ends `completed`, not
`failed`, and the only signal is `verification.passed: false`.

**Test:** probe `V2` gives a page with no book on it and requires `isbn` and `author`. If it
ends `completed` with `passed: false`, then every client that branches on `status` treats a
useless answer as a success. The follow-up question is whether `verification.problems`
contains anything a caller can act on.

## H4 — a broken page does not produce a documented error code

**Claim to test:** the four documented codes (`time_limit`, `budget_exceeded`, `no_answer`,
`provider_key_rejected`) do not cover a DNS failure or a 404 page, and the resulting code is
not in the list. The docs say any other failure means "create it again", which is the wrong
instruction for a permanently broken URL.

**Test:** probes `F1`–`F3`. If the task instead completes with a hallucinated answer, that is
a more serious result than an undocumented code and will be reported as such.

## H5 — `max_cost_usd` does not cap the total

**Claim to test:** `limits.max_cost_usd` bounds model spend but not browser time, so a task
can cost more than its stated cap. The reference is ambiguous about whether the cap includes
the browser charge.

**Test:** probe `M2` sets a $0.02 cap on a task designed to run long, and compares the
returned `total_usd` to the cap. A `budget_exceeded` failure with a total above the cap
confirms it.

## H6 — `Idempotency-Key` equality is computed on bytes

**Claim to test:** the same key with the same JSON object in a different key order is treated
as a different body.

**Test:** probe `I2` sends the same object twice with reordered keys. A `422
idempotency_key_reused` means the comparison is on raw bytes and a client that serialises
dicts in a different order can never safely retry. A second task with a new id is worse: the
key silently failed to deduplicate.

## H7 — two concurrent creates with one key produce two tasks

**Claim to test:** the check-then-insert behind idempotency is not atomic.

**Test:** probe `I4` fires both requests from two threads and counts distinct ids. A single id
means the gateway locks correctly.

## H8 — `indexes` in the request body is silently ignored

**Claim to test:** the HTTP API reads `X-Moss-Indexes` and nothing else, so an OpenAI client
that puts `indexes` in the JSON body gets an ungrounded answer with no error.

The quickstart says to use the header instead of `indexes` and that without it "Moss does not
search before the model runs". It does not say what happens to an `indexes` body field.

**Test:** one `POST /v1/responses` with `indexes: ["<name>"]` in the body and no header,
against an index whose content is the only possible source of the answer. If the reply is
generic, the field was ignored. This is the one inference probe that spends money, so it runs
once, at `moss/fastlane-1`, with a short prompt.

## H9 — there is no way to list tasks

**Claim to test:** no `GET /v1/tasks` exists, so a client that loses a task id has no way to
recover it and no way to reconcile what it was billed for.

**Test:** probe `C` calls `GET /v1/tasks` and records the status. A `404` or `405` confirms
the gap; a `200` would be a documentation failure instead.

## H10 — resolved from source, kept for the record

**Claim tested:** the SDK's task retry set includes `409`, which the files routes use to mean
"the task has not finished".

**Result:** the implementation matches the changelog. `_TASK_RETRY_STATUSES = frozenset({408,
429})` (`inference.py:63`) and `_retry()` only adds a retry for `status >= 500`
(`inference.py:1838`), so a `409` is returned to the caller on the first attempt. No probe
needed. This is listed so the negative result is visible: not every question I asked found a
bug, and the ones that did not are not quietly dropped.

## Results

| # | outcome | where it went |
|---|---|---|
| H1 | **unresolved.** 14 minutes after the runs, `traffic_usd` was still `null` on all 18 tasks and no `total_usd` had changed. The docs say "a few hours", so this neither confirms nor falsifies settlement. | F06 |
| H2 | **confirmed.** `cost_usd` is model-only; `total_usd` adds the browser charge. | F06 |
| H3 | **falsified as written.** The output did not miss the schema: `"Not found"` is a valid string, so `passed` was `true`. The real finding is that `passed` is a shape check, not a correctness check. | F08 |
| H4 | **confirmed, with a different shape than expected.** No undocumented code appeared; the tasks ended `completed` with `error: null`. | F09 |
| H5 | **confirmed.** A $0.02 cap produced $0.021088 of model spend, `completed`, no `budget_exceeded`. | F07 |
| H6 | **falsified.** Reordered keys deduplicated to the same task id. Equality is computed on JSON semantics, not raw bytes. | — |
| H7 | **falsified.** Two concurrent creates with one key produced one task id. The check-then-insert is atomic enough. | — |
| H8 | **falsified.** `indexes` in the body is not ignored: it returns `400 unsupported_parameter` and tells the caller to use the header. | F10 |
| H9 | **falsified.** `GET /v1/tasks` exists and is paginated. It is a documentation gap, not a missing route. | F05 |
| H10 | **resolved from source.** A `409` is returned to the caller, not retried. | — |

The three clean falsifications (H6, H7, H8) are the parts of the API that held up best under
adversarial testing. H3 and H9 also failed as written, but each produced a finding rather than
a clean pass, so they are counted separately. All five are recorded here for the same reason
as the findings: a review that only lists defects is not measuring anything.
