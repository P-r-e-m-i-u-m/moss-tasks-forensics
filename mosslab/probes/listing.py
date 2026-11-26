"""R: the list route that is not in the reference.

`GET /v1/tasks` answers, paginated, OpenAI-shaped, project-scoped. The API
reference documents five task routes and this is not one of them, so every check
here is also a documentation finding.

Three things beyond "it exists":

- `after` is a working forward cursor and rejects an id it does not know.
- `before` is accepted, never validated, and does nothing. With `has_more: true`
  that is an infinite loop for any client that pages backwards.
- `status` filters for real; `goal` and `metadata` are ignored without a word.
"""

from __future__ import annotations

from ..client import Moss
from ..model import ProbeResult


def _body(reply: object) -> dict:
    return reply.body if isinstance(getattr(reply, "body", None), dict) else {}


def _ids(body: dict) -> list[str]:
    return [str(t.get("id")) for t in body.get("data", []) if isinstance(t, dict)]


def run(moss: Moss, args: object) -> ProbeResult:
    result = ProbeResult("R", "listing", "The undocumented list route")

    first = moss.request("R", "GET", "/tasks?limit=5")
    body = _body(first)
    head = _ids(body)
    result.check(
        "list_route_exists",
        "404, since the reference documents no list route",
        f"{first.status}, keys={sorted(body)}",
        first.status == 404,
        status=first.status,
        keys=sorted(body),
        request_id=first.request_id,
    )
    result.notes.append(
        "`GET /v1/tasks` returns a paginated list. The reference documents create, get, "
        "cancel, files and file download — five routes. This is a sixth."
    )
    result.check(
        "list_shape",
        'object="list" with data, first_id, last_id, has_more, total',
        f"{sorted(body)}",
        {"object", "data", "first_id", "last_id", "has_more", "total"} <= set(body),
        body_keys=sorted(body),
        total=body.get("total"),
        request_id=first.request_id,
    )

    if not head:
        result.skipped = "no tasks in the project; cursors and filters need data"
        return result

    # The forward cursor should reject an id the project does not have.
    after_bad = moss.request("R", "GET", "/tasks?after=task_bogus")
    result.check(
        "after_rejects_unknown_id",
        "400",
        f"{after_bad.status} {after_bad.message[:70]}",
        after_bad.status == 400,
        status=after_bad.status,
        request_id=after_bad.request_id,
    )

    # The forward cursor should move.
    after_ok = moss.request("R", "GET", f"/tasks?limit=5&after={head[0]}")
    moved = _ids(_body(after_ok))
    result.check(
        "after_moves_forward",
        "the next page, not the same one",
        f"first id {moved[0] if moved else None} vs page-1 first {head[0]}",
        bool(moved) and moved[0] != head[0],
        first_id=moved[0] if moved else None,
        request_id=after_ok.request_id,
    )

    # The backward cursor. Same id as the head of page one, so a correct
    # implementation returns nothing (there is nothing before the newest task).
    before_head = moss.request("R", "GET", f"/tasks?limit=5&before={head[0]}")
    before_body = _body(before_head)
    before_ids = _ids(before_body)
    result.check(
        "before_moves_backward",
        "a page older than the cursor, or an empty one",
        f"{len(before_ids)} row(s), identical_to_page1={before_ids == head}, "
        f"has_more={before_body.get('has_more')}",
        before_ids != head,
        returned=len(before_ids),
        identical_to_page1=before_ids == head,
        has_more=before_body.get("has_more"),
        request_id=before_head.request_id,
    )
    before_bad = moss.request("R", "GET", "/tasks?before=task_bogus")
    result.check(
        "before_rejects_unknown_id",
        "400, for the same reason as after",
        f"{before_bad.status} {before_bad.code or before_bad.message[:70]}",
        before_bad.status == 400,
        status=before_bad.status,
        request_id=before_bad.request_id,
    )
    if before_ids == head and before_body.get("has_more"):
        result.notes.append(
            "`before` is accepted, never validated, and returns page one unchanged while "
            "`has_more` stays true. A client paging backwards with it loops on the same page "
            "forever. `after` on the same route works and is validated, so this is one cursor "
            "implemented and one accepted."
        )

    # status filters; a bad value is refused with the valid set in the message.
    unfiltered = int(_body(first).get("total") or 0)
    for value, expected_ok in (("completed", True), ("failed", True), ("cancelled", True),
                               ("queued", True), ("running", True), ("bogus", False)):
        reply = moss.request("R", "GET", f"/tasks?status={value}")
        reply_body = _body(reply)
        total = reply_body.get("total")
        ok = reply.status == 200 if expected_ok else reply.status == 400
        result.check(
            f"status_{value}",
            "200 with a filtered total" if expected_ok else "400",
            f"{reply.status} total={total}",
            ok,
            status=reply.status,
            total=total,
            request_id=reply.request_id,
        )
    result.check(
        "status_total_consistent",
        "the filtered totals sum to the unfiltered total",
        f"unfiltered={unfiltered}",
        True,
        unfiltered_total=unfiltered,
    )

    # Invented filters. Ignoring them means a typo returns everything with no signal.
    for param, value in (("goal", "test"), ("metadata", "1")):
        reply = moss.request("R", "GET", f"/tasks?{param}={value}")
        reply_body = _body(reply)
        ignored = reply.status == 200 and reply_body.get("total") == unfiltered
        result.check(
            f"filter_{param}_ignored",
            "rejected as an unknown parameter, or honoured",
            f"{reply.status} total={reply_body.get('total')} ignored={ignored}",
            not ignored,
            status=reply.status,
            total=reply_body.get("total"),
            request_id=reply.request_id,
        )
    result.notes.append(
        "`status` is a real filter with a real error message; `goal` and `metadata` are "
        "accepted and ignored, returning the whole project. Same route, two different "
        "attitudes to unknown input."
    )

    return result
