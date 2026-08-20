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
    report-data.json               ranked frequency table, per-bucket incident counts + headline numbers
    joblogs/<job_id>.log           raw logs of failed jobs (ANSI intact; empty = expired)
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import re
import subprocess  # noqa: S404
import sys
from collections import defaultdict
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")

# The Actions list-runs API silently returns at most this many results per query.
API_RESULT_CAP = 1000

# Playwright's breadcrumb separator (U+203A) as it appears in job logs.
PW_SEP = "\u203a"

# Known systemic failure signatures. When one matches a job log, the job is
# tagged with the bucket. The tags feed the report's per-bucket incident counts
# (``bucket_incidents``) and the judgment step (SKILL.md Step 4), which reports
# a bucketed cascade as one incident rather than N flaky tests; the per-test
# table still lists every test, annotated with its buckets, so casualties can
# be discounted. Keep in sync with the table in SKILL.md.
BUCKETS: list[tuple[str, str]] = [
    ("stack-readiness", r"ServerNotResponsiveError: Unable to read from '[^']*/api/schema/load"),
    ("vitest-mock-corruption", r"TypeError: (?:vi\.mocked\(\.\.\.\)|\w+)\.mock\w+ is not a function"),
    ("prefect-setup-triggers-timeout", r"'Setup triggers'.*ReadTimeout|Task run encountered an exception ReadTimeout"),
    ("neo4j-deadlock", r"Neo\.TransientError\.Transaction\.DeadlockDetected"),
    ("compose-boot-failure", r"'docker', 'compose'.*'up', '--wait'.*non-zero exit status"),
    ("sqlite-locked", r"sqlite3\.OperationalError[):] database is locked"),
    ("runner-oom", r"Process completed with exit code 137|exit code: 137"),
    ("docker-network-pool-exhausted", r"all predefined address pools have been fully subnetted"),
    ("actions-download-429", r"Failed to download action .*429"),
    # pytest summary is green (no "N failed") yet the process exits 1: a
    # session-teardown/plugin abort, e.g. the testcontainers result reporting.
    (
        "pytest-green-exit-1",
        r"=+ \d+ passed(?:(?!\d+ failed)[^\n])*=+[^\n]*\n(?:[^\n]*\n){0,3}[^\n]*Process completed with exit code 1\.",
    ),
]

LEDGER_FIELDS = (
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


def gh(args: list[str], *, check: bool = True) -> str:
    res = subprocess.run(["gh", *args], capture_output=True, text=True, errors="replace", check=False)  # noqa: S603, S607
    if res.returncode != 0 and check:
        raise RuntimeError(f"gh {' '.join(args[:3])}... failed: {res.stderr.strip()[:300]}")
    return res.stdout


def gh_json_lines(args: list[str]) -> list[dict]:
    out = gh(args)
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def fetch_job_log(repo: str, job_id: int, log_path: Path) -> None:
    """Download one job log, distinguishing gone from transiently unavailable.

    On success the log is written to ``log_path``. On HTTP 404/410 (the log
    expired or was deleted on GitHub's side) an empty file is written as a
    durable sentinel so the job is never re-fetched. On any other failure
    (rate limit, network) — including a successful call with an empty body,
    which a real job log never has — nothing is written, so the next
    collection retries.
    """
    res = subprocess.run(  # noqa: S603
        ["gh", "api", f"repos/{repo}/actions/jobs/{job_id}/logs"],  # noqa: S607
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if res.returncode == 0 and res.stdout:
        log_path.write_text(res.stdout, encoding="utf-8")
    elif res.returncode == 0:
        print(f"[collect] WARN log {job_id}: empty response, leaving unfetched for retry", file=sys.stderr)
    elif "HTTP 404" in res.stderr or "HTTP 410" in res.stderr:
        log_path.write_text("", encoding="utf-8")
    else:
        print(f"[collect] WARN log {job_id}: {res.stderr.strip()[:300]}", file=sys.stderr)


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


def _runs_query(repo: str, created: str) -> str:
    return f"repos/{repo}/actions/runs?event=pull_request&created={created}&per_page=100"


def list_runs(repo: str, since: dt.date, until: dt.date) -> list[dict]:
    """List runs in [since, until], splitting the date range to stay under the API's 1000-result cap."""
    jq = (
        ".workflow_runs[] | {id, name, head_branch, head_sha, run_attempt, "
        "conclusion, status, created_at, prs: [.pull_requests[] | "
        "{number, base: .base.ref}]}"
    )
    created = f"{since.isoformat()}..{until.isoformat()}"
    total = int(gh(["api", _runs_query(repo, created).replace("per_page=100", "per_page=1"), "--jq", ".total_count"]))
    if total > API_RESULT_CAP and since < until:
        mid = since + (until - since) // 2
        print(f"[collect] {total} runs in {created} exceeds the API result cap; splitting", file=sys.stderr)
        return list_runs(repo, since, mid) + list_runs(repo, mid + dt.timedelta(days=1), until)
    if total > API_RESULT_CAP:
        print(f"[collect] WARN {total} runs on {since} alone; the API returns only the newest results", file=sys.stderr)
    return gh_json_lines(["api", _runs_query(repo, created), "--paginate", "--jq", jq])


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
    fails.update(
        m.group(1).split(" - ")[0].rstrip(",")
        for m in re.finditer(r"(?:FAILED|ERROR) ((?:backend/)?tests/\S+::\S+)", text)
    )
    # legacy TS Playwright — numbered entries of the failure report
    if "E2E-testing-playwright" in job_name:
        for m in re.finditer(rf"\d+\)\s+\[[\w-]+\]\s+{PW_SEP}\s+(tests/e2e/[^\n{PW_SEP}]+){PW_SEP}([^\n]+)", text):
            spec = m.group(1).strip().split(":")[0]
            title = re.sub(r"\s+", " ", m.group(2)).strip()[:120]
            fails.add(f"PW {spec} {PW_SEP} {title}")
    # vitest browser mode
    if job_name == "frontend-tests":
        fails.update(
            f"VITEST {m.group(1)}" for m in re.finditer(r"FAIL\s+\|?\s*\w*\s*\|?\s+(src/\S+\.test\.\w+)", text)
        )
    return sorted(fails)


def classify(text: str) -> list[str]:
    return [name for name, pat in BUCKETS if re.search(pat, text)]


def match_runs_to_prs(runs: list[dict], pr_by_num: dict[int, dict], sha2pr: dict[str, set[int]]) -> list[dict]:
    matched = []
    for r in runs:
        nums = {p["number"] for p in r["prs"] if p["number"] in pr_by_num}
        nums |= {n for n in sha2pr.get(r["head_sha"], set()) if n in pr_by_num}
        if nums:
            r["pr_nums"] = sorted(nums)
            matched.append(r)
    return matched


def collect_failed_jobs(
    repo: str, targets: list[tuple[dict, int]], pr_by_num: dict[int, dict], win_dir: Path
) -> list[dict]:
    """Fetch failed jobs and their logs for each (run, attempt); build job entries."""
    jobs_out = []
    for r, attempt in targets:
        try:
            jobs = failed_jobs_for_attempt(repo, r["id"], attempt)
        except RuntimeError as exc:
            print(f"[collect] WARN jobs {r['id']}/{attempt}: {exc}", file=sys.stderr)
            continue
        for job in jobs:
            log_path = win_dir / "joblogs" / f"{job['id']}.log"
            if not log_path.exists():
                fetch_job_log(repo, job["id"], log_path)
            text = ANSI.sub("", log_path.read_text(errors="replace")) if log_path.exists() else ""
            jobs_out.append(
                {
                    "run": r["id"],
                    "attempt": attempt,
                    "final_attempt": r["run_attempt"],
                    "final_conclusion": r["conclusion"],
                    "recovered_same_run": attempt < r["run_attempt"] and r["conclusion"] == "success",
                    "run_created": r["created_at"],
                    "workflow": r["name"],
                    "prs": [{"number": n, "base": pr_by_num[n]["baseRefName"]} for n in r["pr_nums"]],
                    "job_id": job["id"],
                    "job": job["name"],
                    "tests": extract_tests(job["name"], text),
                    "buckets": classify(text),
                    "log_ok": bool(text.strip()),
                }
            )
    return jobs_out


def append_ledger(ledger_path: Path, jobs_out: list[dict], repo: str, today: dt.date) -> int:
    seen: set[str] = set()
    if ledger_path.exists():
        seen = {json.loads(line)["dedup_key"] for line in ledger_path.open(encoding="utf-8")}
    added = 0
    with ledger_path.open("a", encoding="utf-8") as fh:
        for entry in jobs_out:
            week = dt.datetime.fromisoformat(entry["run_created"]).strftime("%G-W%V")
            for test in entry["tests"] or [""]:
                key = f"{entry['job_id']}:{test}"
                if key in seen:
                    continue
                seen.add(key)
                record = {
                    "dedup_key": key,
                    "fetched_at": today.isoformat(),
                    "week": week,
                    "repo": repo,
                    "test": test,
                    **{k: entry[k] for k in LEDGER_FIELDS},
                }
                fh.write(json.dumps(record) + "\n")
                added += 1
    return added


def ranked_tests(jobs_out: list[dict]) -> list[dict]:
    freq: dict[str, list[dict]] = defaultdict(list)
    for e in jobs_out:
        for t in e["tests"]:
            freq[t].append(e)
    table = [
        {
            "test": test,
            "distinct_runs": len({e["run"] for e in entries}),
            "distinct_prs": len({p["number"] for e in entries for p in e["prs"]}),
            "attempts": len(entries),
            "recovered_on_retry": sum(e["recovered_same_run"] for e in entries),
            "buckets": sorted({b for e in entries for b in e["buckets"]}),
            "prs": sorted({p["number"] for e in entries for p in e["prs"]}),
        }
        for test, entries in freq.items()
    ]
    table.sort(key=lambda x: (-x["distinct_prs"], -x["distinct_runs"], x["test"]))
    return table


def bucket_incidents(jobs_out: list[dict]) -> dict[str, dict[str, int]]:
    """Count distinct jobs/runs/PRs per systemic bucket, so a cascade reads as one incident."""
    jobs: dict[str, set[int]] = defaultdict(set)
    runs: dict[str, set[int]] = defaultdict(set)
    prs: dict[str, set[int]] = defaultdict(set)
    for e in jobs_out:
        for b in e["buckets"]:
            jobs[b].add(e["job_id"])
            runs[b].add(e["run"])
            prs[b].update(p["number"] for p in e["prs"])
    return {b: {"jobs": len(jobs[b]), "runs": len(runs[b]), "prs": len(prs[b])} for b in sorted(jobs)}


def weekly_history(ledger_path: Path) -> dict[str, dict[str, int]]:
    hist: dict[str, dict[str, int]] = {}
    if ledger_path.exists():
        for line in ledger_path.open(encoding="utf-8"):
            rec = json.loads(line)
            if rec["test"]:
                weeks = hist.setdefault(rec["test"], {})
                weeks[rec["week"]] = weeks.get(rec["week"], 0) + 1
    return {t: dict(sorted(w.items())) for t, w in sorted(hist.items())}


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
    ap.add_argument("--since", type=dt.date.fromisoformat)
    ap.add_argument("--cache", type=Path, default=Path.home() / "ci-cache")
    args = ap.parse_args()

    today = dt.datetime.now(tz=dt.UTC).date()
    since = args.since or today - dt.timedelta(days=args.days)
    repo_dir = args.cache / args.repo.replace("/", "-")
    win_dir = repo_dir / "windows" / f"{since.isoformat()}_{today.isoformat()}"
    (win_dir / "joblogs").mkdir(parents=True, exist_ok=True)

    pr_by_num = {p["number"]: p for p in list_prs(args.repo, since, args.base)}
    print(f"[collect] {len(pr_by_num)} PRs in scope (bases: {args.base or 'all'})", file=sys.stderr)

    runs = list_runs(args.repo, since, today)
    (win_dir / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in runs))
    print(f"[collect] {len(runs)} pull_request runs since {since}", file=sys.stderr)

    matched = match_runs_to_prs(runs, pr_by_num, pr_head_shas(args.repo, list(pr_by_num)))

    # Attempts worth reading: every earlier attempt of a retried run (those
    # failures are what the retry "fixed"), plus the final attempt when it
    # failed outright. Runs cancelled on attempt 1 are concurrency noise.
    targets = [(r, a) for r in matched for a in range(1, r["run_attempt"] + (r["conclusion"] == "failure"))]
    print(f"[collect] {len(matched)} runs matched to PRs, {len(targets)} run-attempts to inspect", file=sys.stderr)

    jobs_out = collect_failed_jobs(args.repo, targets, pr_by_num, win_dir)
    (win_dir / "failed_jobs_with_tests.json").write_text(json.dumps(jobs_out, indent=1))
    new_records = append_ledger(repo_dir / "ledger.jsonl", jobs_out, args.repo, today)

    report = {
        "window": {"since": since.isoformat(), "until": today.isoformat()},
        "base_filter": args.base or "all",
        "prs_in_scope": len(pr_by_num),
        "runs_matched": len(matched),
        "runs_retried": sum(1 for r in matched if r["run_attempt"] > 1),
        "runs_recovered_on_retry": sum(1 for r in matched if r["run_attempt"] > 1 and r["conclusion"] == "success"),
        "runs_failed_final": sum(1 for r in matched if r["conclusion"] == "failure"),
        "failed_jobs": len(jobs_out),
        "ranked_tests": ranked_tests(jobs_out),
        "bucket_incidents": bucket_incidents(jobs_out),
        "weekly_history": weekly_history(repo_dir / "ledger.jsonl"),
        "new_ledger_records": new_records,
    }
    (win_dir / "report-data.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    print(f"[collect] window dir: {win_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
