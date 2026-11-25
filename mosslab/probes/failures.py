"""F: what a failure looks like when the web, not the model, is the problem.

The reference lists four task error codes and says anything else means "create it
again". These probes stay inside that gap on purpose.
"""

from __future__ import annotations

import uuid

from ..client import Moss
from ..model import ProbeResult, task_brief
from . import common


def run(moss: Moss, args: object) -> ProbeResult:
    result = ProbeResult("F", "failures", "Failure taxonomy")
    interval = float(getattr(args, "interval", 2.0))
    run_id = uuid.uuid4().hex[:8]

    cases = [
        (
            "F1",
            "dns_failure",
            common.task(
                goal="Open the page and report its title.",
                environment={"type": "browser", "start_url": f"https://moss-{run_id}.invalid"},
            ),
        ),
        (
            "F2",
            "page_404",
            common.task(
                goal="Open the page and report its title.",
                environment={
                    "type": "browser",
                    "start_url": f"https://example.com/missing-{run_id}",
                },
            ),
        ),
        (
            "F3",
            "no_such_entity",
            common.task(
                goal=(
                    "Find the direct phone number of the chief executive of Zorblax Dynamics, "
                    "a company that does not exist. Report the number exactly."
                ),
                environment={"type": "browser"},
            ),
        ),
    ]

    for probe_id, name, payload in cases:
        created = moss.create(probe_id, payload)
        if created.status != 202 or not isinstance(created.body, dict):
            result.check(
                f"{name}_created",
                "202",
                f"{created.status} {created.code or created.error_type or ''}",
                False,
                message=created.message[:300],
                request_id=created.request_id,
            )
            continue
        task_id = str(created.body.get("id"))
        result.task_ids.append(task_id)
        run_obj = moss.poll(probe_id, task_id, timeout_s=180, interval=interval)
        task = run_obj.final
        error = task.get("error") or {}
        code = error.get("code")

        result.check(
            f"{name}_terminal",
            "ends, does not hang",
            f"{run_obj.status} after {len(run_obj.polls)} poll(s), ${run_obj.cost_usd:.4f}",
            run_obj.status in ("completed", "failed", "cancelled"),
            **task_brief(task),
        )
        if run_obj.status == "failed":
            documented = code in ("time_limit", "budget_exceeded", "no_answer", "provider_key_rejected")
            result.check(
                f"{name}_documented_code",
                "one of the four documented codes",
                f"{code}: {str(error.get('message'))[:160]}",
                documented,
                **task_brief(task),
            )
            if not documented:
                result.notes.append(
                    f"{name}: failed with undocumented code {code!r}. The docs say any other "
                    "failure means recreate the task, so a caller cannot tell a retryable "
                    "web failure from a permanent one."
                )
        else:
            result.notes.append(
                f"{name}: ended {run_obj.status} with no error; the agent answered around the "
                f"failure. output_text={str((task.get('result') or {}).get('output_text'))[:160]!r}"
            )

    return result
