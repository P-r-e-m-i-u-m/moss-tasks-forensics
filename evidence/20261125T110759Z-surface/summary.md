# Run 20261125T110759Z-surface

- gateway: `https://inference.moss.dev/v1`
- tasks created: 0
- spend: $0.0000

| probe | checks | failed | skipped |
|---|---|---|---|
| P Unauthenticated surface | 4 | 3 |  |

## Detail

### P — Unauthenticated surface

| check | expected | observed | result |
|---|---|---|---|
| models_requires_auth | 401 without a token | 200, 19 model(s) returned | **fail** |
| models_lists_task_models | the catalog includes the models a task accepts | 19 listed, 0 of ['moss-advanced', 'moss-balanced', 'moss-fast'] present | **fail** |
| health_requires_auth | 401, or a body with only a status field | 200, fields=['decide', 'decide_projects', 'indexes', 'models', 'projects', 'revision', 'traces'] | **fail** |
| error_request_id_matches_header | body.request_id == X-Moss-Request-Id | body='6d1552f4857c414ab0b2aa16c2fc07b0' header='6d1552f4857c414ab0b2aa16c2fc07b0' | pass |

> A caller who discovers models the OpenAI way (`GET /v1/models`) finds 19 ids and none of the three that `POST /v1/tasks` accepts. The task models are documented separately and never appear here.

> `/health` is outside `/v1`, needs no credentials, and returns 7 fields including the deployed revision and span counters. That is a free inventory of the deployment for anyone who guesses the path.
