# Run 20261125T112814Z-core

- gateway: `https://inference.moss.dev/v1`
- tasks created: 11
- spend: $0.0052

| probe | checks | failed | skipped |
|---|---|---|---|
| R The undocumented list route | 13 | 2 |  |
| I Idempotency-Key semantics | 6 | 0 |  |
| L Task state machine and cancellation | 15 | 0 |  |

## Detail

### R — The undocumented list route

| check | expected | observed | result |
|---|---|---|---|
| list_route_exists | 404, since the reference documents no list route | 200, keys=['data', 'first_id', 'has_more', 'last_id', 'object', 'total'] | **fail** |
| list_shape | object="list" with data, first_id, last_id, has_more, total | ['data', 'first_id', 'has_more', 'last_id', 'object', 'total'] | pass |
| limit_1 | 200 | 200 | pass |
| limit_100 | 200 | 200 | pass |
| limit_0 | 400 | 400 invalid_request_error | pass |
| limit_101 | 400 | 400 invalid_request_error | pass |
| limit_abc | 400 | 400 invalid_request_error | pass |
| after_validated | 400 for an id that is not a task of this project | 400 after must be the id of a task of this project | pass |
| before_validated | 400, for the same reason as after | 200  | **fail** |
| filter_status | 400 unknown parameter, or a filtered result | 200 total=0 | pass |
| filter_goal | 400 unknown parameter, or a filtered result | 200 total=0 | pass |
| filter_metadata | 400 unknown parameter, or a filtered result | 200 total=0 | pass |
| pagination_walk | walking by after returns distinct ids and agrees with total | walked=0 total=0 distinct=0 | pass |

> `GET /v1/tasks` returns a paginated list. The reference documents create, get, cancel, files and file download — five routes. This is a sixth.

> `after` rejects an unknown task id; `before` accepts one and returns the first page. Two cursors on the same route, two different contracts.

> Whether the list is scoped to this project cannot be proven with one project. The `after` error message says 'of this project', which is the only evidence either way.

### I — Idempotency-Key semantics

| check | expected | observed | result |
|---|---|---|---|
| replay_same_body | same task id, Idempotent-Replayed: true | ids_match=True header='true' | pass |
| replay_reordered_keys | treated as the same body (same id) or refused with 422 | 202  ids_match=True | pass |
| replay_different_body | 422 idempotency_key_reused | 422 idempotency_key_reused | pass |
| replay_concurrent | one distinct task id | 1 distinct id(s) from 2 accepted request(s) | pass |
| key_length_255 | 202 | 202  | pass |
| key_length_256 | 400 | 400 invalid_request_error | pass |

> reordered-key result tells us whether equality is computed on JSON semantics or on raw bytes.

tasks: `task_0a847b767dd24af18d8b2e8f637d0795`, `task_7ee1f8e32bd64e958252a043a7275941`, `task_7ee1f8e32bd64e958252a043a7275941`, `task_37a995225f974e05b5e4b47b5fa66c91`, `task_36513f7d23514ba4ad3edfe823901f76`, `task_514689ce9fa848249b40a1a4b4f95cfb`

### L — Task state machine and cancellation

| check | expected | observed | result |
|---|---|---|---|
| create_status | 202 and a task id | 202 task_c506d2b1736e41b78fd5923c5e2a474e | pass |
| reaches_terminal | completed | completed after 17.3s over 8 poll(s) | pass |
| transitions_monotonic | queued -> running -> terminal, no regressions | running -> completed | pass |
| timestamps_ordered | created_at <= started_at <= finished_at | 2026-11-25T11:28:24.004189+00:00 / 2026-11-25T11:28:24.020033+00:00 / 2026-11-25T11:28:40.073418+00:00 | pass |
| trace_available_field | boolean on a finished task | True | pass |
| trace_route_after_finish | 200 with a step record | 200  keys=['final_result', 'screenshots', 'steps', 'timeline', 'video'] | pass |
| files_before_finish | 409 task_not_finished | 409 task_not_finished | pass |
| trace_before_finish | structured 4xx, not 5xx | 404 not_found_error | pass |
| cancel_queued | 200 and cancelled outright | 200 running | pass |
| queued_ends_cancelled | cancelled | cancelled | pass |
| cancel_running | 200, cancel_requested true or already cancelled | 200 status=running requested=True | pass |
| running_ends_cancelled | cancelled | cancelled | pass |
| cancel_completed | 200, status unchanged | 200 completed | pass |
| cancel_twice | idempotent | 200 completed | pass |
| cancel_unknown | 404 not_found_error | 404 not_found_error | pass |

> trace body keys: ['final_result', 'screenshots', 'steps', 'timeline', 'video']

tasks: `task_c506d2b1736e41b78fd5923c5e2a474e`, `task_13e3dfbedba947bc977226af2a337192`, `task_7a7f9355b51b496bac3755e61b27410c`
