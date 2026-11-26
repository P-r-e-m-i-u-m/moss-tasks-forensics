# Run 20261125T113850Z-listing3

- gateway: `https://inference.moss.dev/v1`
- tasks created: 0
- spend: $0.0000

| probe | checks | failed | skipped |
|---|---|---|---|
| R The undocumented list route | 15 | 5 |  |

## Detail

### R — The undocumented list route

| check | expected | observed | result |
|---|---|---|---|
| list_route_exists | 404, since the reference documents no list route | 200, keys=['data', 'first_id', 'has_more', 'last_id', 'object', 'total'] | **fail** |
| list_shape | object="list" with data, first_id, last_id, has_more, total | ['data', 'first_id', 'has_more', 'last_id', 'object', 'total'] | pass |
| after_rejects_unknown_id | 400 | 400 after must be the id of a task of this project | pass |
| after_moves_forward | the next page, not the same one | first id task_29dfe1d4eef24caf9267dc79b55ec323 vs page-1 first task_cf17fc31c9684822ace8141d270b0906 | pass |
| before_moves_backward | a page older than the cursor, or an empty one | 5 row(s), identical_to_page1=True, has_more=True | **fail** |
| before_rejects_unknown_id | 400, for the same reason as after | 200  | **fail** |
| status_completed | 200 with a filtered total | 200 total=14 | pass |
| status_failed | 200 with a filtered total | 200 total=1 | pass |
| status_cancelled | 200 with a filtered total | 200 total=3 | pass |
| status_queued | 200 with a filtered total | 200 total=0 | pass |
| status_running | 200 with a filtered total | 200 total=0 | pass |
| status_bogus | 400 | 400 total=None | pass |
| status_total_consistent | the filtered totals sum to the unfiltered total | unfiltered=18 | pass |
| filter_goal_ignored | rejected as an unknown parameter, or honoured | 200 total=18 ignored=True | **fail** |
| filter_metadata_ignored | rejected as an unknown parameter, or honoured | 200 total=18 ignored=True | **fail** |

> `GET /v1/tasks` returns a paginated list. The reference documents create, get, cancel, files and file download — five routes. This is a sixth.

> `before` is accepted, never validated, and returns page one unchanged while `has_more` stays true. A client paging backwards with it loops on the same page forever. `after` on the same route works and is validated, so this is one cursor implemented and one accepted.

> `status` is a real filter with a real error message; `goal` and `metadata` are accepted and ignored, returning the whole project. Same route, two different attitudes to unknown input.
