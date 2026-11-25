"""Free checks before spending anything: credentials, route access, model list.

    python -m mosslab.preflight

Creates no tasks. If this fails, nothing downstream will work and the reason is
worth reading rather than guessing at.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .client import Moss
from .run import ROOT, load_env


def main() -> int:
    load_env()
    run_dir = ROOT / "evidence" / "_preflight"
    with Moss(run_dir, max_usd=0.0, max_tasks=0) as moss:
        print(f"gateway  {moss.base}")
        print(f"project  {moss.project_id[:6]}… ({len(moss.project_id)} chars)")
        print(f"key      {'same value as project id' if moss.project_key == moss.project_id else 'distinct'}")

        models = moss.request("preflight", "GET", "/models")
        if models.status == 401:
            print("\n401 authentication_error")
            print(f"  {models.message}")
            print(
                "\nThe header is `Authorization: Bearer <project_id>:<project_key>`.\n"
                "Both halves are needed and they are different values. Re-copy them from\n"
                "the project settings page in the portal."
            )
            return 1
        if models.status != 200:
            print(f"\nmodels: {models.status} {models.code or models.error_type}")
            print(f"  {models.message[:300]}")
            return 1

        data = (models.body or {}).get("data") or []
        print(f"models   {len(data)} served")
        for item in data[:6]:
            print(f"         {item.get('id')}")

        probe = moss.request("preflight", "GET", "/tasks/task_" + "0" * 32)
        print(f"tasks    GET unknown id -> {probe.status} {probe.code or probe.error_type or ''}")
        if probe.status == 403 and probe.code == "tasks_not_enabled":
            print("\nTasks are not enabled on this project. That is worth one line to Sri.")
            return 1
        if probe.status != 404:
            print(f"\nUnexpected: expected 404 not_found_error. {probe.message[:200]}")
            return 1

        print("\nready")
        return 0


if __name__ == "__main__":
    sys.exit(main())
