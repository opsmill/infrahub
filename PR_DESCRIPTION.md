# Why

Merging a proposed change whose source branch had been **rebased** failed with `ResourceNotFoundError: Multiple diffs for branch <branch> with tracking_id branch.<branch>`, even though both Schema and Data Integrity validators passed and the pre-merge check reported the change eligible to merge.

A rebase advances the branch's `branched_from` time. When the tracked diff is recalculated, the pre-rebase diff root's `from_time` now falls *before* the new time window, so it escapes the time-bounded stale-diff cleanup and is left behind under the same branch tracking id. Two roots then share `branch.<branch>`, and the merge task's single-diff lookup (`get_one(tracking_id=…)`) finds more than one and raises.

Closes #9898

## What changed

<!-- Behavioral changes -->
- **Merging a proposed change after its source branch was rebased now succeeds.** Rebased branches no longer accumulate duplicate diff roots under one tracking id.
- When recalculating a branch's tracked diff, the coordinator now deletes every *other* root carrying the same tracking id — querying by tracking id alone instead of within the aggregation's time range — so a tracking id always maps to a single diff.
- Because the merge flow re-runs the diff update before the failing lookup, this also unblocks databases already in the broken state on the next merge attempt.

<!-- What stayed the same -->
- No schema changes; no API contract changes. Only the diff-coordinator cleanup path is affected.

## How to review

- Core change: `backend/infrahub/core/diff/coordinator.py` — the stale-root cleanup in `_update_diffs`.
- Regression test: `test_tracking_diff_not_duplicated_after_rebase` reproduces the rebase → duplicate-root scenario (fails with the exact issue error before the fix).

## How to test

```bash
uv run pytest backend/tests/component/core/diff/test_coordinator.py -q
```

The new test fails on `stable` with `Multiple diffs for branch branch with tracking_id branch.branch` and passes with this fix. Full diff + branch-merge component suites: 240 passed, no regressions.

## Impact & rollout

- **Backward compatibility:** No breaking changes. Existing broken databases self-heal on the next tracked-diff recalculation (e.g. the next merge).
- **Performance:** One extra lightweight `get_roots_metadata(tracking_id=…)` query per diff recalculation.
- **Config/env changes:** None.
- **Deployment notes:** Safe to deploy.

## Checklist

- [x] Tests added/updated
- [x] Changelog entry added
- [ ] External docs updated (not needed — internal fix, no user-facing behavior change)
- [x] Internal .md docs reviewed
- [x] I have reviewed AI generated content
