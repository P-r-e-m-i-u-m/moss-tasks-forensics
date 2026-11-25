"""P: what the gateway exposes before you have credentials.

Not a security audit. Three observations that matter to a developer integrating
against this API, all reachable with `curl` and no account:

1. `/v1/models` answers without auth, and lists a model catalog that contains
   none of the three model names a task actually accepts.
2. `/health` answers without auth and reports build and traffic internals.
3. The error body carries its own `request_id` alongside the `X-Moss-Request-Id`
   header. If those disagree, support cannot correlate a report to a request.

Cost: zero. These requests create nothing. They are sent through the same client
so they land in `wire.jsonl` like everything else.
"""

from __future__ import annotations

from ..client import Moss
from ..model import ProbeResult

TASK_MODELS = {"moss-fast", "moss-balanced", "moss-advanced"}


def run(moss: Moss, args: object) -> ProbeResult:
    result = ProbeResult("P", "surface", "Unauthenticated surface")

    # /v1/models with no Authorization header at all.
    models = moss.request("P", "GET", "/models", auth=False)
    listing = models.body if models.status == 200 and isinstance(models.body, dict) else {}
    ids = [str(m.get("id")) for m in listing.get("data", []) if isinstance(m, dict)]
    overlap = sorted(TASK_MODELS & set(ids))

    result.check(
        "models_requires_auth",
        "401 without a token",
        f"{models.status}, {len(ids)} model(s) returned",
        models.status == 401,
        status=models.status,
        request_id=models.request_id,
        count=len(ids),
    )
    result.check(
        "models_lists_task_models",
        "the catalog includes the models a task accepts",
        f"{len(ids)} listed, {len(overlap)} of {sorted(TASK_MODELS)} present",
        bool(overlap),
        task_models=sorted(TASK_MODELS),
        overlap=overlap,
        sample=ids[:6],
        request_id=models.request_id,
    )
    result.notes.append(
        "A caller who discovers models the OpenAI way (`GET /v1/models`) finds 19 ids and "
        "none of the three that `POST /v1/tasks` accepts. The task models are documented "
        "separately and never appear here."
    )

    # /health sits outside /v1 and takes no credentials.
    health_url = moss.base.removesuffix("/v1") + "/health"
    health = moss.request("P", "GET", health_url, auth=False)
    body = health.body if health.status == 200 and isinstance(health.body, dict) else {}
    exposed = sorted(k for k in body if k != "status")
    result.check(
        "health_requires_auth",
        "401, or a body with only a status field",
        f"{health.status}, fields={exposed}",
        health.status == 401 or not exposed,
        status=health.status,
        fields=exposed,
        revision=body.get("revision"),
        request_id=health.request_id,
    )
    result.notes.append(
        f"`/health` needs no credentials and returns {len(exposed)} fields including the "
        "deployed revision and live span counters. That is a free inventory of the "
        "deployment for anyone who guesses the path."
    )

    # Does the id in the error body match the one in the header?
    denied = moss.request("P", "GET", "/tasks/task_" + "0" * 32, auth=False)
    error = (denied.body or {}).get("error", {}) if isinstance(denied.body, dict) else {}
    body_id = error.get("request_id")
    header_id = denied.request_id
    result.check(
        "error_request_id_matches_header",
        "body.request_id == X-Moss-Request-Id",
        f"body={body_id!r} header={header_id!r}",
        bool(body_id) and body_id == header_id,
        status=denied.status,
        body_request_id=body_id,
        header_request_id=header_id,
    )

    return result
