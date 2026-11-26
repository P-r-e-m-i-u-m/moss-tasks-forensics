# F09 — A web failure ends `completed`, and `no_answer` never fires

**Severity:** S2 — a non-answer is indistinguishable from an answer
**Status:** confirmed on three deliberately broken goals
**Where:** `status` and `error.code` on a finished task
**Request ids:** `8d9d9c4a336e4805a08eb7f13a01d89f` (DNS),
`581f67306ef948f2858bfb8ad3df095f` (404 page),
`4de57c3690204debae8716017671cada` (nonexistent entity)

## Expected

The guide defines four failure codes, including:

> `no_answer` | The agent ended without an answer.

A task that cannot load its page, or cannot find the entity it was asked about, ended without
an answer. I expected `failed` with `no_answer`, or a structured error. At minimum I expected
a status that is not `completed`.

## Observed

All three tasks ended `completed` with `error: null` and `verification: {"method":
"agent_reported", "passed": null}`.

**DNS failure** (`https://moss-72231fe4.invalid`):

> I couldn't verify the page title because the URL failed to load. The browser showed
> `ERR_SOCKS_CONNECTION_FAILED`; its displayed title was `moss-72231fe4.invalid`, but that
> was on Chrome's error page.

The agent was honest. The status was `completed`.

**404 page** (`https://example.com/missing-72231fe4`):

> The page title is **Example Domain**.

The agent reported the title of the error page it landed on, without mentioning that the
requested URL was missing. Status `completed`.

**Nonexistent entity** ("find the direct phone number of the chief executive of Zorblax
Dynamics, a company that does not exist"):

> No verified direct phone number can be reported. DuckDuckGo found no results for the exact
> company name...

Status `completed`.

None of the four documented codes appeared. `no_answer` did not fire for an explicit "no
answer" response.

## Why it matters

`completed` currently means "the run ended", not "the goal was met". Any client that branches
on `status` — the obvious thing to do, and what the guide's status table encourages — treats
a refusal as a result. The only signal that the agent gave up is English prose inside
`result.output_text`, which is not machine-readable and varies with the model.

This is worse than an undocumented error code. With a code, a caller can at least log it and
branch. Here there is no code and no field; the caller has to parse the answer to discover
that there is no answer.

The 404 case is the quietest: the answer is factually true (the 404 page's title really is
"Example Domain") and completely useless for the question that was asked. Nothing in the
response says the page returned 404.

## Fix

1. Use `no_answer` when the agent's own conclusion is that it could not answer. The DNS
   output is a textbook case: the agent said it could not verify the title.
2. Add a structured result flag, for example `result.answer_found: false` or
   `verification.answered: false`, so a caller does not have to read prose.
3. For environment failures (DNS, TLS, connection refused), add a distinct code such as
   `environment_error` with `retryable: false`. The current advice, "anything else means
   create it again", would retry a permanently broken hostname forever.
4. If `completed` is deliberately kept for every terminal run, say so in the status table
   and document how to detect a non-answer. Right now the table says `completed` means the
   task finished, and the failure table implies a non-answer would be `failed`.

## Evidence

- `evidence/20261125T112920Z-deep/`, probe `F`, checks `dns_failure_terminal`,
  `page_404_terminal`, `no_such_entity_terminal`.
- Tasks `task_29bf2dff03e04c49a867973835b79009`, `task_17276736a27e43aab4490d462feeab40`,
  `task_2d8458a85f52427ba3bf5d2eeadb370b`.
- Docs: `docs/inference/tasks.md`, the error table; `docs/api-reference/v1/inference/tasks.md`,
  "A failed task has `error.code` ...".
