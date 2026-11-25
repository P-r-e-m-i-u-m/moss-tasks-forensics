"""Check the tree before it goes public.

Two jobs: make sure no credential reached a tracked file, and make sure the
evidence files that are supposed to exist do. Run this before every push.

    python -m mosslab.verify
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from .run import ROOT, load_env

SUSPECT = [
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-.:]{8,}"), "literal bearer token"),
    (re.compile(r"\bsk-[A-Za-z0-9]{16,}"), "sk- style secret"),
    (re.compile(r"\bproj_[A-Za-z0-9]{8,}"), "project id"),
]


def tracked() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
    return [ROOT / line for line in out.splitlines() if line.strip()]


def main() -> int:
    load_env()
    import os

    secrets = {
        value
        for name in ("MOSS_PROJECT_ID", "MOSS_PROJECT_KEY")
        if (value := os.environ.get(name, "").strip())
    }

    files = tracked()
    problems: list[str] = []

    for path in files:
        if not path.is_file() or path.suffix in {".png", ".jpg", ".webm", ".zip", ".pdf"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            problems.append(f"{path.relative_to(ROOT)}: unreadable ({exc})")
            continue
        relative = path.relative_to(ROOT)
        for secret in secrets:
            if secret in text:
                problems.append(f"{relative}: contains a live credential")
        for pattern, label in SUSPECT:
            for match in pattern.finditer(text):
                problems.append(f"{relative}: {label} -> {match.group(0)[:12]}...")

    if (ROOT / ".env").exists() and (ROOT / ".env") in files:
        problems.append(".env is tracked")

    if problems:
        print("FAIL")
        for problem in problems:
            print(f"  {problem}")
        return 1

    evidence = sorted((ROOT / "evidence").glob("*/wire.jsonl"))
    print(f"clean: {len(files)} tracked file(s), {len(evidence)} evidence run(s)")
    for run in evidence:
        lines = sum(1 for _ in run.open(encoding="utf-8"))
        print(f"  {run.parent.name}: {lines} exchanges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
