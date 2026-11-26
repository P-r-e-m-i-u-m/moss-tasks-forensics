"""N: the Inference path, tested rather than read.

The Tasks API is the assignment's third question, but Inference is the product.
These are the cheapest calls that answer a real question:

- Does `POST /v1/responses` behave like the OpenAI Responses API it claims to be?
- The quickstart says to send `X-Moss-Indexes` as a header "instead of `indexes`".
  What happens to `indexes` in the body? Point both at an index that does not
  exist: if the field is read, the call fails; if it is ignored, it succeeds.
- Does the response carry the rate-limit headers the docs promise?
- Does streaming produce the documented event names?

Five short calls, `moss/fastlane-1`, no index. Cents at most.
"""

from __future__ import annotations

import json
import time

from ..client import Moss
from ..model import ProbeResult, brief

PROMPT = "Reply with the single word: ready"
MODEL = "moss/fastlane-1"
MISSING_INDEX = "index_that_does_not_exist_9f3c"


def run(moss: Moss, args: object) -> ProbeResult:
    result = ProbeResult("N", "inference", "Inference path and the indexes header")

    started = time.perf_counter()
    reply = moss.request(
        "N1",
        "POST",
        "/responses",
        body={"model": MODEL, "input": PROMPT, "max_output_tokens": 16},
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    body = reply.body if isinstance(reply.body, dict) else {}
    usage = body.get("usage") or {}

    result.check(
        "response_ok",
        "200 with an OpenAI-shaped object",
        f"{reply.status} object={body.get('object')!r} "
        f"output_text={str(body.get('output_text'))[:40]!r}",
        reply.status == 200 and body.get("object") == "response",
        **brief(reply),
        elapsed_ms=elapsed_ms,
    )
    result.check(
        "usage_tokens_present",
        "input and output token counts",
        f"in={usage.get('input_tokens')} out={usage.get('output_tokens')}",
        bool(usage.get("input_tokens")) and bool(usage.get("output_tokens")),
        usage=usage,
        request_id=reply.request_id,
    )
    rate_headers = {
        k: v for k, v in reply.headers.items() if k.startswith("x-ratelimit-")
    }
    result.check(
        "rate_limit_headers",
        "the x-ratelimit-* set the docs describe",
        f"{sorted(rate_headers)}",
        {"x-ratelimit-limit-requests", "x-ratelimit-remaining-requests"} <= set(rate_headers),
        headers=rate_headers,
        request_id=reply.request_id,
    )

    # `indexes` in the body, against an index that does not exist.
    body_indexes = moss.request(
        "N2",
        "POST",
        "/responses",
        body={"model": MODEL, "input": PROMPT, "indexes": [MISSING_INDEX], "max_output_tokens": 16},
    )
    result.check(
        "body_indexes_is_read",
        f"4xx, because {MISSING_INDEX} does not exist",
        f"{body_indexes.status} {body_indexes.code or body_indexes.error_type or ''}",
        400 <= body_indexes.status < 500,
        **brief(body_indexes),
    )
    if body_indexes.status == 200:
        result.notes.append(
            "`indexes` in the JSON body is accepted and ignored: the call succeeded while "
            "naming an index that does not exist. Grounding is header-only."
        )

    # The same index name, as the header the quickstart documents.
    header_indexes = moss.request(
        "N3",
        "POST",
        "/responses",
        body={"model": MODEL, "input": PROMPT, "max_output_tokens": 16},
        headers={"X-Moss-Indexes": MISSING_INDEX},
    )
    result.check(
        "header_indexes_is_read",
        f"4xx, because {MISSING_INDEX} does not exist",
        f"{header_indexes.status} {header_indexes.code or header_indexes.error_type or ''}",
        400 <= header_indexes.status < 500,
        **brief(header_indexes),
    )

    # An unknown model should be refused the same way it is on tasks.
    bad_model = moss.request(
        "N4", "POST", "/responses", body={"model": "moss-does-not-exist", "input": PROMPT}
    )
    result.check(
        "unknown_model_refused",
        "400 model_not_found",
        f"{bad_model.status} {bad_model.code or bad_model.error_type or ''}",
        bad_model.status == 400,
        **brief(bad_model),
    )

    # Streaming: does the documented event name arrive?
    events: list[str] = []
    first_delta = None
    with moss._http.stream(
        "POST",
        "/responses",
        json={"model": MODEL, "input": PROMPT, "stream": True, "max_output_tokens": 16},
        headers={
            "Authorization": f"Bearer {moss.project_id}:{moss.project_key}",
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        },
    ) as stream:
        for line in stream.iter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                events.append("[DONE]")
                break
            try:
                event = json.loads(payload)
            except ValueError:
                continue
            name = str(event.get("type"))
            if name not in events:
                events.append(name)
            if name == "response.output_text.delta" and first_delta is None:
                first_delta = event.get("delta")
            if len(events) > 12:
                break

    result.check(
        "stream_event_names",
        "response.output_text.delta among the events",
        f"{events[:8]}",
        "response.output_text.delta" in events,
        events=events[:12],
        first_delta=first_delta,
    )

    return result
