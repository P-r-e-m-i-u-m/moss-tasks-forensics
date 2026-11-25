"""Harness self-test. No network, no credentials, no spend.

The one thing that must not fail is redaction: if the project key reaches
wire.jsonl, the evidence bundle is unsafe to publish. This exercises the write
path with a fake transport and then reads the file back.

    python tests/test_harness.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

os.environ["MOSS_PROJECT_ID"] = "proj_test_0123456789"
os.environ["MOSS_PROJECT_KEY"] = "sk_test_secret_abcdefghijklmnop"

from mosslab.client import Moss  # noqa: E402


def handler(request: httpx.Request) -> httpx.Response:
    assert request.headers["authorization"].startswith("Bearer proj_test_")
    return httpx.Response(
        202,
        json={
            "id": "task_" + "a" * 32,
            "object": "task",
            "status": "queued",
            "goal": "probe",
            "usage": {"cost": {"total_usd": 0.001}},
        },
        headers={"x-moss-request-id": "req_test"},
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        with Moss(run_dir, transport=httpx.MockTransport(handler)) as moss:
            reply = moss.create("T1", {"goal": "probe"}, key="idem-1")
            assert reply.status == 202, reply.status
            assert reply.request_id == "req_test"
            assert reply.body["id"].startswith("task_")
            moss.account(reply.body)

        raw = (run_dir / "wire.jsonl").read_text(encoding="utf-8")
        assert "sk_test_secret" not in raw, "project key reached disk"
        assert "proj_test_0123" not in raw, "project id reached disk"

        record = json.loads(raw.splitlines()[0])
        assert "authorization" not in {k.lower() for k in record["request"]["headers"]}
        assert record["probe"] == "T1"
        assert record["request"]["headers"]["Idempotency-Key"] == "idem-1"
        assert record["response"]["status"] == 202
        assert moss.spent_usd == 0.001

    print("harness ok: redaction, evidence record, cost accounting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
