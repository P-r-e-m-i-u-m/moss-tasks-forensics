# Run 20261125T113933Z-inference

- gateway: `https://inference.moss.dev/v1`
- tasks created: 0
- spend: $0.0000

| probe | checks | failed | skipped |
|---|---|---|---|
| N Inference path and the indexes header | 7 | 0 |  |

## Detail

### N — Inference path and the indexes header

| check | expected | observed | result |
|---|---|---|---|
| response_ok | 200 with an OpenAI-shaped object | 200 object='response' output_text='None' | pass |
| usage_tokens_present | input and output token counts | in=94 out=2 | pass |
| rate_limit_headers | the x-ratelimit-* set the docs describe | ['x-ratelimit-limit-requests', 'x-ratelimit-limit-tokens', 'x-ratelimit-remaining-requests', 'x-ratelimit-remaining-tokens', 'x-ratelimit-reset-requests', 'x-ratelimit-reset-tokens'] | pass |
| body_indexes_is_read | 4xx, because index_that_does_not_exist_9f3c does not exist | 400 unsupported_parameter | pass |
| header_indexes_is_read | 4xx, because index_that_does_not_exist_9f3c does not exist | 403 permission_error | pass |
| unknown_model_refused | 400 model_not_found | 400 model_not_found | pass |
| stream_event_names | response.output_text.delta among the events | ['response.created', 'response.in_progress', 'response.output_item.added', 'response.content_part.added', 'response.output_text.delta', 'response.output_text.done', 'response.content_part.done', 'response.output_item.don | pass |
