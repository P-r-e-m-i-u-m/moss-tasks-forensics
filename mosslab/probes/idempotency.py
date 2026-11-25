"""I: what Idempotency-Key actually guarantees.

The interesting question is not whether replay works on the happy path. It is what
"the same body" means, and what happens when two requests arrive at once.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

from ..client import Moss
from ..model import ProbeResult, brief
from . import common


def _reordered(payload: dict) -> dict:
    """Same JSON object, different key order. A hash of the bytes would notice."""
    return dict(reversed(list(payload.items())))


def run(moss: Moss, args: object) -> ProbeResult:
    result = ProbeResult("I", "idempotency", "Idempotency-Key semantics")
    payload = common.task()

    # I1: replay, same bytes.
    key = str(uuid.uuid4())
    first = moss.create("I1", payload, key=key)
    second = moss.create("I1", payload, key=key)
    first_id = str((first.body or {}).get("id"))
    second_id = str((second.body or {}).get("id"))
    replayed = (second.header("idempotent-replayed") or "").lower()
    result.check(
        "replay_same_body",
        "same task id, Idempotent-Replayed: true",
        f"ids_match={first_id == second_id} header={replayed!r}",
        first.status == 202 and second.status == 202 and first_id == second_id,
        first=brief(first),
        second=brief(second),
        first_id=first_id,
        second_id=second_id,
        first_has_header=first.header("idempotent-replayed"),
    )
    result.task_ids.append(first_id)

    # I2: same key, reordered keys. Semantically identical, byte-different.
    key_order = str(uuid.uuid4())
    a = moss.create("I2", payload, key=key_order)
    b = moss.create("I2", _reordered(payload), key=key_order)
    a_id = str((a.body or {}).get("id"))
    b_id = str((b.body or {}).get("id"))
    result.check(
        "replay_reordered_keys",
        "treated as the same body (same id) or refused with 422",
        f"{b.status} {b.code or b.error_type or ''} ids_match={a_id == b_id}",
        (b.status == 422) or (b.status == 202 and a_id == b_id),
        first=brief(a),
        second=brief(b),
        first_id=a_id,
        second_id=b_id,
    )
    result.notes.append(
        "reordered-key result tells us whether equality is computed on JSON semantics or on raw bytes."
    )
    if b.status == 202 and b_id != a_id:
        moss.cancel("I2", b_id)
        result.notes.append("reordered body created a second task, so the key is byte-scoped.")
    result.task_ids += [a_id, b_id]

    # I3: same key, different goal.
    key_diff = str(uuid.uuid4())
    c = moss.create("I3", payload, key=key_diff)
    changed = common.task(goal="Open the page and report its main heading.")
    d = moss.create("I3", changed, key=key_diff)
    result.check(
        "replay_different_body",
        "422 idempotency_key_reused",
        f"{d.status} {d.code or d.error_type or ''}",
        d.status == 422 and d.code == "idempotency_key_reused",
        first=brief(c),
        second=brief(d),
    )
    result.task_ids.append(str((c.body or {}).get("id")))

    # I4: two concurrent creates, one key. The race the contract implies is impossible.
    key_race = str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(moss.create, "I4", payload, key=key_race) for _ in range(2)]
        replies = [future.result() for future in futures]
    ids = [str((r.body or {}).get("id")) for r in replies if r.status == 202]
    unique = sorted(set(i for i in ids if i and i != "None"))
    result.check(
        "replay_concurrent",
        "one distinct task id",
        f"{len(unique)} distinct id(s) from {len(ids)} accepted request(s)",
        len(unique) == 1,
        replies=[brief(r) for r in replies],
        ids=ids,
    )
    if len(unique) > 1:
        for extra in unique[1:]:
            moss.cancel("I4", extra)
            result.notes.append(f"concurrent replay produced a duplicate task ({extra}); cancelled it.")
    result.task_ids += unique

    # I5: key length boundaries.
    for size, expected in ((255, 202), (256, 400)):
        reply = moss.create("I5", payload, key="k" * size)
        result.check(
            f"key_length_{size}",
            f"{expected}",
            f"{reply.status} {reply.code or reply.error_type or ''}",
            reply.status == expected,
            **brief(reply),
        )
        if reply.status == 202:
            task_id = str((reply.body or {}).get("id"))
            moss.cancel("I5", task_id)
            result.task_ids.append(task_id)

    return result
