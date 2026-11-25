"""Run selected probe suites and write the evidence bundle."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .client import BudgetExceeded, Moss
from .model import ProbeResult

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "evidence"


def load_env(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def registry() -> dict[str, list]:
    from .probes import SUITES

    return SUITES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Moss Tasks API evidence run")
    parser.add_argument(
        "--suites",
        default="contract",
        help="comma-separated: contract,idempotency,lifecycle,money,schema,failures,files,sdk",
    )
    parser.add_argument("--label", default="run", help="suffix for the evidence directory")
    parser.add_argument("--max-usd", type=float, default=float(os.environ.get("MOSS_MAX_USD", "3")))
    parser.add_argument("--max-tasks", type=int, default=int(os.environ.get("MOSS_MAX_TASKS", "40")))
    parser.add_argument("--interval", type=float, default=2.0, help="poll interval, seconds")
    parser.add_argument("--poll-timeout", type=float, default=300.0)
    parser.add_argument("--dry-run", action="store_true", help="list probes, send nothing")
    args = parser.parse_args(argv)

    load_env()
    suites = registry()
    wanted = [name.strip() for name in args.suites.split(",") if name.strip()]
    unknown = [name for name in wanted if name not in suites]
    if unknown:
        parser.error(f"unknown suite(s): {', '.join(unknown)}")

    if args.dry_run:
        for name in wanted:
            for probe in suites[name]:
                print(f"{probe.fn.__module__.split('.')[-1]:<12} {probe.id:<6} {probe.title}")
        return 0

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = EVIDENCE / f"{stamp}-{args.label}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results: list[ProbeResult] = []
    errors: list[dict[str, str]] = []

    with Moss(run_dir, max_usd=args.max_usd, max_tasks=args.max_tasks) as moss:
        print(f"run {run_dir.name}")
        print(f"gateway {moss.base}")
        print(f"ceiling ${moss.max_usd:.2f} / {moss.max_tasks} tasks\n")

        for suite in wanted:
            for probe in suites[suite]:
                print(f"  {probe.id:<6} {probe.title} ... ", end="", flush=True)
                started = time.perf_counter()
                try:
                    result = probe.fn(moss, args)
                except BudgetExceeded as exc:
                    result = ProbeResult(probe.id, suite, probe.title, skipped=f"budget: {exc}")
                except KeyboardInterrupt:
                    raise
                except Exception as exc:  # noqa: BLE001 - a probe crash is data, not a stop
                    errors.append({"probe": probe.id, "error": repr(exc)})
                    result = ProbeResult(probe.id, suite, probe.title, skipped=f"crashed: {exc!r}")
                took = time.perf_counter() - started
                results.append(result)
                if result.skipped:
                    print(f"skip ({result.skipped})")
                else:
                    print(f"{result.passed}/{len(result.checks)} checks, {took:.1f}s")

        budget = moss.budget()

    payload = {
        "run": run_dir.name,
        "started_utc": stamp,
        "finished_utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "gateway": os.environ.get("MOSS_INFERENCE_URL") or "https://inference.moss.dev/v1",
        "budget": budget,
        "results": [
            {
                "id": r.id,
                "suite": r.suite,
                "title": r.title,
                "skipped": r.skipped,
                "checks": [
                    {
                        "name": c.name,
                        "expected": c.expected,
                        "observed": c.observed,
                        "passed": c.passed,
                        "evidence": c.evidence,
                    }
                    for c in r.checks
                ],
                "notes": r.notes,
                "task_ids": r.task_ids,
            }
            for r in results
        ],
        "errors": errors,
    }
    (run_dir / "results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "summary.md").write_text(render(payload), encoding="utf-8")

    print(f"\nspent ${budget['spent_usd']:.4f} over {budget['tasks_created']} tasks")
    print(f"evidence: {run_dir.relative_to(ROOT)}")
    return 0 if not errors else 1


def render(payload: dict) -> str:
    lines = [
        f"# Run {payload['run']}",
        "",
        f"- gateway: `{payload['gateway']}`",
        f"- tasks created: {payload['budget']['tasks_created']}",
        f"- spend: ${payload['budget']['spent_usd']:.4f}",
        "",
        "| probe | checks | failed | skipped |",
        "|---|---|---|---|",
    ]
    for result in payload["results"]:
        checks = result["checks"]
        failed = sum(1 for c in checks if not c["passed"])
        lines.append(
            f"| {result['id']} {result['title']} | {len(checks)} | {failed} | {result['skipped'] or ''} |"
        )

    lines += ["", "## Detail", ""]
    for result in payload["results"]:
        if result["skipped"]:
            lines += [f"### {result['id']} — skipped", "", f"`{result['skipped']}`", ""]
            continue
        lines += [f"### {result['id']} — {result['title']}", ""]
        lines += ["| check | expected | observed | result |", "|---|---|---|---|"]
        for check in result["checks"]:
            mark = "pass" if check["passed"] else "**fail**"
            observed = check["observed"].replace("|", "\\|")[:220]
            expected = check["expected"].replace("|", "\\|")[:120]
            lines.append(f"| {check['name']} | {expected} | {observed} | {mark} |")
        for note in result["notes"]:
            lines += ["", f"> {note}"]
        if result["task_ids"]:
            lines += ["", f"tasks: {', '.join(f'`{t}`' for t in result['task_ids'])}"]
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
