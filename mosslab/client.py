"""Thin HTTP client for the Moss Tasks API, with an evidence trail.

Every exchange is appended to `wire.jsonl` before the result is interpreted, so a
finding can be checked without trusting the probe that reported it. The client is
deliberately dumb: no retries, no backoff, no SDK. The SDK is tested separately,
because it hides the headers this work is about.

Credentials are scrubbed from the record at write time, not at commit time. A
secret that never reaches disk cannot leak through a forgotten `.gitignore`.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE = "https://inference.moss.dev/v1"
TERMINAL = ("completed", "failed", "cancelled")


class BudgetExceeded(RuntimeError):
    """Raised before a create that would cross the run's dollar ceiling."""


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            f"{name} is not set. Copy .env.example to .env and fill it in, "
            "or export it in the shell."
        )
    return value


@dataclass(frozen=True)
class Resp:
    """One HTTP exchange, after parsing."""

    status: int
    body: Any
    headers: dict[str, str]
    request_id: str | None
    elapsed_ms: float
    text: str
    content: bytes = b""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def error(self) -> dict[str, Any]:
        if isinstance(self.body, dict) and isinstance(self.body.get("error"), dict):
            return self.body["error"]
        return {}

    @property
    def code(self) -> str | None:
        return self.error.get("code")

    @property
    def error_type(self) -> str | None:
        return self.error.get("type")

    @property
    def message(self) -> str:
        return str(self.error.get("message", ""))

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())


@dataclass
class Poll:
    """One observation of a task, for transition timing."""

    at: float
    status: str
    cancel_requested: bool
    usage: dict[str, Any]
    request_id: str | None


@dataclass
class Run:
    """A task observed from creation to a terminal state."""

    task_id: str
    created: dict[str, Any]
    polls: list[Poll] = field(default_factory=list)
    final: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return str(self.final.get("status") or (self.polls[-1].status if self.polls else ""))

    @property
    def cost_usd(self) -> float:
        usage = self.final.get("usage") or {}
        cost = usage.get("cost") or {}
        return float(cost.get("total_usd") or usage.get("cost_usd") or 0.0)

    @property
    def elapsed_s(self) -> float:
        if not self.polls:
            return 0.0
        return self.polls[-1].at - self.polls[0].at


class Moss:
    """A raw client. One instance per run directory."""

    def __init__(
        self,
        run_dir: Path,
        *,
        base: str | None = None,
        max_usd: float = 3.0,
        max_tasks: int = 40,
        timeout: float = 120.0,
    ) -> None:
        self.project_id = _env("MOSS_PROJECT_ID")
        self.project_key = _env("MOSS_PROJECT_KEY")
        if ":" in self.project_id:
            raise SystemExit("MOSS_PROJECT_ID looks wrong: it must not contain ':'.")
        self.base = (base or os.environ.get("MOSS_INFERENCE_URL") or DEFAULT_BASE).rstrip("/")
        self.max_usd = max_usd
        self.max_tasks = max_tasks
        self.spent_usd = 0.0
        self.created = 0
        self.run_dir = run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        self._wire_path = run_dir / "wire.jsonl"
        self._wire = self._wire_path.open("a", encoding="utf-8")
        self._lock = threading.Lock()
        self._seq = 0
        self._cost_by_task: dict[str, float] = {}
        self._http = httpx.Client(
            base_url=self.base,
            timeout=httpx.Timeout(timeout, connect=10.0),
            follow_redirects=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        self._http.close()
        self._wire.close()

    def __enter__(self) -> "Moss":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- redaction ---------------------------------------------------------

    def _scrub(self, text: str) -> str:
        text = text.replace(self.project_key, "<MOSS_PROJECT_KEY>")
        text = text.replace(self.project_id, "<MOSS_PROJECT_ID>")
        return text

    # -- transport ---------------------------------------------------------

    def request(
        self,
        probe: str,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        accept: str = "application/json",
    ) -> Resp:
        sent = {"Accept": accept}
        if body is not None:
            sent["Content-Type"] = "application/json"
        sent.update(headers or {})
        sent["Authorization"] = f"Bearer {self.project_id}:{self.project_key}"

        started = time.perf_counter()
        try:
            reply = self._http.request(method, path, json=body, headers=sent)
            elapsed_ms = (time.perf_counter() - started) * 1000
            text = reply.text
            try:
                parsed: Any = reply.json()
            except ValueError:
                parsed = None
            result = Resp(
                status=reply.status_code,
                body=parsed,
                headers={k.lower(): v for k, v in reply.headers.items()},
                request_id=reply.headers.get("x-moss-request-id"),
                elapsed_ms=round(elapsed_ms, 1),
                text=text,
                content=reply.content,
            )
        except httpx.HTTPError as error:
            elapsed_ms = (time.perf_counter() - started) * 1000
            result = Resp(
                status=0,
                body={"error": {"type": "transport_error", "code": "transport", "message": repr(error)}},
                headers={},
                request_id=None,
                elapsed_ms=round(elapsed_ms, 1),
                text="",
            )

        self._record(
            probe=probe,
            method=method,
            path=path,
            body=body,
            headers=sent,
            result=result,
        )
        return result

    def _record(
        self,
        *,
        probe: str,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        headers: dict[str, str],
        result: Resp,
    ) -> None:
        with self._lock:
            self._seq += 1
            record = {
                "seq": self._seq,
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "probe": probe,
                "request": {
                    "method": method,
                    "url": self.base + path,
                    "headers": {k: v for k, v in headers.items() if k.lower() != "authorization"},
                    "body": body,
                },
                "response": {
                    "status": result.status,
                    "headers": result.headers,
                    "body": result.body,
                    "bytes": len(result.content),
                },
                "elapsed_ms": result.elapsed_ms,
                "request_id": result.request_id,
            }
            line = json.dumps(record, ensure_ascii=False, default=str)
            self._wire.write(self._scrub(line) + "\n")
            self._wire.flush()

    # -- tasks -------------------------------------------------------------

    def create(self, probe: str, payload: dict[str, Any], *, key: str | None = None) -> Resp:
        """Create a task, after checking the run budget."""
        if self.created >= self.max_tasks:
            raise BudgetExceeded(f"task ceiling reached ({self.max_tasks})")
        if self.spent_usd >= self.max_usd:
            raise BudgetExceeded(f"dollar ceiling reached (${self.spent_usd:.3f})")
        headers = {"Idempotency-Key": key} if key else None
        reply = self.request(probe, "POST", "/tasks", body=payload, headers=headers)
        if reply.status == 202:
            self.created += 1
        return reply

    def task(self, probe: str, task_id: str) -> Resp:
        return self.request(probe, "GET", f"/tasks/{task_id}")

    def cancel(self, probe: str, task_id: str) -> Resp:
        return self.request(probe, "POST", f"/tasks/{task_id}/cancel")

    def files(self, probe: str, task_id: str) -> Resp:
        return self.request(probe, "GET", f"/tasks/{task_id}/files")

    def trace(self, probe: str, task_id: str) -> Resp:
        return self.request(probe, "GET", f"/tasks/{task_id}/trace")

    def poll(
        self,
        probe: str,
        task_id: str,
        *,
        timeout_s: float = 300.0,
        interval: float = 2.0,
    ) -> Run:
        """Poll until terminal. Records every observation, including the boring ones."""
        started = time.perf_counter()
        run = Run(task_id=task_id, created={})
        while True:
            reply = self.task(probe, task_id)
            now = time.perf_counter()
            if reply.ok and isinstance(reply.body, dict):
                body = reply.body
                run.polls.append(
                    Poll(
                        at=now,
                        status=str(body.get("status")),
                        cancel_requested=bool(body.get("cancel_requested")),
                        usage=body.get("usage") or {},
                        request_id=reply.request_id,
                    )
                )
                if body.get("status") in TERMINAL:
                    run.final = body
                    self.account(body)
                    return run
            elif reply.status == 404:
                run.final = {"status": "not_found", "error": reply.error}
                return run
            if now - started > timeout_s:
                run.final = {"status": "poll_timeout", "polls": len(run.polls)}
                return run
            time.sleep(interval)

    def account(self, task: dict[str, Any]) -> None:
        """Add a task's billable cost once, so the run total never double-counts."""
        task_id = str(task.get("id") or "")
        usage = task.get("usage") or {}
        cost = usage.get("cost") or {}
        total = float(cost.get("total_usd") or usage.get("cost_usd") or 0.0)
        if not task_id:
            return
        previous = self._cost_by_task.get(task_id, 0.0)
        if total > previous:
            self.spent_usd += total - previous
            self._cost_by_task[task_id] = total

    def budget(self) -> dict[str, Any]:
        return {
            "spent_usd": round(self.spent_usd, 6),
            "tasks_created": self.created,
            "ceiling_usd": self.max_usd,
            "task_ceiling": self.max_tasks,
        }
