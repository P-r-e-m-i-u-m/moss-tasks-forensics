"""C: what the gateway accepts, what it refuses, and how it says so.

These requests are designed to fail validation, so most cost nothing. Anything the
gateway accepts by mistake is cancelled immediately and reported as an observation.
"""

from __future__ import annotations

import json

from ..client import Moss
from ..model import ProbeResult, brief
from . import common

RUNTIME_TOO_LOW = common.task(limits={"max_runtime_seconds": 59, "max_cost_usd": 0.02})
RUNTIME_TOO_HIGH = common.task(limits={"max_runtime_seconds": 7201, "max_cost_usd": 0.02})
COST_TOO_LOW = common.task(limits={"max_runtime_seconds": 90, "max_cost_usd": 0.009})
COST_TOO_HIGH = common.task(limits={"max_runtime_seconds": 90, "max_cost_usd": 50.01})
GOAL_TOO_LONG = common.task(goal="g" * 20_001)
SCHEMA_NOT_OBJECT = common.task(output_schema={"type": "string"})
SCHEMA_UNKNOWN_MODEL = common.task(model="moss-does-not-exist")
MISSING_ENVIRONMENT = {k: v for k, v in common.task().items() if k != "environment"}
UNKNOWN_FIELD = common.task(nope=1)
DESKTOP = common.task(environment={"type": "desktop"})
BAD_EFFORT = common.task(effort="extreme")
BAD_METADATA = common.task(metadata={"blob": "m" * 5_000})

# A body past the documented 256 KiB ceiling. There is no valid field long enough
# to build one, so this leans on unknown fields to reach the size.
BIG_BODY = common.task(**{f"pad_{i}": "p" * 8_000 for i in range(40)})

CASES = [
    ("unknown_field", UNKNOWN_FIELD, 400, "invalid_request_error"),
    ("environment_type", DESKTOP, 400, None),
    ("effort_value", BAD_EFFORT, 400, None),
    ("runtime_below_min", RUNTIME_TOO_LOW, 400, None),
    ("runtime_above_max", RUNTIME_TOO_HIGH, 400, None),
    ("cost_below_min", COST_TOO_LOW, 400, None),
    ("cost_above_max", COST_TOO_HIGH, 400, None),
    ("goal_over_20k", GOAL_TOO_LONG, 400, None),
    ("metadata_over_4k", BAD_METADATA, 400, None),
    ("schema_not_object", SCHEMA_NOT_OBJECT, 400, None),
    ("model_unknown", SCHEMA_UNKNOWN_MODEL, 400, "model_not_found"),
    ("environment_missing", MISSING_ENVIRONMENT, 400, None),
]

# The one case where the documented limits disagree with each other, so the
# expected answer is genuinely ambiguous.
BIG_BODY_EXPECTED = 413


def run(moss: Moss, args: object) -> ProbeResult:
    result = ProbeResult("C", "contract", "Request validation and error shape")
    created: list[str] = []

    for name, payload, expected_status, expected_code in CASES:
        reply = moss.request("C", "POST", "/tasks", body=payload)
        observed_code = reply.code or reply.error_type
        ok = reply.status == expected_status and (
            expected_code is None or reply.code == expected_code
        )
        result.check(
            name,
            f"{expected_status}" + (f" {expected_code}" if expected_code else ""),
            f"{reply.status} {observed_code or ''}",
            ok,
            **brief(reply),
            body_bytes=len(json.dumps(payload).encode()),
        )
        if reply.status == 202 and isinstance(reply.body, dict):
            task_id = str(reply.body.get("id"))
            created.append(task_id)
            moss.cancel("C", task_id)
            result.notes.append(
                f"{name}: accepted with 202 and cancelled ({task_id}); the limit is not enforced."
            )
        elif reply.status == 400 and name == "unknown_field":
            named = "nope" in reply.message
            result.check(
                "unknown_field_names_the_field",
                "message names the offending field",
                f"named={named}: {reply.message[:160]}",
                named,
                **brief(reply),
            )

    big = moss.request("C", "POST", "/tasks", body=BIG_BODY)
    result.check(
        "body_over_256kib",
        f"{BIG_BODY_EXPECTED}",
        f"{big.status} {big.code or big.error_type or ''}",
        big.status == BIG_BODY_EXPECTED,
        **brief(big),
        body_bytes=len(json.dumps(BIG_BODY).encode()),
        note="if 400, validation runs before the size check; the docs promise 413",
    )
    if big.status == 202 and isinstance(big.body, dict):
        created.append(str(big.body.get("id")))
        moss.cancel("C", str(big.body.get("id")))

    missing = moss.request("C", "GET", "/tasks")
    result.check(
        "list_route_absent",
        "404 or 405 (no list route is documented)",
        f"{missing.status} {missing.code or missing.error_type or ''}",
        missing.status in (404, 405),
        **brief(missing),
    )

    unknown_id = moss.request("C", "GET", "/tasks/task_00000000000000000000000000000000")
    result.check(
        "unknown_task",
        "404 not_found_error",
        f"{unknown_id.status} {unknown_id.code or unknown_id.error_type or ''}",
        unknown_id.status == 404,
        **brief(unknown_id),
    )

    result.task_ids = created
    return result
