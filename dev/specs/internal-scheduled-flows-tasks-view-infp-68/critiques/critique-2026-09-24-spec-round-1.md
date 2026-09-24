# Critique Report: Internal & Scheduled Background Flows in the Tasks View

**Feature**: `internal-scheduled-flows-tasks-view-infp-68` · **Ticket**: infp-68

**Date**: 2026-09-24 · **Round**: 1 · **Scope**: `spec.md` only (`plan.md` not yet authored)

**Reviewer**: Spec Reviewer

## Executive Summary

The spec is well-built: the structure is complete, the requirements are
behavioural and testable, no `[NEEDS CLARIFICATION]` markers remain, and every
autonomous decision is recorded with rationale. The author re-verified the
ticket's stale code references and corrected two of its counts — both
corrections check out (19 internal workflows; five scheduled, `merge-watcher`
included; 3 × 1440 = ~4,320 runs/day).

It is nonetheless **not ready to plan against**, because its central premise is
wrong for 8 of the 19 internal workflows. The claim that internal runs are
"structurally excluded" from the Tasks view holds only for workflows that never
call `add_tags()`. Eight internal workflows do call it, with the `namespace`
parameter left at its default `True`, which stamps `infrahub.app` onto the
running flow — so their runs already satisfy today's filter and already appear
in the default Tasks list. FR-003 and SC-005, written from the wrong premise,
would have the planner enforce a *removal* of those runs as if it were
behaviour preservation.

A second, smaller contradiction (FR-002 vs FR-004) is unsatisfiable against
Prefect's available filter primitives.

Neither defect undermines the feature's motivation: the three flows the
incident story rests on — `git_repositories_sync`, `clean-up-deadlocks`,
`merge-watcher` — call no tagging helper and are genuinely invisible today.

**Verdict**: ⚠️ **PROCEED WITH UPDATES** — two must-address items, both
resolvable by restating facts and requirements. No rethink of the feature is
needed.

## Product Lens Findings

### 3a. Problem Validation

Strong. The problem is concrete, evidenced by a named production incident, and
the spec resists the temptation to over-scope: it explicitly declines to
replace the Prefect UI, to change schedules, and to fix the underlying
`CANCEL_NEW` stall. The cost of inaction is demonstrated rather than asserted.

### 3b. User Value Assessment

Stories 1 and 2 are correctly identified as the MVP pair — a health signal that
dead-ends is not actionable, and the spec says so. Story 3 (Type facet) is
correctly demoted to P2. Acceptance scenarios are written as outcomes, not
mechanics.

**P1 💡** — The requirement set is large for a feature whose P1 slice is "list
five deployments with their last outcome". FR-014 through FR-019a (the
scheduled view) are the MVP; FR-020 through FR-025 (the Type facet) are not.
The spec should say plainly that the Type facet can ship separately, so the
planner can sequence it as an independent increment rather than one release.

### 3d. Edge Cases & User Experience

The edge-case list is the strongest section of the spec. Partial deployment
registration, purged history, collision-cancellation vs. crash, the randomised
cron minute, and count/list filter symmetry are all anticipated. FR-016a
(never colour alone) is a genuine accessibility requirement, not a box-tick.

**P2 💡** — Success-criteria numbering runs SC-001…SC-006, SC-009, SC-010,
SC-007, SC-008. Cosmetic, but it makes traceability tables harder to read.

### 3e. Success Measurement

Measurable and mostly time-bound (30 seconds, 2 seconds p95, three scheduled
intervals). SC-003 is an especially good criterion: it restates the motivating
incident as a test.

## Engineering Lens Findings

### 4a. Architecture Soundness

**E1 🎯 MUST-ADDRESS — The "internal flows are structurally excluded" premise
is false for 8 of 19 workflows.**

`add_tags()` (`backend/infrahub/workflows/utils.py:22-64`) updates the *current
flow run's* tags through the Prefect API and adds `TAG_NAMESPACE` by default:

```python
async def add_tags(..., namespace: bool = True, ...) -> None:
    ...
    new_tags = set(current_tags + branch_tags + node_tags + others_tags)
    if namespace:
        new_tags.add(TAG_NAMESPACE)          # utils.py:60-61
    await client.update_flow_run(current_flow_run_id, tags=list(new_tags))
```

Eight `INTERNAL` workflows call it with that default, so their runs acquire
`infrahub.app` at runtime and pass today's `FlowRunFilterTags(all_=[TAG_NAMESPACE])`:

| Internal workflow | Call site |
|---|---|
| `action-run-generator` | `backend/infrahub/generators/tasks.py` |
| `action-run-generator-group-event` | `backend/infrahub/generators/tasks.py` |
| `generator-definition-run` | `backend/infrahub/generators/tasks.py` |
| `diff-refresh-all` | diff tasks |
| `proposed-changed-refresh-artifacts` | proposed-change tasks |
| `proposed-changed-run-generator` | proposed-change tasks |
| `proposed-changed-repository-checks` | proposed-change tasks |
| `artifacts-generation-validation` | `backend/infrahub/artifacts/tasks.py` |

That this is deliberate, not incidental, is confirmed by the single opt-out in
the codebase: `graphql-query-group-update` passes `namespace=False`
(`backend/infrahub/groups/tasks.py:22`). Namespace-tagging is currently the
per-**run** "show this in the Tasks UI" switch; workflow type is a
per-**deployment** classification. The spec treats the two as equivalent. They
are not.

Consequences for the spec as written:

- The Overview's "structurally cannot show a single `INTERNAL` one" and "every
  `INTERNAL` flow lacks `infrahub.app` and is structurally excluded" are wrong.
- **FR-003** defines the preserved default set as "`CORE` and `USER` runs, and
  no internal runs". Implemented literally, that *removes* eight workflows'
  runs from the default Tasks list — a user-visible regression the spec does
  not acknowledge and has no changelog or migration note for.
- **SC-005** ("exactly the results they returned before this change — verified
  by an automated regression test") then codifies the wrong baseline. The test
  would lock in the regression rather than catch it.

Suggested resolution: restate the premise as "internal runs are excluded unless
the flow opts in at runtime via `add_tags(namespace=True)`, which 8 of 19 do";
redefine FR-003's preserved set by *observed result*, not by type ("the default
selection returns exactly the runs it returns today, including those internal
runs that currently carry the namespace tag"); and decide explicitly whether
those eight should keep appearing by default (recommended — removing them is an
unrelated regression) or be moved behind the Type facet (then it needs its own
changelog entry and an out-of-scope-or-not decision). This is a decision the
spec must make, not defer to the plan.

**E2 🎯 MUST-ADDRESS — FR-002 and FR-004 are mutually unsatisfiable.**

FR-004 requires a run carrying the namespace tag but no workflow-type tag to
remain visible in the default selection. Prefect 3.8.6's `FlowRunFilterTags`
exposes only `operator`, `all_`, `any_` and `is_null_` — there is no "lacks tag
X" predicate, and `is_null_` tests for *no tags at all*, not for the absence of
one tag. "Has `infrahub.app` AND lacks `infrahub.app/workflow-type/*`" is
therefore not expressible in a single tag filter. The only way to honour FR-004
is to keep an unconditional namespace requirement — precisely what FR-002 and
the ticket's fifth acceptance criterion forbid.

The scenario also appears to be vacuous. `TAG_NAMESPACE` and
`WorkflowTag.WORKFLOWTYPE` were introduced in the same commit (`d63f9575c`,
"Add tags for deployment and run in prefect"), every deployment stamps the type
tag unconditionally (`models.py:92`, outside the `if self.type != INTERNAL`
guard), and `add_tags()` preserves `current_tags` — so no run has ever carried
one tag without the other.

Suggested resolution: drop FR-004, or restate it as a non-normative note
("pre-tagging runs predate both tags and are out of scope"). If it is kept,
the spec must say which primitive is expected to express it.

### 4d. Performance & Scalability

Well handled. FR-012a's "aggregate counts, never per-run reads" is the right
constraint and the spec correctly identifies `FlowRunCounter`
(`backend/infrahub/task_manager/flow_run/count.py`) as the existing cheap path —
verified: it counts server-side and caches above
`config.SETTINGS.workflow.flow_run_count_cache_threshold` with a one-minute TTL,
which also lines up neatly with FR-019a's ≤60s staleness bound.

**E3 💡** — SC-006 says "a bounded, constant number of **backend** requests
regardless of how many scheduled flows exist", while FR-012a permits work that
"scales with the number of scheduled flows". Both are satisfiable at once
(constant client→backend; M×N backend→Prefect count calls, ~25 today), but the
wording invites a planner to read SC-006 as forbidding the per-flow counts
FR-012a allows. Disambiguate SC-006 as client-to-backend requests.

### 4f. Operational Readiness

**E4 💡** — FR-010 requires "never run" to read distinctly from "latest run
failed", and the edge-case list concedes "purged history" may be
indistinguishable from "never run". There is more signal available than the
spec assumes: a deployment's creation time compared against the retention
window (`infrahub tasks flush flow-runs`, default 30 days — verified at
`backend/infrahub/cli/tasks.py:68-86`) separates the two in most cases. Worth
noting so the planner does not discard the distinction by default.

### 4c. Security & Privacy

**Q1 🤔** — Assumption 3 (no new permission gates viewing) is flagged by the
author as the one decision a reviewer could reasonably reverse. The reasoning
holds on inspection: `webhook-send` is indeed `WorkflowType.CORE`
(`catalogue.py`) and therefore already visible, and its headers are already
masked (`backend/infrahub/graphql/types/task.py:42`, "Request headers as sent,
with secret values masked"). The internal webhook flows carry ids and fan-out
arguments, not payloads. Concurring: no new gate, and if a later reviewer
disagrees the narrower remedy the spec names — restricting the parameter field —
is the correct one. No change required.

### 4e. Testing Strategy

Constitution Principle IV requires E2E coverage for user-facing features. The
spec's success criteria imply it (SC-002, SC-003 describe stack-level
scenarios) but no requirement states it. Not a spec defect — test level is a
planning decision — flagged so the planner does not miss it.

## Cross-Lens Insights

**X1 🎯** — E1 is simultaneously a correctness defect and a product-scope
question. Eight internal workflows are already visible; the spec must decide
whether this feature preserves that or changes it. Either answer is defensible,
but leaving it undecided means the planner picks silently, and the "no
behaviour change by default" promise that the ticket's fourth acceptance
criterion rests on becomes untrue either way.

## Findings Summary

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| E1 | Engineering | 🎯 | Architecture | 8 of 19 internal workflows call `add_tags(namespace=True)` and are already visible in the default Tasks list; the spec's premise, FR-003 and SC-005 all assume they are not | Restate the premise; define FR-003's preserved set by observed result; decide explicitly whether those 8 keep appearing by default |
| X1 | Both | 🎯 | Scope × Correctness | Whether the 8 already-visible internal workflows stay in the default list is an undecided product question | Decide in the spec, not the plan; if they move, it needs its own changelog entry |
| E2 | Engineering | 🎯 | Architecture | FR-004 is unsatisfiable given Prefect's tag-filter primitives and contradicts FR-002; the scenario it guards has never existed | Drop FR-004 or demote it to a non-normative note |
| P1 | Product | 💡 | Scope | Scheduled view (P1) and Type facet (P2) are specified as one deliverable | State that they can ship as independent increments |
| E3 | Engineering | 💡 | Performance | SC-006 "constant number of backend requests" reads as conflicting with FR-012a's per-flow scaling | Scope SC-006 explicitly to client→backend requests |
| E4 | Engineering | 💡 | Operations | "Never run" vs "history purged" treated as indistinguishable | Note deployment creation time vs. the 30-day retention default as available signal |
| P2 | Product | 💡 | Readability | Success criteria numbered out of order (SC-009/010 before SC-007/008) | Renumber |
| Q1 | Engineering | 🤔 | Security | Assumption 3 (no permission gate) flagged for reviewer attention | Reviewer concurs; premise verified against the catalogue and the masking field. No change required |

## Verification Notes

Every code reference in the spec was checked against the worktree. All were
accurate:

- `filters.py:30` / `:40`, `constants.py:31`, `models.py:88-92`,
  `graphql/queries/task.py:183-197` — correct as cited.
- 19 `INTERNAL` workflows; 5 scheduled; `merge-watcher` present with
  `* * * * *`, concurrency 1, `CANCEL_NEW`; `webhook-configure` with `ENQUEUE`
  — all confirmed.
- `prefect_client.py` exposes flow runs, logs, artifacts, flows, counts, state
  writes and cancellation only — no deployment read path. The spec's decision
  to treat deployment exposure as required scope (Assumption 2) is correct.
- `infrahub tasks flush flow-runs` (30 days) and `flush stale-runs` (2 days)
  — confirmed at `backend/infrahub/cli/tasks.py:68-106`.
- `webhook-send` is `WorkflowType.CORE`; `HttpRequest.headers` is documented as
  masked — both confirmed.

The one class of fact the spec did not check is the runtime tag mutation path
(`workflows/utils.py`), which is where finding E1 comes from.
