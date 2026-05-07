# Quickstart — Manual Smoke Test

This recipe exercises the new branch-merge coordination end-to-end against a running Infrahub instance. Use it during PR review and after rollout to a staging environment.

## Prerequisites

- A running Infrahub stack: `uv run invoke dev.start`
- The new feature merged through PR 3 at minimum (BranchLocker + merge wiring + GraphQL chokepoint wrap).
- `curl` and `jq` available, or the GraphQL playground at `http://localhost:8000/graphql`.

## Setup

1. Create two branches:

   ```graphql
   mutation { BranchCreate(data: { name: "feature-A" }) { ok branch { name } } }
   mutation { BranchCreate(data: { name: "feature-B" }) { ok branch { name } } }
   ```

2. On `feature-A`, create a node you'll merge later. Anything cheap; e.g.:

   ```graphql
   mutation { CoreStandardGroupCreate(data: { name: { value: "smoke-test-A" } }) { ok object { id } } }
   ```

## Scenario 1 — Reject during merge (US1, US3)

1. In one terminal, kick off a long merge of `feature-A → main`. (If a long merge is hard to reproduce, simulate by adding a `await asyncio.sleep(20)` inside `_do_merge_branch` for the test — remove before commit.)
2. While the merge is running, in another terminal issue a mutation against `feature-A`:

   ```graphql
   mutation { CoreStandardGroupCreate(data: { name: { value: "during-merge" } }, branch: "feature-A") { ok object { id } } }
   ```

3. **Expected**: GraphQL response with `errors[0].extensions.code == "BRANCH_LOCKED_FOR_MERGE"` and `extensions.branch == "feature-A"`. Message names the branch and tells the caller to retry.

4. Issue the same mutation against `main`. **Expected**: same `BRANCH_LOCKED_FOR_MERGE` (the target branch is also held).

5. Wait for the merge to complete. Re-issue the mutation. **Expected**: success.

## Scenario 2 — Drain wait (US1)

1. Start a long-running mutation on `feature-A`. The simplest reproduction: a mutation that includes a slow trigger (rule, computed attribute) — or directly invoke `BranchLocker.acquire_write` from a test script and hold the context.
2. While the writer is in flight, initiate a merge of `feature-A → main`.
3. **Expected**: the merge waits. Logs show `acquire_merge` polling writer keys.
4. Complete the writer. **Expected**: the merge proceeds within one drain-poll interval and the merged dataset includes the writer's effect.

## Scenario 3 — Drain timeout (US1, US3)

1. Set `INFRAHUB_MERGE_WRITE_DRAIN_TIMEOUT_SECONDS=5` in the dev environment (or override in `infrahub.toml`).
2. Start a writer that holds `acquire_write` for >5 s.
3. Initiate a merge of `feature-A → main`.
4. **Expected**: merge fails with `MERGE_WRITE_DRAIN_TIMEOUT` after 5 s. Branch returns to `OPEN`. Subsequent writes against `feature-A` succeed.

## Scenario 4 — Crash recovery (US4)

1. Start a writer process and hold `acquire_write`.
2. `kill -9` the writer process.
3. Wait for `merge.writer_ttl_seconds` (default 120 s) to elapse.
4. **Expected**: a merge of the same branch no longer waits on the dead writer's writer key — the key has been TTL-evicted from the cache.

For the merge-side mirror: kill the merge worker mid-merge, wait for `merge.intent_ttl_seconds` (default 300 s), confirm writes against the affected branches succeed.

## Scenario 5 — Internal write bypass (US5)

This is exercised automatically by any merge that includes post-merge schema migration or IPAM reconciliation.

1. Modify a schema on `feature-A` (add a new attribute).
2. Initiate a merge of `feature-A → main`.
3. **Expected**: merge completes. Post-merge schema migration runs. IPAM reconciliation runs. Neither fails with `BranchLockedError` — they receive `merge_holder_id` from the merge and bypass the claim.
4. Throughout, external mutations against `feature-A` and `main` are still rejected (per Scenario 1).

## Scenario 6 — Unrelated branch (US2)

1. Initiate a merge of `feature-A → main`.
2. While the merge is running, issue a mutation against `feature-B`.
3. **Expected**: the mutation is *not* rejected by `BranchLockedError` — `feature-B` is not held by the merge.

   **Note**: today's `global_graph_lock()` may still serialize this write at a different layer (see research.md §A.1). This scenario tests the new coordination's contribution; it does not test the legacy behavior. SC-001 is satisfied if the new locker introduces no *additional* delay relative to the pre-feature baseline.

## Cleanup

```graphql
mutation { BranchDelete(data: { name: "feature-A" }) { ok } }
mutation { BranchDelete(data: { name: "feature-B" }) { ok } }
```

If you reset the drain-timeout config, restore the default.

## Automation

The integration_docker tests at `backend/tests/integration_docker/test_branch_merge_coordination.py` (added by this work) automate Scenarios 1, 2, 3, 4, and 5. This quickstart is the manual sanity-check pass — useful when first wiring up a new wrap site or validating a config-default change.
