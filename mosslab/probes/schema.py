"""V: output_schema, and what verification.passed actually promises.

The documented surprise is that a schema miss still ends `completed`. The useful
question is what a caller gets to detect it, and whether a malformed schema is
refused before a task is paid for.
"""

from __future__ import annotations

from ..client import Moss
from ..model import ProbeResult, task_brief
from . import common

SATISFIABLE = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
    "additionalProperties": False,
}

UNSATISFIABLE = {
    "type": "object",
    "properties": {
        "isbn": {"type": "string"},
        "author": {"type": "string"},
    },
    "required": ["isbn", "author"],
}

MALFORMED_BUT_VALID_JSON = {
    "type": "object",
    "properties": {"title": {"type": "nonsense"}},
    "required": ["title"],
}


def run(moss: Moss, args: object) -> ProbeResult:
    result = ProbeResult("V", "schema", "output_schema and verification")
    interval = float(getattr(args, "interval", 2.0))

    # V1: the schema can be met.
    ok_body = common.task(
        goal="Report the page title exactly as shown.",
        output_schema=SATISFIABLE,
    )
    created = moss.create("V1", ok_body)
    task_id = str((created.body or {}).get("id"))
    result.task_ids.append(task_id)
    run_obj = moss.poll("V1", task_id, timeout_s=240, interval=interval)
    task = run_obj.final
    verification = task.get("verification") or {}
    output = (task.get("result") or {}).get("output")

    result.check(
        "satisfiable_completes",
        "completed",
        run_obj.status,
        run_obj.status == "completed",
        **task_brief(task),
    )
    result.check(
        "satisfiable_passes",
        "verification.passed true",
        f"passed={verification.get('passed')} method={verification.get('method')}",
        verification.get("passed") is True,
        verification=verification,
    )
    result.check(
        "satisfiable_output_object",
        "result.output has the schema's shape",
        f"{type(output).__name__} {sorted(output) if isinstance(output, dict) else output!r}"[:200],
        isinstance(output, dict) and "title" in output,
        output=output,
    )

    # V2: the schema cannot be met on example.com.
    bad_body = common.task(
        goal="Report the ISBN and author of the book reviewed on this page.",
        output_schema=UNSATISFIABLE,
    )
    created_bad = moss.create("V2", bad_body)
    bad_id = str((created_bad.body or {}).get("id"))
    result.task_ids.append(bad_id)
    bad_run = moss.poll("V2", bad_id, timeout_s=240, interval=interval)
    bad_task = bad_run.final
    bad_verification = bad_task.get("verification") or {}

    result.check(
        "unsatisfiable_still_completes",
        "completed, per the docs",
        bad_run.status,
        bad_run.status == "completed",
        **task_brief(bad_task),
    )
    result.check(
        "unsatisfiable_fails_verification",
        "verification.passed false",
        f"passed={bad_verification.get('passed')} method={bad_verification.get('method')}",
        bad_verification.get("passed") is False,
        verification=bad_verification,
    )
    problems = bad_verification.get("problems") or []
    result.check(
        "verification_explains",
        "problems is a non-empty list a caller can act on",
        f"{len(problems)} problem(s): {str(problems)[:300]}",
        bool(problems),
        problems=problems,
    )
    result.notes.append(
        "A schema miss is a 202-shaped success: status=completed, exit code 0 for any client "
        "that checks status only. The only signal is verification.passed."
    )

    # V3: valid JSON, invalid JSON Schema. The reference does not say what happens.
    malformed = common.task(output_schema=MALFORMED_BUT_VALID_JSON)
    reply = moss.create("V3", malformed)
    result.check(
        "malformed_schema_rejected_before_running",
        "400, no task created",
        f"{reply.status} {reply.code or reply.error_type or ''}",
        reply.status == 400,
        status=reply.status,
        code=reply.code,
        type=reply.error_type,
        message=reply.message[:300],
        request_id=reply.request_id,
    )
    if reply.status == 202 and isinstance(reply.body, dict):
        task = reply.body
        result.task_ids.append(str(task.get("id")))
        result.notes.append(
            "malformed schema was accepted; the task ran and will be judged against a schema no "
            "validator can evaluate."
        )
        moss.cancel("V3", str(task.get("id")))

    return result
