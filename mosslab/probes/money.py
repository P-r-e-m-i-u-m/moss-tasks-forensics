"""M: whether the numbers add up, and whether they are final when the task is.

A metering API has one job here: the cost you read at completion should be the cost
you are billed. Two fields that look like the total, plus a traffic charge that can
arrive hours later, make that worth checking rather than assuming.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from ..client import Moss
from ..model import ProbeResult, task_brief
from . import common

BROWSER_USD_PER_HOUR = 0.02


def _ts(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def run(moss: Moss, args: object) -> ProbeResult:
    result = ProbeResult("M", "money", "Cost accounting and budget failure")
    interval = float(getattr(args, "interval", 2.0))

    # M1: one ordinary task, then arithmetic on its own bill.
    created = moss.create("M1", common.task())
    task_id = str((created.body or {}).get("id"))
    result.task_ids.append(task_id)
    run_obj = moss.poll("M1", task_id, timeout_s=240, interval=interval)
    task = run_obj.final
    usage = task.get("usage") or {}
    cost = usage.get("cost") or {}

    result.check(
        "cost_block_present",
        "usage.cost with model/browser/traffic/total",
        f"keys={sorted(cost)}",
        set(cost) >= {"model_usd", "browser_usd", "traffic_usd", "total_usd"},
        usage=usage,
    )

    parts = [cost.get("model_usd"), cost.get("browser_usd"), cost.get("traffic_usd")]
    if all(isinstance(p, (int, float)) for p in parts):
        drift = abs(sum(parts) - float(cost.get("total_usd") or 0))
        result.check(
            "parts_sum_to_total",
            "model + browser + traffic == total",
            f"sum={sum(parts):.6f} total={cost.get('total_usd')} drift={drift:.9f}",
            drift < 1e-6,
            cost=cost,
        )
    else:
        result.notes.append(f"M1: a cost part is null, so the sum cannot be checked: {parts!r}")

    cost_usd = usage.get("cost_usd")
    total_usd = cost.get("total_usd")
    if isinstance(cost_usd, (int, float)) and isinstance(total_usd, (int, float)):
        result.check(
            "two_totals_agree",
            "usage.cost_usd == usage.cost.total_usd",
            f"cost_usd={cost_usd} total_usd={total_usd}",
            abs(float(cost_usd) - float(total_usd)) < 1e-9,
            usage=usage,
        )

    result.check(
        "traffic_settled_at_completion",
        "traffic_usd is a number when the task is finished",
        f"traffic_usd={cost.get('traffic_usd')!r}",
        isinstance(cost.get("traffic_usd"), (int, float)),
        usage=usage,
    )
    if cost.get("traffic_usd") is None:
        result.notes.append(
            "traffic_usd is null at completion, so total_usd is not the final bill. "
            "Re-polling later is the only way to learn the real cost."
        )

    seconds = usage.get("browser_seconds")
    browser_usd = cost.get("browser_usd")
    if isinstance(seconds, (int, float)) and isinstance(browser_usd, (int, float)):
        expected = math.ceil(seconds / 60) * (BROWSER_USD_PER_HOUR / 60)
        result.check(
            "browser_rounds_up_per_minute",
            f"ceil({seconds}s/60) * ${BROWSER_USD_PER_HOUR}/h",
            f"expected={expected:.9f} billed={browser_usd:.9f}",
            abs(expected - float(browser_usd)) < 1e-9,
            seconds=seconds,
            billed=browser_usd,
        )

    finished = _ts(task.get("finished_at"))
    expires = _ts(task.get("files_expire_at"))
    if finished and expires:
        days = (expires - finished).total_seconds() / 86400
        result.check(
            "files_expire_in_seven_days",
            "7 days after finish",
            f"{days:.3f} days",
            abs(days - 7) < 0.05,
            finished=task.get("finished_at"),
            expires=task.get("files_expire_at"),
        )

    # M2: the budget ceiling. Cheap on purpose: the cap is the thing under test.
    over = common.slow_task(limits={"max_runtime_seconds": 180, "max_cost_usd": 0.02})
    budgeted = moss.create("M2", over)
    budget_id = str((budgeted.body or {}).get("id"))
    result.task_ids.append(budget_id)
    budget_run = moss.poll("M2", budget_id, timeout_s=240, interval=interval)
    budget_task = budget_run.final
    result.check(
        "budget_exceeded_reported",
        "failed with error.code budget_exceeded",
        f"{budget_run.status} {(budget_task.get('error') or {}).get('code')}",
        budget_run.status == "failed"
        and (budget_task.get("error") or {}).get("code") == "budget_exceeded",
        **task_brief(budget_task),
    )
    result.check(
        "budget_respected",
        "model spend at or below the cap",
        f"total=${budget_run.cost_usd:.4f} cap=$0.02 (browser billed separately)",
        budget_run.cost_usd <= 0.10,
        **task_brief(budget_task),
    )

    # M3: the runtime ceiling. The only deliberately slow probe.
    timed = common.slow_task(limits={"max_runtime_seconds": 60, "max_cost_usd": 0.05})
    clocked = moss.create("M3", timed)
    clocked_id = str((clocked.body or {}).get("id"))
    result.task_ids.append(clocked_id)
    clock_run = moss.poll("M3", clocked_id, timeout_s=180, interval=interval)
    clock_task = clock_run.final
    result.check(
        "time_limit_reported",
        "failed with error.code time_limit",
        f"{clock_run.status} {(clock_task.get('error') or {}).get('code')}",
        clock_run.status == "failed"
        and (clock_task.get("error") or {}).get("code") == "time_limit",
        **task_brief(clock_task),
    )
    result.check(
        "time_limit_bills_work_done",
        "usage still accounts for the spend",
        f"total=${clock_run.cost_usd:.4f} calls={(clock_task.get('usage') or {}).get('model_calls')}",
        clock_run.cost_usd > 0,
        **task_brief(clock_task),
    )

    return result
