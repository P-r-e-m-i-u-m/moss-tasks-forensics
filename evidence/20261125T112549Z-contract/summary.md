# Run 20261125T112549Z-contract

- gateway: `https://inference.moss.dev/v1`
- tasks created: 0
- spend: $0.0000

| probe | checks | failed | skipped |
|---|---|---|---|
| C Request validation and error shape | 16 | 1 |  |

## Detail

### C — Request validation and error shape

| check | expected | observed | result |
|---|---|---|---|
| unknown_field | 400 invalid_request_error | 400 invalid_request_error | pass |
| unknown_field_names_the_field | message names the offending field | named=True: Unknown field nope | pass |
| environment_type | 400 | 400 invalid_request_error | pass |
| effort_value | 400 | 400 invalid_request_error | pass |
| runtime_below_min | 400 | 400 invalid_request_error | pass |
| runtime_above_max | 400 | 400 invalid_request_error | pass |
| cost_below_min | 400 | 400 invalid_request_error | pass |
| cost_above_max | 400 | 400 invalid_request_error | pass |
| goal_over_20k | 400 | 400 invalid_request_error | pass |
| metadata_over_4k | 400 | 400 invalid_request_error | pass |
| schema_not_object | 400 | 400 invalid_request_error | pass |
| model_unknown | 400 model_not_found | 400 model_not_found | pass |
| environment_missing | 400 | 400 invalid_request_error | pass |
| body_over_256kib | 413 | 413 invalid_request_error | pass |
| list_route_absent | 404 or 405 (no list route is documented) | 200  | **fail** |
| unknown_task | 404 not_found_error | 404 not_found_error | pass |
