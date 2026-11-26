# F10 — A mistyped index name returns `403 permission_error`, not `404`

**Severity:** S3 — the error sends the developer to the wrong problem
**Status:** confirmed
**Where:** `X-Moss-Indexes` on `POST /v1/responses`
**Request id:** `b1a4a9bb36be4a49a33da3f6fce8d234`

## Expected

The quickstart says to send the index as a header:

> With curl or an OpenAI client, send the header `X-Moss-Indexes: faq` instead of `indexes`.

If the name does not exist, the natural answer is `404 not_found_error` naming the index. If
it exists but belongs to another project, `403 permission_error` is correct.

## Observed

I sent an index name that does not exist:

```
POST /v1/responses
X-Moss-Indexes: index_that_does_not_exist_9f3c

403
{
  "error": {
    "message": "X-Moss-Indexes names an index outside this project",
    "type": "permission_error",
    "code": "permission_error",
    "request_id": "b1a4a9bb36be4a49a33da3f6fce8d234"
  }
}
```

The same request with `indexes` in the JSON body gets a much better error:

```
400
{
  "error": {
    "message": "indexes is not supported",
    "type": "invalid_request_error",
    "code": "unsupported_parameter",
    "request_id": "1aefd32e75f2411f885719bbd133e012"
  }
}
```

That one tells the caller exactly what to do: use the header. The header path does not.

## Why it matters

`403` means "authenticated, not allowed". A developer who mistypes `faq` as `fqa` will check
their project key, their role, their plan, and the index's sharing settings before they
check the spelling. The message says "outside this project", which implies the index exists
somewhere else — a small information leak, and a misleading one when the real cause is a
typo.

The body-field error shows the team knows how to write a precise message. The header path
should match it.

## Fix

Return `404 not_found_error` with `"no index named <name> in this project"` when the name is
unknown. Reserve `403` for an index that exists but is not readable by this project. If the
two cases are deliberately merged to prevent enumeration, say so in the docs and use a
neutral message such as `"index not available to this project"`, not one that asserts where
it lives.

## Evidence

- `evidence/20261125T113933Z-inference/`, probe `N3`, check `header_indexes_is_read`.
- The same run, probe `N2`, check `body_indexes_is_read`, for the contrasting body-field
  error.
- Docs: `docs/inference/quickstart.md`, the `X-Moss-Indexes` paragraph.
