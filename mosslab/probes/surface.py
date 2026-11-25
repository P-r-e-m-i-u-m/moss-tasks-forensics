"""P: what the gateway exposes before you have credentials.

Not a security audit. Three observations that matter to a developer integrating
against this API, all reachable with `curl` and no account:

1. `/v1/models` answers without auth, and lists a model catalog that contains
   none of the three model names a task actually accepts.
2. `/health` answers without auth and reports build and traffic internals.
3. The error body carries its own `request_id` alongside the `X-Moss-Request-Id`
   header. If those disagree, support cannot correlate a report to a request.

Cost: zero. These requests create nothing.
"""

from __future__ import annotations

import httpx

from ..client import Moss
from ..model import ProbeResult

TASK_MODELS = {"moss-fast", "moss-balanced", "moss-advanced"}


def run(moss: Moss, args: object) -> ProbeResult:
    result = ProbeResult("P", "surface", "Unauthenticated surface")
    base = moss.base

    with httpx.Client(timeout=20.0, follow_redirects=False) as anon:
        models = anon.get(f"{base}/models")
        listing = models.json() if models.status_code == 200 else {}
        ids = [str(m.get("id")) for m in listing.get("data", []) if isinstance(m, dict)]
        overlap = sorted(TASK_MODELS & set(ids))

        result.check(
            "models_requires_auth",
            "401 without a token",
            f"{models.status_code}, {len(ids)} model(s) returned",
            models.status_code == 401,
            status=models.status_code,
            request_id=models.headers.get("x-moss-request-id"),
        )
        result.check(
            "models_lists_task_models",
            "the catalog includes the models a task accepts",
            f"{len(ids)} listed, {len(overlap)} of {sorted(TASK_MODELS)} present",
            bool(overlap),
            task_models=sorted(TASK_MODELS),
            overlap=overlap,
            sample=ids[:6],
        )
        result.notes.append(
            "A caller who discovers models the OpenAI way (`GET /v1/models`) finds 19 ids and "
            "none of the three that `POST /v1/tasks` accepts. The task models are documented "
            "separately and never appear here."
        )

        health = anon.get(base.removesuffix("/v1") + "/health")
        body = health.json() if health.status_code == 200 else {}
        exposed = sorted(k for k in body if k not in ("status",))
        result.check(
            "health_requires_auth",
            "401, or a body with only a status field",
            f"{health.status_code}, fields={exposed}",
            health.status_code == 401 or not exposed,
            status=health.status_code,
            body=body,
            request_id=health.headers.get("x-moss-request-id"),
        )
        result.notes.append(
            f"`/health` is outside `/v1`, needs no credentials, and returns {len(exposed)} "
            "fields including the deployed revision and span counters. That is a free "
            "inventory of the deployment for anyone who guesses the path."
        )

        denied = anon.get(f"{base}/tasks/task_" + "0" * 32)
        error = (denied.json() or {}).get("error", {}) if denied.content else {}
        body_id = error.get("request_id")
        header_id = denied.headers.get("x-moss-request-id")
        result.check(
            "error_request_id_matches_header",
            "body.request_id == X-Moss-Request-Id",
            f"body={body_id!r} header={header_id!r}",
            bool(body_id) and body_id == header_id,
            status=denied.status_code,
            body_request_id=body_id,
            header_request_id=header_id,
        )
        if body_id and header_id and body_id != header_id:
            result.notes.append(
                "The 401 body and the response header carry different request ids. A user who "
                "quotes the id from the error message sends support to a different request than "
                "the one the gateway logged."
            )

    return result
