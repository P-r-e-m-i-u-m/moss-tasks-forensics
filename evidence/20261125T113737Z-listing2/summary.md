# Run 20261125T113737Z-listing2

- gateway: `https://inference.moss.dev/v1`
- tasks created: 0
- spend: $0.0000

| probe | checks | failed | skipped |
|---|---|---|---|
| R The undocumented list route | 13 | 2 |  |

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
| filter_status | 400 unknown parameter, or a filtered result | 200 total=14 | pass |
| filter_goal | 400 unknown parameter, or a filtered result | 200 total=18 | pass |
| filter_metadata | 400 unknown parameter, or a filtered result | 200 total=18 | pass |
| pagination_walk | walking by after returns distinct ids and agrees with total | walked=6 total=18 distinct=6 | pass |

> `GET /v1/tasks` returns a paginated list. The reference documents create, get, cancel, files and file download — five routes. This is a sixth.

> `after` rejects an unknown task id; `before` accepts one and returns the first page. Two cursors on the same route, two different contracts.

> Whether the list is scoped to this project cannot be proven with one project. The `after` error message says 'of this project', which is the only evidence either way.
