"""D: what the SDK does that the wire does not, measured rather than assumed.

`tasks.run` hides the polling loop. The loop's shape matters: a twenty-minute task
polled every two seconds is six hundred requests, and none of them carry a hint
from the server about when to come back.
"""

from __future__ import annotations

import asyncio
import os
import time

from ..client import Moss
from ..model import ProbeResult, task_brief
from . import common


def run(moss: Moss, args: object) -> ProbeResult:
    result = ProbeResult("D", "sdk", "SDK polling behaviour")
    try:
        from moss import MossInference
    except Exception as exc:  # noqa: BLE001 - absence of the SDK is a skip, not a failure
        result.skipped = f"moss SDK not importable: {exc!r}"
        return result

    instance: dict[str, object] = {}

    async def exercise() -> None:
        client = MossInference(
            os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"]
        )
        counts: dict[str, int] = {}
        original = client._send

        async def counted(method: str, path: str, *a: object, **k: object):  # type: ignore[no-untyped-def]
            counts[method] = counts.get(method, 0) + 1
            return await original(method, path, *a, **k)

        client._send = counted  # type: ignore[method-assign]
        started = time.perf_counter()
        try:
            task = await client.tasks.run(
                goal="Open the page and report its title.",
                environment={"type": "browser", "start_url": common.START},
                model="moss-fast",
                limits={"max_runtime_seconds": 90, "max_cost_usd": 0.02},
                timeout=240,
            )
        finally:
            elapsed = time.perf_counter() - started
            instance.update(
                elapsed=elapsed,
                counts=counts,
                task=locals().get("task"),
                request_id=getattr(client.tasks, "_last_request_id", None),
            )
            await client.close()

    asyncio.run(exercise())
    task = instance.get("task")
    counts = instance.get("counts") or {}
    elapsed = float(instance.get("elapsed") or 0)

    if task is None:
        result.check("sdk_run_returned", "a task", "None", False)
        return result

    raw = getattr(task, "raw", {}) or {}
    result.task_ids.append(str(getattr(task, "id", "")))
    result.check(
        "sdk_run_returns_task",
        "completed",
        f"{getattr(task, 'status', None)} in {elapsed:.1f}s",
        getattr(task, "status", None) == "completed",
        **task_brief(raw),
    )
    result.check(
        "sdk_one_create",
        "exactly one POST",
        f"POST={counts.get('POST', 0)} GET={counts.get('GET', 0)}",
        counts.get("POST", 0) == 1,
        counts=counts,
    )

    polls = int(counts.get("GET", 0))
    expected = max(1, round(elapsed / 2.0))
    result.check(
        "sdk_poll_cadence",
        "roughly one GET per 2 s, fixed, no backoff",
        f"{polls} GET(s) in {elapsed:.1f}s, expected about {expected}",
        abs(polls - expected) <= 2,
        counts=counts,
        elapsed_s=round(elapsed, 1),
        polls=polls,
    )
    result.check(
        "sdk_surfaces_cost",
        "raw usage carries the cost block the SDK types do not",
        f"cost={((raw.get('usage') or {}).get('cost'))}",
        isinstance((raw.get("usage") or {}).get("cost"), dict),
        usage=raw.get("usage"),
    )

    result.notes.append(
        f"For a task of {elapsed:.0f}s the SDK spent {polls} requests on polling. "
        "At the documented 20-minute default on moss-advanced that is about 600 GETs, "
        "with no Retry-After or server hint to slow down. Polling is the client's whole "
        "integration surface and it is fixed at 2 s."
    )
    return result
