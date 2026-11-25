"""G: the file routes, including the nested paths the SDK's own encoder implies.

The reference documents `GET /tasks/{id}/files/{path}` without saying whether
`{path}` is one segment or the rest of the URL. The SDK encodes each segment and
joins them, which only makes sense if the route is greedy. Worth confirming.
"""

from __future__ import annotations

from urllib.parse import quote

from ..client import Moss
from ..model import ProbeResult, brief
from . import common


def run(moss: Moss, args: object) -> ProbeResult:
    result = ProbeResult("G", "files", "Task files")
    interval = float(getattr(args, "interval", 2.0))

    created = moss.create(
        "G1",
        common.task(goal="Open the page, take a note of the heading, and save it as notes.txt."),
    )
    task_id = str((created.body or {}).get("id"))
    result.task_ids.append(task_id)
    run_obj = moss.poll("G1", task_id, timeout_s=240, interval=interval)
    if run_obj.status != "completed":
        return _unfinished(result, run_obj)

    listing = moss.files("G1", task_id)
    result.check(
        "list_shape",
        '{object: "list", data: [{path, bytes}]}',
        f"{listing.status} keys={sorted(listing.body) if isinstance(listing.body, dict) else None}",
        listing.status == 200
        and isinstance(listing.body, dict)
        and listing.body.get("object") == "list"
        and isinstance(listing.body.get("data"), list),
        **brief(listing),
    )
    files = [f for f in (listing.body or {}).get("data", []) if isinstance(f, dict)]
    result.check(
        "files_present",
        "at least one file after a finished task",
        f"{len(files)} file(s)",
        len(files) > 0,
        paths=[f.get("path") for f in files][:20],
    )
    if not files:
        return result

    first = files[0]
    path = str(first.get("path", ""))
    download = moss.request(
        "G1", "GET", f"/tasks/{task_id}/files/{quote(path, safe='/')}", accept="*/*"
    )
    result.check(
        "download",
        "200 with the listed byte count",
        f"{download.status} bytes={len(download.content)} listed={first.get('bytes')}",
        download.status == 200 and len(download.content) == int(first.get("bytes") or -1),
        path=path,
        content_type=download.header("content-type"),
        content_length=download.header("content-length"),
        disposition=download.header("content-disposition"),
        request_id=download.request_id,
    )

    nested = next((f for f in files if "/" in str(f.get("path", ""))), None)
    if nested is None:
        result.notes.append("no nested path in this task's files; the greedy-route case is untested.")
    else:
        nested_path = str(nested["path"])
        nested_reply = moss.request(
            "G1", "GET", f"/tasks/{task_id}/files/{quote(nested_path, safe='/')}", accept="*/*"
        )
        result.check(
            "download_nested_path",
            "200, same bytes",
            f"{nested_reply.status} bytes={len(nested_reply.content)}",
            nested_reply.status == 200
            and len(nested_reply.content) == int(nested.get("bytes") or -1),
            path=nested_path,
            **brief(nested_reply),
        )

    missing = moss.request(
        "G1", "GET", f"/tasks/{task_id}/files/{quote('does-not-exist.txt', safe='')}"
    )
    result.check(
        "missing_file",
        "404 not_found_error",
        f"{missing.status} {missing.code or missing.error_type or ''}",
        missing.status == 404,
        **brief(missing),
    )

    traversal = moss.request(
        "G1", "GET", f"/tasks/{task_id}/files/..%2F..%2Fetc%2Fpasswd", accept="*/*"
    )
    result.check(
        "encoded_traversal_refused",
        "4xx, not a file from outside the task directory",
        f"{traversal.status} {traversal.code or traversal.error_type or ''}",
        400 <= traversal.status < 500,
        **brief(traversal),
        note="single benign check; no attempt was made to read a host file",
    )

    return result


def _unfinished(result: ProbeResult, run_obj: object) -> ProbeResult:
    result.check(
        "task_completed",
        "completed",
        f"{getattr(run_obj, 'status', 'unknown')}",
        False,
        final=getattr(run_obj, "final", {}),
    )
    return result
