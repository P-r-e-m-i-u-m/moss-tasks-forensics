"""L: status transitions, cancellation, and the trace surface the docs never mention."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from ..client import Moss
from ..model import ProbeResult, brief, task_brief
from . import common


def _ts(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _unique_in_order(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if not seen or seen[-1] != value:
            seen.append(value)
    return seen


def run(moss: Moss, args: object) -> ProbeResult:
    result = ProbeResult("L", "lifecycle", "Task state machine and cancellation")
    interval = float(getattr(args, "interval", 2.0))
    budget = float(getattr(args, "poll_timeout", 300.0))

    # L1: the normal path, timed.
    created = moss.create("L1", common.task())
    result.check(
        "create_status",
        "202 and a task id",
        f"{created.status} {(created.body or {}).get('id', '')}",
        created.status == 202 and bool((created.body or {}).get("id")),
        **brief(created),
    )
    task_id = str((created.body or {}).get("id"))
    result.task_ids.append(task_id)
    started = time.perf_counter()
    run_obj = moss.poll("L1", task_id, timeout_s=budget, interval=interval)
    wall = round(time.perf_counter() - started, 1)
    final = run_obj.final

    result.check(
        "reaches_terminal",
        "completed",
        f"{run_obj.status} after {wall}s over {len(run_obj.polls)} poll(s)",
        run_obj.status == "completed",
        **task_brief(final),
        polls=len(run_obj.polls),
        wall_s=wall,
    )

    transitions = _unique_in_order([p.status for p in run_obj.polls])
    allowed = {"queued": 0, "running": 1, "completed": 2, "failed": 2, "cancelled": 2}
    monotonic = all(
        allowed.get(a, -1) <= allowed.get(b, -1) for a, b in zip(transitions, transitions[1:])
    )
    result.check(
        "transitions_monotonic",
        "queued -> running -> terminal, no regressions",
        " -> ".join(transitions),
        monotonic,
        transitions=transitions,
    )

    created_at = _ts(final.get("created_at"))
    started_at = _ts(final.get("started_at"))
    finished_at = _ts(final.get("finished_at"))
    ordered = bool(created_at and finished_at and created_at <= finished_at) and (
        started_at is None or (created_at and created_at <= started_at <= finished_at)
    )
    result.check(
        "timestamps_ordered",
        "created_at <= started_at <= finished_at",
        f"{final.get('created_at')} / {final.get('started_at')} / {final.get('finished_at')}",
        ordered,
        **task_brief(final),
    )

    # L7: the trace route the SDK knows about and the reference does not document.
    trace_flag = final.get("trace_available")
    trace = moss.trace("L7", task_id)
    result.check(
        "trace_available_field",
        "boolean on a finished task",
        f"{trace_flag!r}",
        isinstance(trace_flag, bool),
        **task_brief(final),
    )
    result.check(
        "trace_route_after_finish",
        "200 with a step record",
        f"{trace.status} {trace.code or trace.error_type or ''} "
        f"keys={sorted(trace.body)[:8] if isinstance(trace.body, dict) else type(trace.body).__name__}",
        trace.status == 200,
        **brief(trace),
        body_keys=sorted(trace.body)[:20] if isinstance(trace.body, dict) else None,
    )
    if trace.status == 200 and isinstance(trace.body, dict):
        result.notes.append(f"trace body keys: {sorted(trace.body)}")

    # L2: files and trace before the task ends, then cancel a queued task.
    queued = moss.create("L2", common.task(goal="Wait ten seconds, then report the page title."))
    queued_id = str((queued.body or {}).get("id"))
    result.task_ids.append(queued_id)
    early_files = moss.files("L2", queued_id)
    early_trace = moss.trace("L2", queued_id)
    result.check(
        "files_before_finish",
        "409 task_not_finished",
        f"{early_files.status} {early_files.code or early_files.error_type or ''}",
        early_files.status == 409,
        **brief(early_files),
    )
    result.check(
        "trace_before_finish",
        "structured 4xx, not 5xx",
        f"{early_trace.status} {early_trace.code or early_trace.error_type or ''}",
        400 <= early_trace.status < 500,
        **brief(early_trace),
    )
    cancelled = moss.cancel("L2", queued_id)
    result.check(
        "cancel_queued",
        "200 and cancelled outright",
        f"{cancelled.status} {(cancelled.body or {}).get('status')}",
        cancelled.status == 200,
        **brief(cancelled),
        body=task_brief(cancelled.body or {}),
    )
    queued_end = moss.poll("L2", queued_id, timeout_s=60, interval=interval)
    result.check(
        "queued_ends_cancelled",
        "cancelled",
        queued_end.status,
        queued_end.status == "cancelled",
        **task_brief(queued_end.final),
    )

    # L3: cancel while running.
    running = moss.create("L3", common.slow_task())
    running_id = str((running.body or {}).get("id"))
    result.task_ids.append(running_id)
    saw_running = False
    for _ in range(30):
        reply = moss.task("L3", running_id)
        if reply.ok and (reply.body or {}).get("status") == "running":
            saw_running = True
            break
        if reply.ok and (reply.body or {}).get("status") in ("completed", "failed"):
            break
        time.sleep(interval)
    running_cancel = moss.cancel("L3", running_id)
    result.check(
        "cancel_running",
        "200, cancel_requested true or already cancelled",
        f"{running_cancel.status} status={(running_cancel.body or {}).get('status')} "
        f"requested={(running_cancel.body or {}).get('cancel_requested')}",
        running_cancel.status == 200,
        **brief(running_cancel),
        saw_running=saw_running,
    )
    running_end = moss.poll("L3", running_id, timeout_s=90, interval=interval)
    result.check(
        "running_ends_cancelled",
        "cancelled",
        running_end.status,
        running_end.status == "cancelled",
        **task_brief(running_end.final),
        saw_running=saw_running,
    )

    # L4/L5: cancelling something already finished is a no-op, twice.
    finished_cancel = moss.cancel("L4", task_id)
    result.check(
        "cancel_completed",
        "200, status unchanged",
        f"{finished_cancel.status} {(finished_cancel.body or {}).get('status')}",
        finished_cancel.status == 200
        and (finished_cancel.body or {}).get("status") == run_obj.status,
        **brief(finished_cancel),
    )
    again = moss.cancel("L5", task_id)
    result.check(
        "cancel_twice",
        "idempotent",
        f"{again.status} {(again.body or {}).get('status')}",
        again.status == 200,
        **brief(again),
    )

    # L6: unknown id.
    missing = moss.cancel("L6", "task_00000000000000000000000000000000")
    result.check(
        "cancel_unknown",
        "404 not_found_error",
        f"{missing.status} {missing.code or missing.error_type or ''}",
        missing.status == 404,
        **brief(missing),
    )

    return result
