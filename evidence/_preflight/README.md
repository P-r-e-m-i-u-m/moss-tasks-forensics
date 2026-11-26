# Preflight

Two credential checks were run before the paid suites. The first used an incomplete
`Authorization` header and got `401`; the second used the documented
`Bearer <project_id>:<project_key>` form and got `404` from a deliberately nonexistent
task, which is the expected authenticated answer.

`wire.jsonl` is append-only across process invocations, so the local `seq` counter restarts
at 1 for each attempt. That is why the file contains two `seq: 1` / `seq: 2` pairs. The
timestamps and request ids distinguish them.
