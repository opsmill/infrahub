#!/usr/bin/env python3
"""Collect CI failure data for flakiness analysis, incrementally, into a local cache.

Fetches GitHub Actions runs for pull requests, matches them to PRs (via the
runs' ``pull_requests`` field *and* a head-SHA join, since the field is often
empty), identifies retried runs and failed attempts, downloads the failed job
logs, extracts failing test identifiers, classifies known systemic failure
signatures, and appends everything to a longitudinal ledger so successive
invocations build trend data.

Only stdlib + the ``gh`` CLI (must be authenticated). Safe to re-run: the runs
listing is refreshed each time, but job logs already on disk are never
re-downloaded and the ledger is deduplicated.

Usage:
  collect.py [--repo OWNER/NAME] [--base GLOB ...] [--days N | --since YYYY-MM-DD]
             [--cache DIR]

Outputs (under <cache>/<owner>-<name>/):
  ledger.jsonl                     one record per (job, test) ever observed
  windows/<since>_<until>/         this invocation's window
    runs.jsonl                     all pull_request runs created in the window
    failed_jobs_with_tests.json    failed jobs of interesting attempts + tests
    report-data.json               ranked frequency table + headline numbers
    joblogs/<job_id>.log           raw logs of failed jobs (ANSI codes intact)
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")

# Known systemic failure signatures. When one matches a job log, the job is
# tagged with the bucket so per-test counts don't mistake an infra cascade for
# N independent flaky tests. Keep in sync with the table in SKILL.md.
BUCKETS: list[tuple[str, str]] = [
    ("stack-readiness", r"ServerNotResponsiveError: Unable to read from '[^']*/api/schema/load"),
    ("vitest-mock-corruption", r"TypeError: (?:vi\.mocked\(\.\.\.\)|\w+)\.mock\w+ is not a function"),
    ("prefect-setup-triggers-timeout", r"'Setup triggers'.*ReadTimeout|Task run encountered an exception ReadTimeout"),
    ("neo4j-deadlock", r"Neo\.TransientError\.Transaction\.DeadlockDetected"),
    ("compose-boot-failure", r"'docker', 'compose'.*'up', '--wait'.*non-zero exit status"),
    ("sqlite-locked", r"sqlite3\.OperationalError\) database is locked"),
]


def gh(args: list[str], *, check: bool = True) -> str:
    res = subprocess.run(["gh", *args], capture_output=True, text=True, errors="replace", check=False)  # noqa: S603, S607
    if res.returncode != 0 and check:
        raise RuntimeError(f"gh {' '.join(args[:3])}... failed: {res.stderr.strip()[:300]}")
    return res.stdout


def gh_json_lines(args: list[str]) -> list[dict]:
    out = gh(args)
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def list_prs(repo: str, since: dt.date, base_globs: list[str]) -> list[dict]:
    # Look back further than the run window: a re-run in the window can belong
    # to a PR whose updatedAt predates it.
    pr_since = since - dt.timedelta(days=21)
    prs = json.loads(
        gh(
            [
                "pr",
                "list",
                "--repo",
                repo,
                "--state",
                "all",
                "--limit",
                "500",
                "--search",
                f"updated:>={pr_since.isoformat()}",
                "--json",
                "number,title,state,baseRefName,headRefName,updatedAt",
            ]
        )
    )
    if base_globs:
        prs = [p for p in prs if any(fnmatch.fnmatch(p["baseRefName"], g) for g in base_globs)]
    return prs


def pr_head_shas(repo: str, numbers: list[int]) -> dict[str, set[int]]:
    sha2pr: dict[str, set[int]] = defaultdict(set)
    for n in numbers:
        out = gh(["api", f"repos/{repo}/pulls/{n}/commits?per_page=100", "--paginate", "--jq", ".[].sha"], check=False)
        for sha in out.split():
            sha2pr[sha].add(n)
    return sha2pr


def list_runs(repo: str, since: dt.date) -> list[dict]:
    jq = (
        ".workflow_runs[] | {id, name, head_branch, head_sha, run_attempt, "
        "conclusion, status, created_at, prs: [.pull_requests[] | "
        "{number, base: .base.ref}]}"
    )
    return gh_json_lines(
        [
            "api",
            f"repos/{repo}/actions/runs?event=pull_request&created=%3E%3D{since.isoformat()}&per_page=100",
            "--paginate",
            "--jq",
            jq,
        ]
    )


def failed_jobs_for_attempt(repo: str, run_id: int, attempt: int) -> list[dict]:
    return gh_json_lines(
        [
            "api",
            f"repos/{repo}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100",
            "--paginate",
            "--jq",
            '.jobs[] | select(.conclusion=="failure") | {id, name}',
        ]
    )


def extract_tests(job_name: str, text: str) -> list[str]:
    """Pull failing test identifiers out of a cleaned (ANSI-stripped) job log."""
    fails: set[str] = set()
    # pytest — backend suites and the pytest-playwright e2e suite
    for m in re.finditer(r"(?:FAILED|ERROR) ((?:backend/)?tests/\S+::\S+)", text):
        fails.add(m.group(1).split(" - ")[0].rstrip(","))
    # legacy TS Playwright — numbered entries of the failure report
    if "E2E-testing-playwright" in job_name:
        for m in re.finditer(r"\d+\)\s+\[\w+\]\s+›\s+(tests/e2e/[^\n›]+)›([^\n]+)", text):
            spec = m.group(1).strip().split(":")[0]
            title = re.sub(r"\s+", " ", m.group(2)).strip()[:120]
            fails.add(f"PW {spec} › {title}")
    # vitest browser mode
    if job_name == "frontend-tests":
        for m in re.finditer(r"FAIL\s+\|?\s*\w*\s*\|?\s+(src/\S+\.test\.\w+)", text):
            fails.add(f"VITEST {m.group(1)}")
    return sorted(fails)


def classify(text: str) -> list[str]:
    return [name for name, pat in BUCKETS if re.search(pat, text)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default="opsmill/infrahub")
    ap.add_argument(
        "--base",
        action="append",
        default=[],
        help="base-branch glob(s) to keep, e.g. release-1.11 or 'release-*' (default: all)",
    )
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--since", type=lambda s: dt.date.fromisoformat(s))
    ap.add_argument("--cache", type=Path, default=Path.home() / "ci-cache")
    args = ap.parse_args()

    today = dt.datetime.now(tz=dt.timezone.utc).date()
    since = args.since or today - dt.timedelta(days=args.days)
    repo_dir = args.cache / args.repo.replace("/", "-")
    win_dir = repo_dir / "windows" / f"{since.isoformat()}_{today.isoformat()}"
    (win_dir / "joblogs").mkdir(parents=True, exist_ok=True)
    ledger_path = repo_dir / "ledger.jsonl"

    prs = list_prs(args.repo, since, args.base)
    pr_by_num = {p["number"]: p for p in prs}
    print(f"[collect] {len(prs)} PRs in scope (bases: {args.base or 'all'})", file=sys.stderr)

    runs = list_runs(args.repo, since)
    (win_dir / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in runs))
    print(f"[collect] {len(runs)} pull_request runs since {since}", file=sys.stderr)

    sha2pr = pr_head_shas(args.repo, list(pr_by_num))

    matched = []
    for r in runs:
        nums = {p["number"] for p in r["prs"] if p["number"] in pr_by_num}
        nums |= sha2pr.get(r["head_sha"], set())
        nums = {n for n in nums if n in pr_by_num}
        if nums:
            r["pr_nums"] = sorted(nums)
            matched.append(r)

    # Attempts worth reading: every earlier attempt of a retried run (those
    # failures are what the retry "fixed"), plus the final attempt when it
    # failed outright. Runs cancelled on attempt 1 are concurrency noise.
    targets: list[tuple[dict, int]] = [
        (r, a) for r in matched for a in range(1, r["run_attempt"] + (r["conclusion"] == "failure"))
    ]

    print(f"[collect] {len(matched)} runs matched to PRs, {len(targets)} run-attempts to inspect", file=sys.stderr)

    seen_ledger: set[str] = set()
    if ledger_path.exists():
        for line in ledger_path.open():
            rec = json.loads(line)
            seen_ledger.add(rec["dedup_key"])

    jobs_out, ledger_new = [], []
    for r, attempt in targets:
        try:
            jobs = failed_jobs_for_attempt(args.repo, r["id"], attempt)
        except RuntimeError as exc:
            print(f"[collect] WARN jobs {r['id']}/{attempt}: {exc}", file=sys.stderr)
            continue
        for job in jobs:
            log_path = win_dir / "joblogs" / f"{job['id']}.log"
            if not log_path.exists() or log_path.stat().st_size == 0:
                text = gh(["api", f"repos/{args.repo}/actions/jobs/{job['id']}/logs"], check=False)
                log_path.write_text(text)  # empty file = log expired/unavailable
            text = ANSI.sub("", log_path.read_text(errors="replace"))
            tests = extract_tests(job["name"], text)
            buckets = classify(text)
            recovered = attempt < r["run_attempt"] and r["conclusion"] == "success"
            entry = {
                "run": r["id"],
                "attempt": attempt,
                "final_attempt": r["run_attempt"],
                "final_conclusion": r["conclusion"],
                "recovered_same_run": recovered,
                "run_created": r["created_at"],
                "workflow": r["name"],
                "prs": [{"number": n, "base": pr_by_num[n]["baseRefName"]} for n in r["pr_nums"]],
                "job_id": job["id"],
                "job": job["name"],
                "tests": tests,
                "buckets": buckets,
                "log_ok": bool(text.strip()),
            }
            jobs_out.append(entry)
            week = dt.datetime.fromisoformat(r["created_at"]).strftime("%G-W%V")
            for test in tests or [""]:
                key = f"{job['id']}:{test}"
                if key in seen_ledger:
                    continue
                seen_ledger.add(key)
                ledger_new.append(
                    {
                        "dedup_key": key,
                        "fetched_at": today.isoformat(),
                        "week": week,
                        "repo": args.repo,
                        "test": test,
                        **{
                            k: entry[k]
                            for k in (
                                "run",
                                "attempt",
                                "final_conclusion",
                                "recovered_same_run",
                                "run_created",
                                "workflow",
                                "job_id",
                                "job",
                                "prs",
                                "buckets",
                            )
                        },
                    }
                )

    (win_dir / "failed_jobs_with_tests.json").write_text(json.dumps(jobs_out, indent=1))
    with ledger_path.open("a") as fh:
        for rec in ledger_new:
            fh.write(json.dumps(rec) + "\n")

    # Frequency table for this window + trend across ledger weeks
    freq: dict[str, list[dict]] = defaultdict(list)
    for e in jobs_out:
        for t in e["tests"]:
            freq[t].append(e)
    table = []
    for test, entries in freq.items():
        table.append(
            {
                "test": test,
                "distinct_runs": len({e["run"] for e in entries}),
                "distinct_prs": len({p["number"] for e in entries for p in e["prs"]}),
                "attempts": len(entries),
                "recovered_on_retry": sum(e["recovered_same_run"] for e in entries),
                "buckets": sorted({b for e in entries for b in e["buckets"]}),
                "prs": sorted({p["number"] for e in entries for p in e["prs"]}),
            }
        )
    table.sort(key=lambda x: (-x["distinct_prs"], -x["distinct_runs"], x["test"]))

    weeks_hist: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    if ledger_path.exists():
        for line in ledger_path.open():
            rec = json.loads(line)
            if rec["test"]:
                weeks_hist[rec["test"]][rec["week"]] += 1

    report = {
        "window": {"since": since.isoformat(), "until": today.isoformat()},
        "base_filter": args.base or "all",
        "prs_in_scope": len(prs),
        "runs_matched": len(matched),
        "runs_retried": sum(1 for r in matched if r["run_attempt"] > 1),
        "runs_recovered_on_retry": sum(1 for r in matched if r["run_attempt"] > 1 and r["conclusion"] == "success"),
        "runs_failed_final": sum(1 for r in matched if r["conclusion"] == "failure"),
        "failed_jobs": len(jobs_out),
        "ranked_tests": table,
        "weekly_history": {t: dict(sorted(w.items())) for t, w in sorted(weeks_hist.items())},
        "new_ledger_records": len(ledger_new),
    }
    (win_dir / "report-data.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    print(f"[collect] window dir: {win_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
