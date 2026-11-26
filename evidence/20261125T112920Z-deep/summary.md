# Run 20261125T112920Z-deep

- gateway: `https://inference.moss.dev/v1`
- tasks created: 9
- spend: $0.0797

| probe | checks | failed | skipped |
|---|---|---|---|
| M Cost accounting and budget failure | 9 | 3 |  |
| V output_schema and verification | 7 | 2 |  |
| F Failure taxonomy | 3 | 0 |  |
| G Task files | 6 | 0 |  |
| D SDK polling behaviour | 4 | 0 |  |

## Detail

### M — Cost accounting and budget failure

| check | expected | observed | result |
|---|---|---|---|
| cost_block_present | usage.cost with model/browser/traffic/total | keys=['browser_usd', 'model_usd', 'total_usd', 'traffic_usd'] | pass |
| two_totals_agree | usage.cost_usd == usage.cost.total_usd | cost_usd=0.003755 total_usd=0.004088 | **fail** |
| traffic_settled_at_completion | traffic_usd is a number when the task is finished | traffic_usd=None | **fail** |
| browser_rounds_up_per_minute | ceil(12s/60) * $0.02/h | expected=0.000333333 billed=0.000333333 | pass |
| files_expire_in_seven_days | 7 days after finish | 7.000 days | pass |
| budget_exceeded_reported | failed with error.code budget_exceeded | completed None | **fail** |
| budget_respected | model spend at or below the cap | total=$0.0218 cap=$0.02 (browser billed separately) | pass |
| time_limit_reported | failed with error.code time_limit | failed time_limit | pass |
| time_limit_bills_work_done | usage still accounts for the spend | total=$0.0125 calls=15 | pass |

> M1: a cost part is null, so the sum cannot be checked: [0.003755, 0.0003333333333333333, None]

> traffic_usd is null at completion, so total_usd is not the final bill. Re-polling later is the only way to learn the real cost.

tasks: `task_10a6cb484c3a4b118e861d43b3accdbc`, `task_06eaf6816add4da49f8067075e9b7e7a`, `task_a43d4fdbe5ec4dddb89664c04cc875af`

### V — output_schema and verification

| check | expected | observed | result |
|---|---|---|---|
| satisfiable_completes | completed | completed | pass |
| satisfiable_passes | verification.passed true | passed=True method=output_schema | pass |
| satisfiable_output_object | result.output has the schema's shape | dict ['title'] | pass |
| unsatisfiable_still_completes | completed, per the docs | completed | pass |
| unsatisfiable_fails_verification | verification.passed false | passed=True method=output_schema | **fail** |
| verification_explains | problems is a non-empty list a caller can act on | 0 problem(s): [] | **fail** |
| malformed_schema_rejected_before_running | 400, no task created | 400 invalid_request_error | pass |

> A schema miss is a 202-shaped success: status=completed, exit code 0 for any client that checks status only. The only signal is verification.passed.

tasks: `task_5c69da2a9766490ea8e6a9e1c9d1ac9f`, `task_ae0ee2f66ccb403394e3cff17c2c425a`

### F — Failure taxonomy

| check | expected | observed | result |
|---|---|---|---|
| dns_failure_terminal | ends, does not hang | completed after 10 poll(s), $0.0045 | pass |
| page_404_terminal | ends, does not hang | completed after 7 poll(s), $0.0045 | pass |
| no_such_entity_terminal | ends, does not hang | completed after 18 poll(s), $0.0093 | pass |

> dns_failure: ended completed with no error; the agent answered around the failure. output_text='I couldn’t verify the page title because the URL failed to load. The browser showed `ERR_SOCKS_CONNECTION_FAILED`; its displayed title was `moss-72231fe4.invali'

> page_404: ended completed with no error; the agent answered around the failure. output_text='The page title is **Example Domain**.'

> no_such_entity: ended completed with no error; the agent answered around the failure. output_text='No verified direct phone number can be reported. DuckDuckGo found no results for the exact company name and no relevant information for the CEO-and-phone follow'

tasks: `task_29bf2dff03e04c49a867973835b79009`, `task_17276736a27e43aab4490d462feeab40`, `task_2d8458a85f52427ba3bf5d2eeadb370b`

### G — Task files

| check | expected | observed | result |
|---|---|---|---|
| list_shape | {object: "list", data: [{path, bytes}]} | 200 keys=['data', 'object'] | pass |
| files_present | at least one file after a finished task | 5 file(s) | pass |
| download | 200 with the listed byte count | 200 bytes=96 listed=96 | pass |
| download_nested_path | 200, same bytes | 200 bytes=96 | pass |
| missing_file | 404 not_found_error | 404 not_found_error | pass |
| encoded_traversal_refused | 4xx, not a file from outside the task directory | 404 not_found_error | pass |

tasks: `task_29dfe1d4eef24caf9267dc79b55ec323`

### D — SDK polling behaviour

| check | expected | observed | result |
|---|---|---|---|
| sdk_run_returns_task | completed | completed in 15.4s | pass |
| sdk_one_create | exactly one POST | POST=1 GET=6 | pass |
| sdk_poll_cadence | roughly one GET per 2 s, fixed, no backoff | 6 GET(s) in 15.4s, expected about 8 | pass |
| sdk_surfaces_cost | raw usage carries the cost block the SDK types do not | cost={'model_usd': 0.00361, 'total_usd': 0.003943, 'browser_usd': 0.0003333333333333333, 'traffic_usd': None} | pass |

> For a task of 15s the SDK spent 6 requests on polling. At the documented 20-minute default on moss-advanced that is about 600 GETs, with no Retry-After or server hint to slow down. Polling is the client's whole integration surface and it is fixed at 2 s.

tasks: `task_cf17fc31c9684822ace8141d270b0906`
