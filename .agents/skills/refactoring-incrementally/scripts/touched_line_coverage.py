#!/usr/bin/env python3
"""Report which pre-change lines a diff modifies or deletes that no test executed.

Usage: touched_line_coverage.py <coverage.json> <base-ref> [<head-ref>]

<coverage.json> must come from running the tests on <base-ref>
(`pytest --cov=<pkg> --cov-report=json:<path>`). Without <head-ref>, the working tree is compared.
Exit: 0 every touched executable line is covered, 1 some are uncovered, 2 error.
"""

from __future__ import annotations

import json
import re
import subprocess  # noqa: S404 - only runs git with fixed arguments
import sys
from pathlib import Path
from typing import Any

MIN_ARGS, MAX_ARGS = 3, 4
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def touched_old_lines(base: str, head: str | None) -> dict[str, set[int]]:
    cmd = ["git", "diff", "-U0", "--no-color", "--diff-filter=MD", base]
    if head:
        cmd.append(head)
    cmd += ["--", "*.py"]
    diff = subprocess.run(  # noqa: S603 - argv is git plus refs the caller passed
        cmd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    touched: dict[str, set[int]] = {}
    current: str | None = None
    for line in diff.splitlines():
        if line.startswith("--- "):
            path = line[4:]
            current = path[2:] if path.startswith("a/") else None
        elif current and (match := HUNK_RE.match(line)):
            start, count = int(match.group(1)), int(match.group(2) or "1")
            touched.setdefault(current, set()).update(range(start, start + count))
    return touched


def main() -> int:
    if len(sys.argv) not in {MIN_ARGS, MAX_ARGS}:
        print(__doc__, file=sys.stderr)
        return 2
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],  # noqa: S607 - git from PATH is intended
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    # coverage.json keys may be absolute or relative to wherever pytest ran.
    files: dict[str, dict[str, Any]] = {}
    for key, data in report["files"].items():
        measured = Path(key)
        rel = (
            measured.relative_to(repo_root)
            if measured.is_absolute() and measured.is_relative_to(repo_root)
            else measured
        )
        files[rel.as_posix()] = data

    touched = touched_old_lines(sys.argv[2], sys.argv[3] if len(sys.argv) == MAX_ARGS else None)
    total_exec = total_missing = 0
    uncovered_report: list[str] = []
    for path, lines in sorted(touched.items()):
        data = next((d for k, d in files.items() if path.endswith(k) or k.endswith(path)), None)
        if data is None:
            uncovered_report.append(f"{path}: not measured (add it to --cov)")
            total_missing += len(lines)
            continue
        executable = set(data["executed_lines"]) | set(data["missing_lines"])
        relevant = lines & executable
        missing = sorted(relevant & set(data["missing_lines"]))
        total_exec += len(relevant)
        total_missing += len(missing)
        status = "ok" if not missing else "UNCOVERED " + ",".join(map(str, missing))
        uncovered_report.append(
            f"{path}: {len(relevant) - len(missing)}/{len(relevant)} touched lines covered  {status}"
        )

    print("\n".join(uncovered_report) or "no pre-existing Python lines modified or deleted")
    print(f"total: {total_exec - total_missing}/{total_exec} touched executable lines covered")
    return 1 if total_missing else 0


if __name__ == "__main__":
    sys.exit(main())
