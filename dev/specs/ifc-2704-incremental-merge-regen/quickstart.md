# Quickstart: Validating incremental merge regeneration

**Plan**: [plan.md](./plan.md) · **Spec**: [spec.md](./spec.md)

This guide lists the runnable scenarios that prove the feature works end-to-end. Each maps to a
spec success criterion (SC) and functional requirement (FR). Implementation detail lives in
`tasks.md`; this is the validation surface.

## Prerequisites

- Backend dev environment: `uv sync --all-groups`.
- Fingerprint foundation present (IFC-2844 / PR #9778) so definition fingerprints populate on
  import; scenarios that assert the null-fingerprint fallback deliberately use pre-feature data.
- The config flag `INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE` (default `True`).

## Run the tests

```bash
# Unit — converter, cache round-trip, limit-trap filter, gates on a merge summary
uv run invoke backend.test-unit --path backend/tests/unit/core/merge

# Functional — selective dispatch end-to-end with inline async tasks
uv run pytest backend/tests/functional -k "selective_merge or incremental_merge"

# Integration Docker — full-stack matrix (triggered-action path; required per constitution IV)
uv run invoke backend.test-integration -k "incremental_merge"
```

## Scenario matrix

| # | Scenario | Setup | Expected | Covers |
|---|---|---|---|---|
| 1 | Single-kind change | Merge a branch changing one object of one kind | Only definitions whose `query_models` include that kind dispatch, only for affected member(s); unrelated definitions/members not dispatched | SC-001, FR-001 |
| 2 | No relevant change | Merge a branch changing only data no definition reads | No generator runs, no artifact regenerates | FR-001 |
| 3 | New target regression | Merge a branch adding a new member (no prior artifact) to a group | Artifact regenerates for the new member (via `members` filter, not `limit`) | SC-003, FR-007 (limit trap) |
| 4 | Conflict resolved to base | Merge where a node's only change was a conflict resolved to the base branch | That node is in the affected set; dependent definitions regenerate | FR-003 |
| 5 | Repo-code change (fingerprint) | Merge a branch with a transform-file change (fingerprint recomputed at import) | Affected definitions regenerate via the definition node's fingerprint element in the diff | FR-004 |
| 6 | Edit-then-revert | Merge a branch that edits then reverts a transform file (net-zero) | Zero regeneration tasks dispatched | SC-005, FR-005 |
| 7 | API-edited definition | Merge a branch where a query/definition was edited over GraphQL (no import) | Dependent definitions still regenerate (ordinary node diff) | FR-006 |
| 8 | Fallback: cache miss | Force the merge cache entry absent when follow-up runs | Full regeneration; nothing left stale | SC-003, FR-008 |
| 9 | Fallback: null fingerprint | Pre-feature data (null fingerprint) + a repo commit change in the diff | All definitions of that repository regenerate | FR-008 |
| 10 | Fallback: incomplete closure | A definition with `dependencies_complete != True` | That definition regenerates (over-execution) | FR-008 |
| 11 | Direct-merge generator cascade | Direct (non-PC) merge that dispatches ≥1 `execute_after_merge` generator | Full artifact regeneration for that merge (no stale artifact from generator output) | FR-011 (D7) |
| 12 | No double-trigger | Merge a transform-file change; repo re-imports on default branch | Regeneration triggered exactly once | D8 (OQ2) |
| 13 | PC vs direct parity | Same underlying diff merged via a PC and directly | Same affected-set decision (artifact cascade differs only per D7) | FR-009 |
| 14 | Baseline scale | Representative dataset; run with flag on vs off | Flag-off reproduces the prior full dispatched-task count; flag-on is proportional to affected set | SC-004 |

## Manual smoke check

1. Start the stack against your branch image (see `dev/` — `demo.start` runs published latest,
   not local code; rebuild is required to run branch code).
2. Create a branch, change one object of a kind read by exactly one artifact definition, merge.
3. Confirm in the task view that only that definition's artifact regenerates for the affected
   member — not the full definition/member fan-out — and the instance stays responsive.
4. Set `INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE=false`, repeat, and confirm the full
   fan-out returns (baseline).
