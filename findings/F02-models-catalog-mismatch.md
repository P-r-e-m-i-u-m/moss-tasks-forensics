# F02 — `/v1/models` is public, and none of its models can run a task

**Severity:** S3 — wrong answer to a question every client asks at startup
**Status:** confirmed
**Route:** `GET https://inference.moss.dev/v1/models`
**Request id:** `e144aebe9ea84644bc3fc987cc0dcb95`

## Expected

An authenticated list of the models this project can call. If the same endpoint is meant to
answer "what can I put in `model`?", it should include the models each product accepts.

## Observed

No `Authorization` header, `200 OK`, 19 models:

```
moss/fastlane-1            openai/gpt-6-luna          anthropic/claude-haiku-5.5
openai/gpt-6.1-terra       openai/gpt-6.1-sol         anthropic/claude-sonnet-5.5
openai/gpt-6-astra         anthropic/claude-opus-5.5  anthropic/claude-fable-5.1
google/gemini-3.8-flash    google/gemini-3.5-flash-lite  google/gemini-4-argon
z-ai/glm-5.3               moonshotai/kimi-k3         deepseek/deepseek-v4.1-flash
qwen/qwen3.8-flash         deepseek/deepseek-v4.1-flash-1017
z-ai/glm-5.3-flash         minimax/minimax-m3.1-flash
```

The only values `POST /v1/tasks` accepts for `model` are `moss-fast`, `moss-balanced` and
`moss-advanced`. **Zero** of them appear in this list. `moss-fastlane-1` is the closest name
and is an inference model, not a task model — a plausible-looking near-miss for anyone
guessing.

## Why it matters

Every OpenAI-compatible client starts by asking this endpoint. The OpenAI Python SDK, the
Vercel AI SDK, LiteLLM, LangChain and anything else that enumerates providers all call
`/models` to populate a dropdown or validate a config. A developer wiring Moss into one of
them gets 19 ids, picks one, and then gets a `400 model_not_found` from the Tasks API for
every choice the list offered.

The names also leak the vendor lineup before any authentication, which is a smaller version
of the same problem as F01.

## Two separate fixes, both small

1. Require auth on `/v1/models`, like every other `/v1` route.
2. Return the models that apply to the calling product, or add the task aliases to the list.
   If they are deliberately separate namespaces, say so in the response — a field like
   `"capabilities": ["tasks"]` would let a client filter instead of guess.

## Evidence

`evidence/20261125T111443Z-surface/wire.jsonl`, probe `P`, the `GET /v1/models` exchange.
`evidence/20261125T111443Z-surface/results.json`, checks `models_requires_auth` and
`models_lists_task_models`.
