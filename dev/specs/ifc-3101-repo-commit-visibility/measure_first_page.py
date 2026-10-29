# ruff: noqa: INP001, S404, S603, S607, PLC2701  # standalone measurement script that runs the git CLI and times a private read function
"""Time the first commit page against a 10,000-commit history (manual measurement aid; not part of the app or tests).

Builds a bare remote with a linear history, clones it, and times the worker-side read of one page
for several imported-commit positions. Each run opens and closes the clone, as a worker does per
request.

Run from the repository root:

  uv run python dev/specs/ifc-3101-repo-commit-visibility/measure_first_page.py
"""

from __future__ import annotations

import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from git import Repo

from infrahub.core.constants import InfrahubKind
from infrahub.git.state.log_reader import _read_commit_log
from infrahub.git.state.models import CommitLogRequest, CommitLogResult

COMMITS = 10_000
PAGE_SIZE = 20
RUNS = 10
FILES = 50
AN_UNKNOWN_COMMIT = "deadbeef" * 5


def build_remote(path: Path) -> None:
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(path)], check=True)
    lines: list[str] = []
    timestamp = 1_700_000_000
    for index in range(1, COMMITS + 1):
        message = f"Commit number {index}"
        content = f"line {index}"
        lines.extend(
            [
                "commit refs/heads/main",
                f"mark :{index}",
                f"author Bench <bench@example.com> {timestamp + index} +0000",
                f"committer Bench <bench@example.com> {timestamp + index} +0000",
                f"data {len(message) + 1}",
                message,
            ]
        )
        if index > 1:
            lines.append(f"from :{index - 1}")
        lines.extend([f"M 644 inline file{index % FILES}.txt", f"data {len(content) + 1}", content, ""])
    subprocess.run(["git", "fast-import", "--quiet"], input="\n".join(lines).encode(), cwd=path, check=True)


def request(imported_commit: str | None, offset: int = 0) -> CommitLogRequest:
    return CommitLogRequest(
        repository_id="measurement",
        repository_name="measurement",
        repository_kind=InfrahubKind.REPOSITORY,
        location="unused",
        infrahub_branch_name="main",
        git_ref="main",
        imported_commit=imported_commit,
        limit=PAGE_SIZE,
        offset=offset,
        include_pending_count=True,
    )


def measure(clone: Path, label: str, commit_log_request: CommitLogRequest) -> None:
    durations: list[float] = []
    result: CommitLogResult | None = None
    for _ in range(RUNS):
        start = time.perf_counter()
        repo = Repo(clone)
        try:
            result = _read_commit_log(repo=repo, request=commit_log_request)
        finally:
            repo.close()
        durations.append(time.perf_counter() - start)
    if result is None:
        raise RuntimeError("No run produced a result")
    print(
        f"{label:<44} condition={result.condition.value:<11} rows={len(result.commits):<3} "
        f"pending={result.pending_count!s:<5} median={statistics.median(durations) * 1000:7.1f} ms "
        f"slowest={max(durations) * 1000:7.1f} ms"
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        remote = Path(directory) / "remote.git"
        clone = Path(directory) / "main"
        build_remote(remote)
        subprocess.run(["git", "clone", "-q", str(remote), str(clone)], check=True)

        repo = Repo(clone)
        head = repo.commit("origin/main").hexsha
        root = repo.git.rev_list("--max-parents=0", "origin/main").strip()
        two_behind = repo.commit("origin/main~2").hexsha
        half_behind = repo.commit(f"origin/main~{COMMITS // 2}").hexsha
        history = int(repo.git.rev_list("--count", "origin/main"))
        repo.close()

        git_version = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True).stdout
        print(
            f"history: {history} commits; Python {sys.version.split()[0]}; {platform.platform()}; {git_version.strip()}"
        )
        print(f"page size {PAGE_SIZE}, {RUNS} runs per case")

        measure(clone, "imported commit is the head", request(imported_commit=head))
        measure(clone, "imported commit 2 behind", request(imported_commit=two_behind))
        measure(clone, f"imported commit {COMMITS // 2} behind", request(imported_commit=half_behind))
        measure(clone, f"imported commit is the root, {COMMITS - 1} behind", request(imported_commit=root))
        measure(clone, "nothing imported", request(imported_commit=None))
        measure(clone, "imported commit not in the clone", request(imported_commit=AN_UNKNOWN_COMMIT))
        measure(
            clone,
            f"last page, offset {COMMITS - PAGE_SIZE}",
            request(imported_commit=head, offset=COMMITS - PAGE_SIZE),
        )


if __name__ == "__main__":
    main()
