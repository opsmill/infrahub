# ruff: noqa: INP001  # standalone script, not a package
"""Print a session's doc-reads log, or its last 200 lines when it is longer.

Usage:
    python3 .agents/plugins/context/scripts/context_trace.py <invoking session id> [session id]
"""

from __future__ import annotations

import argparse
import sys

from context_map import resolve_log

MAX_LINES = 200


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("invoking_session", help="the session running this script, used when no session is given")
    parser.add_argument("session", nargs="?", help="session id, session directory, or reads.jsonl path")
    args = parser.parse_args()

    log = resolve_log(args.session or args.invoking_session).with_suffix(".log")
    lines = log.read_text(encoding="utf-8").splitlines()
    if len(lines) > MAX_LINES:
        print(f"Last {MAX_LINES} of {len(lines)} lines; the full log is {log}")
        lines = lines[-MAX_LINES:]
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
