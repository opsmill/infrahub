# Validation status

## Delivery boundary

The delivered workflow enables observation only. Its mutation job has an unconditional false guard;
no manual input, repository variable, or secret can enable it. Local tests use fake mutation
transports. Live validation used read-only GitHub requests. No lifecycle comment, label, dashboard,
cache mutation, closure, merge, or production workflow dispatch was performed.

Hosted mutation validation and production recovery remain unverified. A named authorized isolated
repository has not been supplied. This blocks activation, not review of the observation-only PR.

## Real inventory dry run

The capture began at `2026-09-28T13:08:21.967171+00:00`. The collector evaluated 117 open PRs:
112 human-authored and five excluded bots. All required pages and same-head readiness queries
completed. It made 906 logical REST reads and 112 GraphQL queries, with zero lifecycle writes.
One in-flight read was interrupted to checkpoint the capture; the resumed scan reused saved
responses and fetched only missing paths. The total HTTP attempt count includes that interrupted
request. Raw responses remain local and are not committed.

The captured inventory is a polling observation over an interval, not an atomic GitHub snapshot.
The token exposed a 5,000 core allowance; this is not proof of hosted `GITHUB_TOKEN` capacity.
See [sanitized inventory evidence](evidence/live-inventory.json).

Offline replay of the captured responses through the policy engine proposes:

| Result | Count |
| --- | ---: |
| Ordinary reminders | 51 |
| Fresh 14-day warnings | 12 |
| Closure candidates | 0 |
| Excluded bots | 5 |
| Draft | 56 |
| Blocked | 36 |
| Waiting for review | 13 |
| Ready to merge | 5 |
| Waiting for author | 2 |

These are proposed actions, not deliveries. No lifecycle ledger existed. Each old eligible PR
therefore needs a fresh confirmed warning; legacy labels do not authorize closure. The 63 proposed
notices make first-run volume explicit for activation review. See
[sanitized policy evidence](evidence/dry-policy.json).

## Acceptance matrix

| Requirement | Evidence and scope |
| --- | --- |
| Infrahub-only, issues excluded | Repository guard and transport allowlist tests; observer inventories PRs only |
| Observation has no lifecycle writes | Read-only transport tests, read permissions, constant-false mutation job, live capture |
| 60-day inactivity and fresh 14-day warning | Boundary and legacy-label tests, server receipt validation |
| Fixed 14/7/1 notices | UTC date-window, daily jitter, missed-window, rerun, and strongest-notice tests |
| Weekly reminders including exempt humans | Cadence and ordinary-message tests with approvals, drafts, and keep-open |
| Correct author/reviewer/team action | Routing matrix, decisive-review reduction, same-head readiness tests |
| Approval, keep-open, and bots exempt closure | Independent exemption and post-gate approval tests |
| Human activity resets; reopening starts fresh | Feed, fingerprint, changed-head, reopen, and human-edit tests |
| Own writes do not reset clocks | Receipt recovery, overlapping feeds, and full lifecycle progression tests |
| No duplicate or ambiguous delivery | Pending intents, failed receipt persistence, marker/content matching, and generation conflict tests |
| Only pinned stale closes | Restricted write transport rejects close/merge operations; pinned processor gate fixture |
| Complete inventory and actual outcomes | Pagination, quota reserve, incomplete-read suppression, independent candidate verification |
| Cache continuation and shifting pages | 36 pinned-source assertions; 574 fully cached candidates need four passes |
| Dashboard and final reconciliation | Rendering, adoption, generation conflict, full-body size, retention, and last-success timestamp tests |
| Hosted timing, permissions, and cache service | Deferred until a named authorized isolated repository is available |
| Production recovery | Requires a later authorized rollout and scheduled-run evidence |

The full lifecycle policy test reaches a current gate. The separate pinned-source fixture proves
that the upstream processor accepts that gate contract. This local composition does not replace
a hosted end-to-end run.

## Capacity and residual risks

The current mixed-backlog read estimate fits a 1,000-core allowance with reserve in local fixtures;
the live capture consumed 906 REST reads. Extra pages, concurrent use, and retries can still exhaust
quota, so actual response headers and request limits remain authoritative.

Mutation preflight includes fresh eligibility reads and ledger persistence. The first-run proposed
notice batch exceeds the conservative mutation estimate under a 1,000-core token. It must stop
before writes; this PR does not claim that batch is operationally ready. Hosted capacity validation
and any required request-cost optimization remain activation blockers.

Four passes resolve the tested 574-candidate restored-cache fixture. They do not guarantee arbitrary
backlog sizes, insufficient operation budgets, API outages, or hostile concurrent changes. Exhaustion
reports exact deferred candidates and fails. The workflow never clears continuation between passes.

An approval or activity can arrive between the final eligibility read and upstream closure. Polling
also cannot reliably detect a same-resolution human edit-and-reversal during an owned write. These
residual races require explicit activation review.

## Local checks

Per-test identifiers, exact commands, ISO timestamps, environments, and verbatim passing output:

- [Setup](evidence/phase-1-validation.txt)
- [Foundations](evidence/phase-2-validation.txt)
- [Reliability](evidence/phase-3-validation.txt)
- [Cleanup](evidence/phase-4-validation.txt)
- [Reminders](evidence/phase-5-validation.txt)
- [Dashboard and compact state](evidence/phase-6-validation.txt)
- [Independent pre-CI checks](evidence/pre-ci-independent.txt)

All 84 unit tests and 36 upstream assertions passed after dashboard integration. The complete
persisted body for the captured inventory is 49,914 characters. A synthetic completed active-cycle
state is 58,974 of 60,000 characters. These checks retain every PR row and all active proof receipts.
The final review found two issues, both fixed with regressions: a delayed reopen could hide newer
activity, and an unsuccessful label write could report success. All 86 unit tests now pass.
See [review and resolution](review-report.md), [final check output](evidence/final-validation.txt),
[per-test report](opsmill-implement-report.md), and [read-only dashboard preview](evidence/dashboard-preview.md).

Final Ruff, formatting, main lint, whole-repository type checks, and YAML checks passed.
Actionlint passes with the intentional constant-false mutation guard diagnostic excluded;
shellcheck is unavailable. YAML was run with the generated nested virtual environment temporarily
outside the tree. The default testcontainers command hits a macOS CPU-metadata error; its tests
pass with the disclosed external shim (10 passed, 2 skipped). This is an environment-qualified
result, not a claim that the default command passed. Hosted testing and mutation capacity still
block activation.
