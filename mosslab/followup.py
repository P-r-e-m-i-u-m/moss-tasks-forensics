"""Re-read finished tasks later and diff their cost.

`traffic_usd` is documented as possibly null for hours after a task ends, which
means `total_usd` at completion is provisional. This tool takes a baseline, then
writes a follow-up snapshot and prints what moved.

    python -m mosslab.followup --run evidence/20261125T101500Z-core
    ... later ...
    python -m mosslab.followup --run evidence/20261125T101500Z-core
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .client import Moss
from .run import ROOT, load_env


def _cost(task: dict) -> dict:
    usage = task.get("usage") or {}
    cost = usage.get("cost") or {}
    return {
        "cost_usd": usage.get("cost_usd"),
        "model_usd": cost.get("model_usd"),
        "browser_usd": cost.get("browser_usd"),
        "traffic_usd": cost.get("traffic_usd"),
        "total_usd": cost.get("total_usd"),
        "status": task.get("status"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Follow up on task costs")
    parser.add_argument("--run", required=True, help="evidence directory of a previous run")
    args = parser.parse_args(argv)

    load_env()
    run_dir = (ROOT / args.run).resolve()
    results_path = run_dir / "results.json"
    if not results_path.exists():
        raise SystemExit(f"no results.json in {run_dir}")

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    task_ids = sorted(
        {
            task_id
            for result in payload["results"]
            for task_id in result.get("task_ids", [])
            if task_id and task_id != "None"
        }
    )

    baseline_path = run_dir / "cost-baseline.json"
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    with Moss(run_dir, max_usd=0.0, max_tasks=0) as moss:
        current = {}
        for task_id in task_ids:
            reply = moss.task("followup", task_id)
            if reply.ok and isinstance(reply.body, dict):
                current[task_id] = _cost(reply.body)
            else:
                current[task_id] = {"status": f"http_{reply.status}", "error": reply.code}
            time.sleep(0.25)

    if not baseline_path.exists():
        baseline_path.write_text(
            json.dumps({"at": stamp, "tasks": current}, indent=2), encoding="utf-8"
        )
        print(f"baseline written for {len(current)} task(s): {baseline_path.name}")
        return 0

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))["tasks"]
    out = run_dir / f"cost-followup-{stamp}.json"
    out.write_text(json.dumps({"at": stamp, "tasks": current}, indent=2), encoding="utf-8")

    print(f"{'task':<38} {'before':>10} {'after':>10} {'delta':>10}  traffic")
    moved = 0
    for task_id, now in current.items():
        before = (baseline.get(task_id) or {}).get("total_usd") or 0.0
        after = now.get("total_usd") or 0.0
        delta = float(after) - float(before)
        if abs(delta) > 1e-9:
            moved += 1
        print(
            f"{task_id:<38} {float(before):>10.6f} {float(after):>10.6f} "
            f"{delta:>+10.6f}  {now.get('traffic_usd')}"
        )
    print(f"\n{moved} of {len(current)} task(s) changed cost after completion")
    print(f"written: {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
