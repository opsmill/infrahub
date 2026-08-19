---
name: analyzing-ci-flakiness
description: >-
  Analyzes recent CI failures on pull requests to identify flaky tests, using retry outcomes
  (failed attempt → green re-run) and cross-PR recurrence as evidence, and maintains a local
  longitudinal ledger so flakiness can be tracked over time. TRIGGER when: the user wants to find
  flaky tests, correlate recent CI failures, check which tests fail across PRs or recover on
  retry, or refresh the flakiness trend report. DO NOT TRIGGER when: babysitting a single PR's CI
  until green → monitoring-pull-requests; diagnosing or fixing one specific failing test → the
  bug-analysis skills.
argument-hint: "Optional base-branch glob(s) and window, e.g. `release-1.11 14` (default: all bases, last 7 days)"
compatibility: Requires the gh CLI authenticated against the repo. Python 3 (stdlib only). Writes a cache under ~/ci-cache.
metadata:
  version: 0.1.0
  author: OpsMill
---

# CI Flakiness Analyzer

## Introduction

A test is *flaky* when its failure does not reproduce on the same code: the run was retried and
went green, or the same test fails on unrelated PRs. This skill mines both signals from GitHub
Actions history, downloads the failed job logs once into a local cache, and appends every
observation to a ledger (`~/ci-cache/<owner>-<name>/ledger.jsonl`) so repeated invocations —
weekly, or ad hoc — accumulate trend data instead of starting from scratch.

The mechanical part (fetching, caching, test-name extraction, known-signature classification) is
done by the bundled script. Your job is the judgment part: separating flakes from real
regressions, spotting new systemic signatures, and writing the report.

## Step 1 — Parse arguments

- Base-branch filter: any arguments that look like branch names or globs (`release-1.11`,
  `release-*`, `stable`). Default: no filter (all PR bases), which is usually what "how flaky is
  CI" means. Filter when the user names a branch.
- Window: a bare integer is a number of days (default 7). An ISO date means "since that date".

## Step 2 — Collect

Run the bundled collector (repo-root relative):

```bash
python3 .agents/skills/analyzing-ci-flakiness/scripts/collect.py \
  [--base <glob> ...] [--days N | --since YYYY-MM-DD] [--repo owner/name]
```

It prints a JSON report to stdout and writes everything under
`~/ci-cache/<owner>-<name>/windows/<since>_<until>/`:

- `runs.jsonl` — every `pull_request` workflow run created in the window
- `failed_jobs_with_tests.json` — failed jobs of the interesting run-attempts, with extracted
  failing tests, systemic-bucket tags, and a `recovered_same_run` flag
- `report-data.json` — headline numbers, ranked per-test table, per-bucket incident counts
  (`bucket_incidents`: distinct jobs/runs/PRs per systemic bucket), and the ledger's weekly
  history
- `joblogs/<job_id>.log` — raw logs (ANSI intact; strip with `sed 's/\x1b\[[0-9;]*m//g'`)

Notes the script already accounts for — don't re-derive them:

- The runs API's `pull_requests` field is empty for many runs; the script joins runs to PRs
  through every PR head commit SHA as well. Don't trust the field alone.
- "Interesting attempts" = every earlier attempt of a retried run (that's what the retry fixed)
  plus final attempts that failed. Runs cancelled on attempt 1 are concurrency noise and skipped.
- Logs already on disk are never re-downloaded; the ledger is deduplicated by (job, test). Old
  logs expire on GitHub's side (~90 days) — an empty `joblogs/*.log` means expired, not passing.

## Step 3 — Investigate what the script could not name

For failed jobs with an empty `tests` list and no bucket tag, read the log yourself (grep for
`##[error]`, `FAILED`, `Error:`, `Timeout`). Two outcomes:

- It matches a *new* systemic signature (infra failure that cascades over many tests). Add a
  regex for it to `BUCKETS` in `collect.py` and to the table below, so future runs classify it.
- It's a genuine test failure the extraction regexes missed — note the test manually and
  consider extending `extract_tests`.

### Known systemic signatures (as of 2026-08 — keep in sync with `BUCKETS` in collect.py)

| Bucket | Signature | Meaning |
|---|---|---|
| `stack-readiness` | `ServerNotResponsiveError … /api/schema/load` | Seeded testcontainers stack not ready; the whole pytest-playwright shard errors. One incident, not N flaky tests. |
| `vitest-mock-corruption` | `TypeError: vi.mocked(...).mockX is not a function` | vitest browser-mode module-mocking race; hits a different test file each time. |
| `prefect-setup-triggers-timeout` | `Setup triggers` task `ReadTimeout` | Prefect hang at session setup; downstream tests hit their own timeouts. |
| `neo4j-deadlock` | `Neo.TransientError.Transaction.DeadlockDetected` | Concurrent-write deadlock, usually integration suites under xdist. |
| `compose-boot-failure` | `docker compose … up --wait` non-zero exit | Stack never booted; job-level infra failure. |
| `sqlite-locked` | `(sqlite3.OperationalError) database is locked` (also matches the raw `sqlite3.OperationalError:` form) | Prefect's sqlite under contention. |
| `runner-oom` | `Process completed with exit code 137` | Runner OOM/SIGKILL; the mass test failures in the same job are casualties, not flakes. |
| `docker-network-pool-exhausted` | `all predefined address pools have been fully subnetted` | Leaked compose networks exhausted the docker address pools on a self-hosted runner. |
| `actions-download-429` | `Failed to download action … 429` | GitHub rate-limited its own action download; pure platform flake. |
| `pytest-green-exit-1` | green pytest summary directly followed by exit 1 | Session-teardown/plugin abort after all tests passed (e.g. testcontainers result reporting). |

## Step 4 — Judge: flake vs regression

For each test in the ranked table, classify:

- **Flaky (strong)** — fails on ≥2 unrelated PRs, or `recovered_on_retry > 0`. The more distinct
  PRs, the stronger.
- **Flaky (weak)** — single occurrence with an infra-flavored error (locator timeout, transient
  branch not found) and the PR later went green. List, but rank low.
- **Suspect regression, not a flake** — the same test fails on *every* attempt of the same
  commit and the PR is still red, or the failures started only after a specific merge. Say so
  explicitly; do not bury it in the flake list. Cross-check: does the test fail on any PR that
  does not contain the suspect change?
- **Systemic bucket** — tests whose only failures carry a bucket tag are casualties, not causes.
  Report the bucket (with the incident count from `bucket_incidents` in `report-data.json`), not
  the individual tests.

Different tests failing on successive attempts of the same run = two independent flakes, not a
regression.

## Step 5 — Report

Write `ANALYSIS.md` into the window directory, then give the user a summary. Lead with the
ranked flake candidates. Include:

1. Headline numbers: PRs in scope, runs matched, retried runs, retried-and-recovered runs
   (pure-flake evidence), hard failures.
2. Ranked flake candidates — test id, distinct PRs/runs, recovered-on-retry count, one-line
   error cause. Group systemic buckets as single entries.
3. Suspected real regressions, clearly separated.
4. Trend — from `weekly_history` in `report-data.json`: which offenders are new this window,
   which recur week over week, which disappeared (likely fixed). This section is the reason the
   ledger exists; don't skip it once ≥2 windows of data exist.

Do not propose fixes unless asked; the deliverable is the evidence-ranked candidate list.
