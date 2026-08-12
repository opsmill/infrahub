# Baseline: Python transform computed-attribute recompute on merge

**Measured**: 2026-08-12 · **Base**: `release-1.11` at `ec2898748` · **Harness**: `backend/tests/integration_docker/test_merge_recompute_timing.py::TestPythonMergeRecomputeTiming`

Recorded before any production change, so the after-numbers have something to compare against. This is the input to the T010 gate and to SC-002, SC-004 and SC-007.

## How it was measured

Every scale runs on a freshly booted stack with nothing else on it. The schema carries a Python transform computed attribute that reads a peer across a relationship, and **no display label and no human-friendly id**, so the Python family is the only derived value in play. The merge payload edits every peer on a branch, so each owner that reads a changed peer has to recompute.

`control_family_runs` counts the three already-coalesced families. It is zero at every scale, which is what makes the rest of the numbers attributable to the Python family alone.

```bash
INFRAHUB_PROFILE_TIMING=1 INFRAHUB_PROFILE_SCALE=<n> INFRAHUB_TESTING_IMAGE_VER=local-dev \
INFRAHUB_TESTING_DOCKER_PULL=false INFRAHUB_TESTING_TASKMGR_SCALEOUT=1 INFRAHUB_TIMEOUT=900 \
uv run --no-sync pytest backend/tests/integration_docker/test_merge_recompute_timing.py::TestPythonMergeRecomputeTiming -q -s
```

## Results

| Changed nodes | Flow runs | Runs per node | Trailing window | Window per node | Merge critical path | Nodes written | Control family runs |
|---|---|---|---|---|---|---|---|
| 5 | 10 | 2.0 | 3.4 s | 0.674 s | 12.5 s | 5 | 0 |
| 100 | 200 | 2.0 | 51.0 s | 0.510 s | 10.3 s | 100 | 0 |
| 1000 | 2000 | 2.0 | **498.2 s** | 0.498 s | 73.3 s | 1000 | 0 |
| 2000 | not run | | | | | | |

The 2000-node scale was not run. Three points already pin the relationship exactly, and the gate below only needs 1000.

## What the numbers show

**The fan-out is exactly two jobs per changed node, at every scale.** 10 at 5, 200 at 100, 2000 at 1000. Not approximately two, exactly two: the reader-resolution job and the transform job, one pair per changed node. This is the per-node entry the feature exists to remove, and it is now measured rather than assumed.

**The trailing window is linear in the changed-node count.** Per-node cost of 0.674 s, 0.510 s, 0.498 s, converging on about half a second as the fixed overhead amortises. At 1000 changed nodes that is **8 minutes and 18 seconds** of background work after the merge call has already returned.

**The merge call is not flat, and an earlier reading of this table said it was.** On the first two points it looked like fixed overhead (12.5 s, 10.3 s). At 1000 nodes it is 73.3 s, a seven-fold jump. That is the graph merge of 1000 changed nodes doing real work, and it is not something this feature addresses. It does not change the conclusion — the trailing window is still 6.8 times the merge call, and 87% of the total time an operator waits — but the merge call cannot be dismissed as constant.

**Every affected node was refreshed at every scale.** `nodes_written` equals the changed-node count exactly, so the baseline measures correct work rather than a path that silently skips.

## T010 gate decision: PROCEED

The threshold, fixed in the task list before any measurement so it could not be chosen to fit the result: **stop if the trailing window at 1000 changed nodes is under 60 seconds.**

Measured: **498.2 s**. That is 8.3 times the threshold. The gate passes and the work is justified.

For the after-comparison, the two targets this baseline sets:

- **SC-002** wants the trailing window at 1000 nodes at or below **49.8 s** (a 90% cut).
- **SC-007** reverts the suppression if the window improves by less than 50%, i.e. if it stays above **249.1 s**, or if transform executions rise above the 1000 recorded here.

## Notes for whoever repeats this

- **Raise the client timeout.** At 1000 nodes and above, `branch.create` exceeds the SDK's 60 s default HTTP read timeout during seeding and the run dies before it measures anything. `INFRAHUB_TIMEOUT=900` fixes it. This is a harness limit, not a product one.
- **Sweep leftover stacks between runs.** An orphaned stack from an aborted run makes the next one fail at boot with the app containers stuck in `Created` and no error on them.
- **The 1000-node run takes 23 minutes**, most of it seeding 2000 nodes and executing 1000 transforms before the merge happens. It cannot complete inside a tool call that caps at ten minutes; detach it.
- **`setsid` does not exist on macOS.** Detach with plain `nohup ... &`, and confirm the pid is alive before believing the run started. A launch that fails instantly leaves a log that a naive watcher reads as "still working".
- **Watch the process, not only the log.** A filter that matches only the success line and a few expected errors stays silent when the run dies for an unanticipated reason, and silence is indistinguishable from progress.
- **Absolute seconds are container-relative.** Only the ratio transfers between machines, which is why SC-002 is expressed as a percentage. Measured on 8 CPUs and 25 GB.
