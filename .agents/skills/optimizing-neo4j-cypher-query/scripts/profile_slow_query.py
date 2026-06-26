#!/usr/bin/env python3
"""Find, extract, and PROFILE slow Cypher queries from the running infrahub-database-1 container.

Reads neo4j's `logs/query.log*` to find slow query executions and extract the exact query
text and parameter map. Runs `PROFILE` via cypher-shell with the extracted params.

Primary identifier is `bolt_id` (the per-connection sequence number neo4j stamps on every
query: `id:NNN` at the start of each log line). It is always present. If the API server is
started with `INFRAHUB_TRACE_ENABLE=true`, every query is also tagged with `infrahub_id`
(the OTel span id in hex) — that lets you cross-reference from a trace, but it is not
required for any of the workflows here.

Subcommands:
  find-slow                                  Print the slowest completed queries
  extract <bolt_id|span_id>                  Print the query text + params for one entry
  profile <bolt_id|span_id> [--no-parallel]  Run PROFILE and save outputs

Assumes the database container is named `infrahub-database-1` and accepts the local-dev
credentials neo4j/admin.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

CONTAINER = "infrahub-database-1"
DB_USER = "neo4j"
# Local-dev default per development/docker-compose-database-neo4j.yml; override via env if needed.
DB_PASS = os.environ.get("NEO4J_PASSWORD", "admin")
DB_NAME = "neo4j"

# A finished-query line carries, in order: a timestamp + `INFO id:<bolt> - transaction id:<n>`
# header, the duration (`<ms> ms:`), byte/page-hit counters, the bolt-session preamble, then
# `neo4j - neo4j - <QUERY> - <PARAMS> - runtime=<R> - {name: '<NAME>', infrahub_id: '<HEX>'}`.
# See scripts/test_profile_slow_query.py for a concrete pinned example.
# "Query started:" lines have no duration; ignore them.
HEAD_RE = re.compile(r"^(?P<ts>\S+ \S+)\s+INFO\s+id:(?P<id>\d+)\s+-\s+transaction id:\d+\s+-\s+(?P<ms>\d+)\s+ms:")
# Body starts after the bolt-session preamble, marked by `>\tneo4j - neo4j - `.
BODY_START_RE = re.compile(r">\s+neo4j\s+-\s+neo4j\s+-\s+")
META_SPAN_RE = re.compile(r"infrahub_id:\s*'(?P<span>[0-9a-f]+)'")
META_NAME_RE = re.compile(r"name:\s*'(?P<name>[^']+)'")


@dataclass
class LogEntry:
    ts: str
    bolt_id: int
    ms: int
    query: str
    params: str  # neo4j map literal, directly usable as cypher-shell `:params <...>`
    runtime: str | None
    name: str | None
    span: str | None  # hex; "0" when tracing was disabled on the API server


def _exec(cmd: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
    # `cmd` is always a fixed argv vector (docker / cypher-shell), never a shell string.
    return subprocess.run(cmd, capture_output=True, text=True, input=stdin, check=False)


def _docker_exec(in_container_cmd: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
    return _exec(["docker", "exec", "-i", CONTAINER, *in_container_cmd], stdin=stdin)


def _assert_container_running() -> None:
    res = _exec(["docker", "ps", "--filter", f"name=^{CONTAINER}$", "--format", "{{.Names}}"])
    if CONTAINER not in res.stdout:
        sys.exit(f"error: container '{CONTAINER}' is not running. Start the dev/demo compose stack first.")


def _read_logs() -> str:
    """Return the concatenated content of all /logs/query.log* (newest file first)."""
    listing = _docker_exec(["sh", "-c", "ls -t /logs/query.log /logs/query.log.* 2>/dev/null"])
    files = [f for f in listing.stdout.strip().splitlines() if f]
    if not files:
        sys.exit("error: no query.log files found in /logs inside the database container")
    return "\n".join(_docker_exec(["cat", f]).stdout for f in files)


# Each log entry begins with a line matching this anchor at column 0.
# Queries span multiple lines (literal newlines inside the Cypher), so we have to
# split the log on this anchor rather than process it line-by-line.
ENTRY_ANCHOR_RE = re.compile(r"(?m)^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+\+\d+\s+INFO\s+")


def _split_entries(text: str) -> list[str]:
    """Split the concatenated log into one string per query entry."""
    matches = list(ENTRY_ANCHOR_RE.finditer(text))
    entries: list[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entries.append(text[start:end].rstrip("\n"))
    return entries


def _is_started_line(entry: str) -> bool:
    """A `Query started:` line carries no duration and is an *expected* skip, not a parse failure."""
    lines = entry.splitlines()
    return bool(lines) and "Query started:" in lines[0]


def _parse(entry: str) -> LogEntry | None:
    """Parse one finished-query entry. Returns None only on a genuine format mismatch.

    Callers must pre-filter `Query started:` lines via `_is_started_line` so that a None
    here unambiguously means "this looked like a finished query but did not match the
    expected query.log layout" — i.e. a signal that the log format may have drifted.
    """
    head = HEAD_RE.search(entry)
    if not head:
        return None
    body_start = BODY_START_RE.search(entry)
    if not body_start:
        return None
    body = entry[body_start.end() :]

    # The body trails as query, then params map, then runtime, then the name/infrahub_id meta.
    # Slice from the right so commas/dashes inside the query text don't confuse the boundaries.
    meta_split = body.rfind(" - {name:")
    if meta_split < 0:
        return None
    meta = body[meta_split + 3 :]
    pre_meta = body[:meta_split]

    rt_idx = pre_meta.rfind(" - runtime=")
    if rt_idx < 0:
        return None
    runtime = pre_meta[rt_idx + len(" - runtime=") :].strip()
    pre_runtime = pre_meta[:rt_idx]

    params_idx = pre_runtime.rfind(" - {")
    if params_idx < 0:
        return None
    query = pre_runtime[:params_idx].strip()
    params = pre_runtime[params_idx + 3 :].strip()

    span_m = META_SPAN_RE.search(meta)
    name_m = META_NAME_RE.search(meta)

    return LogEntry(
        ts=head.group("ts"),
        bolt_id=int(head.group("id")),
        ms=int(head.group("ms")),
        query=query,
        params=params,
        runtime=None if runtime == "null" else runtime,
        name=name_m.group("name") if name_m else None,
        span=span_m.group("span") if span_m else None,
    )


def _iter_entries(skipped: list[str] | None = None) -> Iterator[LogEntry]:
    """Yield parsed finished-query entries.

    `Query started:` lines are skipped silently (expected). Any other entry that fails to
    parse is appended to `skipped` (when provided) so callers can warn — a non-empty
    `skipped` on a real log usually means neo4j's query.log format has drifted and the
    regexes above need updating, NOT that there were no slow queries.
    """
    for entry in _split_entries(_read_logs()):
        if _is_started_line(entry):
            continue
        e = _parse(entry)
        if e is None:
            if skipped is not None:
                skipped.append(entry)
            continue
        yield e


def _find_by_id(ident: str) -> LogEntry:
    """Identify a log entry by bolt_id (numeric) or non-zero span_id (hex)."""
    matches: list[LogEntry] = []
    if ident.isdigit():
        target = int(ident)
        matches = [e for e in _iter_entries() if e.bolt_id == target]
        key = f"bolt_id={ident}"
    else:
        matches = [e for e in _iter_entries() if e.span == ident]
        key = f"span_id={ident}"
    if not matches:
        sys.exit(f"no completed query.log entry for {key}")
    # Prefer the slowest match (in case of duplicate bolt_ids across log rotations).
    matches.sort(key=lambda e: e.ms, reverse=True)
    return matches[0]


def cmd_find_slow(args: argparse.Namespace) -> None:
    _assert_container_running()
    skipped: list[str] = []
    entries = list(_iter_entries(skipped))
    if skipped:
        print(
            f"[warning] skipped {len(skipped)} unparseable log entr"
            f"{'y' if len(skipped) == 1 else 'ies'} — if this is large or the result below is "
            "empty/short, neo4j's query.log format likely drifted; update the regexes in this script.",
            file=sys.stderr,
        )
    if args.min_ms:
        entries = [e for e in entries if e.ms >= args.min_ms]
    if args.name:
        entries = [e for e in entries if e.name == args.name]
    entries.sort(key=lambda e: e.ms, reverse=True)
    if not entries:
        sys.exit(
            "no completed queries found in query.log* — has the slow scenario been triggered yet? "
            "(if the [warning] above reported many skipped entries, the log format may have changed)"
        )

    shown = entries[: args.limit]
    name_width = min(max((len(e.name or "?") for e in shown), default=4), 40)
    name_width = max(name_width, 12)
    has_trace = any(e.span and e.span != "0" for e in shown)

    if has_trace:
        print(f"{'ms':>7}  {'bolt_id':>8}  {'runtime':<8}  {'name':<{name_width}}  span_id")
        print(f"{'-' * 7}  {'-' * 8}  {'-' * 8}  {'-' * name_width}  {'-' * 16}")
        for e in shown:
            span = e.span if (e.span and e.span != "0") else "-"
            print(
                f"{e.ms:>7}  {e.bolt_id:>8}  {(e.runtime or '-'):<8}  {(e.name or '?')[:name_width]:<{name_width}}  {span}"
            )
    else:
        print(f"{'ms':>7}  {'bolt_id':>8}  {'runtime':<8}  {'name'}")
        print(f"{'-' * 7}  {'-' * 8}  {'-' * 8}  {'-' * name_width}")
        for e in shown:
            print(f"{e.ms:>7}  {e.bolt_id:>8}  {(e.runtime or '-'):<8}  {(e.name or '?')[:name_width]}")
        print(
            "\n[note] all span_ids are '0' — the API server was started without INFRAHUB_TRACE_ENABLE=true.",
            file=sys.stderr,
        )
        print(
            "       bolt_id is sufficient for `extract` / `profile`; tracing is only needed "
            "for cross-referencing with Tempo/Grafana.",
            file=sys.stderr,
        )


def cmd_extract(args: argparse.Namespace) -> None:
    _assert_container_running()
    e = _find_by_id(args.identifier)
    print(f"# {e.ms} ms  runtime={e.runtime or '-'}  name={e.name}  bolt_id={e.bolt_id}  span_id={e.span or '-'}")
    print("=== QUERY ===")
    print(e.query)
    print()
    print("=== PARAMS (cypher map literal — usable as `:params <...>` in cypher-shell) ===")
    print(e.params)


def _strip_parallel_prefix(query: str) -> tuple[str, bool]:
    """Strip a leading `CYPHER runtime=...` clause if present."""
    lines = query.splitlines()
    if lines and lines[0].lstrip().upper().startswith("CYPHER RUNTIME"):
        return "\n".join(lines[1:]).lstrip(), True
    return query, False


def cmd_profile(args: argparse.Namespace) -> None:
    _assert_container_running()
    e = _find_by_id(args.identifier)

    query = e.query
    stripped = False
    if args.no_parallel:
        query, stripped = _strip_parallel_prefix(query)
        if stripped:
            print("[stripped leading `CYPHER runtime=...` prefix]", file=sys.stderr)

    profiled = "PROFILE " + query
    cypher_input = f":params {e.params}\n{profiled};\n"

    cmd = [
        "docker",
        "exec",
        "-i",
        CONTAINER,
        "cypher-shell",
        "-u",
        DB_USER,
        "-p",
        DB_PASS,
        "-d",
        DB_NAME,
        "--format",
        "verbose",
    ]
    res = _exec(cmd, stdin=cypher_input)

    out_dir = pathlib.Path(args.out) if args.out else pathlib.Path.cwd() / "profile-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = e.span if (e.span and e.span != "0") else f"bolt{e.bolt_id}"
    base = out_dir / f"profile_{tag}"
    base.with_suffix(".cypher").write_text(profiled + "\n")
    base.with_suffix(".params").write_text(e.params + "\n")
    base.with_suffix(".out").write_text(res.stdout + ("\n--- STDERR ---\n" + res.stderr if res.stderr else ""))
    base.with_suffix(".meta").write_text(
        f"ms_from_log={e.ms}\n"
        f"runtime_from_log={e.runtime or '-'}\n"
        f"name={e.name}\n"
        f"bolt_id={e.bolt_id}\n"
        f"span_id={e.span or '-'}\n"
        f"stripped_parallel={stripped}\n"
    )

    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        sys.exit(res.returncode)
    print(f"\n[wrote {base}.cypher / .params / .out / .meta]", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    fs = sub.add_parser("find-slow", help="Print the slowest queries from query.log*")
    fs.add_argument("--limit", type=int, default=15)
    fs.add_argument("--min-ms", type=int, default=0, help="Only show queries that took at least this many ms")
    fs.add_argument("--name", default=None, help="Filter by query name (e.g. diff_property_paths)")
    fs.set_defaults(fn=cmd_find_slow)

    ex = sub.add_parser("extract", help="Print query + params for a bolt_id or span_id")
    ex.add_argument("identifier", help="bolt_id (numeric) or span_id (hex)")
    ex.set_defaults(fn=cmd_extract)

    pr = sub.add_parser("profile", help="Run PROFILE on a bolt_id's or span_id's query")
    pr.add_argument("identifier", help="bolt_id (numeric) or span_id (hex)")
    pr.add_argument(
        "--no-parallel", action="store_true", help="Strip a leading `CYPHER runtime=...` clause before profiling"
    )
    pr.add_argument("--out", default=None, help="Output directory (default: ./profile-out)")
    pr.set_defaults(fn=cmd_profile)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
