# F08 — `verification.passed` means "the JSON fits the schema", not "the answer is right"

**Severity:** S3 — a success flag that a placeholder can earn
**Status:** confirmed; the original hypothesis was falsified and the real behaviour is narrower
**Where:** `verification` on a finished task with `output_schema`
**Request id:** `83660bd03c834b3d84116ba81339c11b`

## What I expected

Hypothesis H3 was: a task whose output fails its `output_schema` still ends `completed`,
and the only signal is `verification.passed: false`. The probe gave the agent a page with no
book on it and a schema requiring `isbn` and `author`, expecting the agent to miss the
schema.

## What actually happened

The agent returned:

```json
{"isbn": "Not found", "author": "Not found"}
```

Both values are strings. The schema required two strings. So the output *met* the schema,
and the task reported:

```json
"status": "completed",
"verification": {
  "method": "output_schema",
  "passed": true
}
```

No `problems` key at all. The hypothesis as written is false: this was not a schema miss.
The result is more interesting than the hypothesis. `passed: true` does not mean the agent
found a book. It means the JSON parsed and the types matched. A placeholder that satisfies
the shape is indistinguishable from a real answer.

## Why it matters

The field name and the docs invite the stronger reading. The reference says:

> `verification` | `{method, passed, problems}`. `passed` is `null` without `output_schema`.
> A task whose answer does not match still ends `completed`.

"A task whose answer does not match" sounds like a correctness check. In practice the only
thing being matched is the schema. For extraction tasks, the most common failure is not
malformed JSON — it is a field that was required but not present on the page, filled with
"Not found", "N/A", or an empty string. All of those pass.

`method: "output_schema"` is an honest hint, and it is the one thing that makes this
recoverable. A client that reads it can know what was checked. A client that reads only
`passed` cannot.

## Fix

1. Document `passed` as schema conformance in the field table, in those words. Keep the
   existing sentence about `completed`, but separate "the output did not validate" from
   "the answer was not correct".
2. Return `problems` on success too, even as an empty list, so the shape is stable.
3. Consider a second signal for extraction: `verification.answer_found` or a per-field
   `null`/`missing` count. A schema with `"type": "string"` cannot express "this value must
   come from the page".
4. If the product does intend semantic verification, say which method does it and how a
   caller selects it. Right now `method` has exactly two observed values,
   `output_schema` and `agent_reported`, and neither checks truth.

## Evidence

- `evidence/20261125T112920Z-deep/`, probe `V2`, checks `unsatisfiable_still_completes`,
  `unsatisfiable_fails_verification`, `verification_explains`. Task
  `task_ae0ee2f66ccb403394e3cff17c2c425a`.
- The same run, probe `V1`: a satisfiable schema returns `passed: true` and
  `result.output: {"title": "Example Domain"}`, which is the intended path.
- `findings/HYPOTHESES.md`, H3: the negative result is recorded there rather than dropped.
