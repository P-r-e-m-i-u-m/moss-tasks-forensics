"""Result types shared by the probes and the reporter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Check:
    """One falsifiable claim about observed behaviour."""

    name: str
    expected: str
    observed: str
    passed: bool
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProbeResult:
    id: str
    suite: str
    title: str
    checks: list[Check] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    task_ids: list[str] = field(default_factory=list)
    skipped: str | None = None

    def check(
        self,
        name: str,
        expected: str,
        observed: Any,
        passed: bool,
        **evidence: Any,
    ) -> None:
        self.checks.append(
            Check(
                name=name,
                expected=expected,
                observed=str(observed),
                passed=bool(passed),
                evidence=evidence,
            )
        )

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c.passed)


def brief(reply: Any) -> dict[str, Any]:
    """The parts of a response worth putting in a check's evidence."""
    return {
        "status": getattr(reply, "status", None),
        "code": getattr(reply, "code", None),
        "type": getattr(reply, "error_type", None),
        "message": getattr(reply, "message", ""),
        "request_id": getattr(reply, "request_id", None),
    }


def task_brief(task: dict[str, Any]) -> dict[str, Any]:
    """The parts of a task object worth keeping in results.json."""
    return {
        key: task.get(key)
        for key in (
            "id",
            "status",
            "model",
            "effort",
            "verification",
            "error",
            "cancel_requested",
            "trace_available",
            "live_url",
            "files_expire_at",
            "created_at",
            "started_at",
            "finished_at",
        )
        if key in task
    } | {"usage": task.get("usage"), "result": task.get("result")}
