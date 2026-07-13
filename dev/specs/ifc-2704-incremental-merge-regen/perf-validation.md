# Performance Validation Plan (live application)

**Feature**: IFC-2704 incremental merge regeneration · **Spec**: [spec.md](./spec.md) ·
**Success criteria**: SC-001, SC-002, SC-003, SC-004, SC-005

Validates that selective post-merge regeneration reduces dispatched work versus the current
blanket regeneration, without under-executing. The method is a same-build A/B: measure the
current blanket path, then measure the selective path, on the same dataset and scenarios.

The baseline (before) run is executed now against the current build, whose
`post_process_branch_merge` submits `TRIGGER_ARTIFACT_DEFINITION_GENERATE` and
`TRIGGER_GENERATOR_DEFINITION_RUN` unconditionally. The retest (after) run is executed once the
feature lands, with `selective_execution_after_merge` toggled. Dispatched-task count is
build-independent, so the baseline captured now is directly comparable to the retest later.

## Metric

| Metric | Definition | Trustworthiness |
|---|---|---|
| Dispatched-task count | Count of post-merge generator/artifact flow runs (see Instrumentation) in the follow-up window | Headline. Deterministic, build-independent, directly comparable across runs and builds |
| Time-to-usable / recompute window | Wall-clock from merge commit to drained follow-up queue | Directional only. Build-dependent; compare within one build, never across builds (a published image vs a source build is not comparable) |
| Under-execution count | Definitions/members whose input changed but were not regenerated | Correctness gate. Must be zero (SC-003) |

## Environment

| Run | Build | How |
|---|---|---|
| Baseline (before) | Current blanket behavior | Any build without the feature: current `stable`/base image, or this branch's base commit. `uv run invoke demo.start` is acceptable for the baseline because the baseline is the unmodified behavior |
| Retest (after) | This branch built locally | Rebuild from source; `demo.start` runs the published image, not local code, and `dev.build` alone can run stale code. Rebuild and wipe the workflow database before the retest. See [[project_infrahub_local_image_testing]] |

Both runs use the same dataset, the same scenario definitions, and inline/awaited follow-up so
the dispatched set is fully observable before teardown.

## Datasets

| Dataset | Shape | Used for |
|---|---|---|
| Representative | Multiple kinds; several artifact and generator definitions with realistic `query_models`; groups with tens of members | Scenario matrix (functional A/B) |
| Scale | One large group (hundreds to low thousands of members) targeted by multiple definitions, approximating the IFC-2306 report (thousands of post-merge tasks, multi-minute unusable window) | Scale run (SC-004 headline reduction) |

The scaled profiling harness reportedly lives in a dedicated dataset repository (per IFC-2761,
IFC-2889). Reuse it for the scale dataset if available rather than authoring a new generator.

## Instrumentation

1. **Enumerate the flow set once.** On the first baseline merge, list the distinct flow names
   spawned in the follow-up window by querying the Prefect API (task manager, `:4200/api`):

   ```bash
   PROJECT=$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep -m1 infrahub)
   PREFECT=$(docker compose -p "$PROJECT" port task-manager 4200)   # host:port
   # flow runs created after a timestamp, newest first
   curl -s -X POST "http://$PREFECT/api/flow_runs/filter" \
     -H 'Content-Type: application/json' \
     -d '{"flow_runs":{"start_time":{"after_":"<merge_commit_iso8601>"}},"sort":"START_TIME_DESC","limit":200}' \
     | jq -r '.[].name' | sort | uniq -c
   ```

   The blanket path produces `trigger-artifact-definition-generate` and
   `trigger-generator-definition-run`, each fanning out to `request-artifact-definition-generate`
   / `request-generator-definition-run` per definition and then per member. Record the exact
   names observed; they are the count target for every subsequent run.

2. **Count per merge.** Use `/api/flow_runs/count` with the same filter plus a name filter for
   the recorded flow set and a start-time bound at the merge commit. This count is the
   dispatched-task metric.

3. **Window.** Record merge commit time and the time the last follow-up flow run reaches a
   terminal state (`/api/flow_runs/filter`, max `end_time`). Report as directional only.

4. **Correctness probe.** After the follow-up drains, assert every artifact/generator whose
   input changed in the scenario has a regenerated output (compare stored value or
   `updated_at`), and that unrelated outputs are untouched. Any changed-input output left stale
   is an under-execution failure (SC-003).

### Counting caveat (validated 2026-07-13)

A naive "count every flow run started after the merge watermark" is polluted and does not
converge. Two sources of noise must be excluded:

- **Recurring background deployments** sit perpetually in `SCHEDULED` with a null or future
  `start_time` (periodic git sync, deadlock cleanup, diff maintenance). The `after_` filter
  sweeps them in and they never drain, so total appears to grow forever.
- **Periodic maintenance flows** (`Sync Git Repositories`, `Clean up deadlocks`) occasionally
  execute inside the measurement window but are unrelated to the merge.

Correct metric: restrict to flow runs in a terminal state with `start_time` inside
`[watermark, watermark + drain]`, filtered to the regeneration flow-name families:
`^Generate artifact `, `^Run generator `, `^Update GraphQLQuery Group`, plus the orchestration
wrappers (`Run all generators`, `Generate all artifacts`, `Trigger Generation of Artifacts`,
`Execute generator`). The headline count is the regeneration leaf flows (artifact generations
+ generator-member runs + GraphQL-query-group updates). The retest must apply the identical
name filter so the before/after numbers are comparable.

## Procedure

### Baseline (before), executed now

1. Start the baseline environment; load the representative dataset.
2. For each scenario in the matrix: perform the merge, capture dispatched-task count, window,
   and the correctness probe. Record under "Baseline" in Results log with the build commit and
   date.
3. Repeat on the scale dataset for the scale run.
4. Commit the filled Results log so the numbers are versioned.

### Retest (after), executed post-implementation

1. Rebuild this branch from source and wipe the workflow database (see Environment).
2. Repeat every scenario twice: `selective_execution_after_merge=false` (must reproduce the
   baseline counts) and `=true` (selective).
3. Fill the "Retest" columns. Compute the reduction versus baseline.

## Scenario matrix

Source scenarios: [quickstart.md](./quickstart.md). Expectation columns are dispatched-task
count relative to the blanket baseline for that scenario.

| # | Scenario | Merge action | Baseline (flag off / current) | Selective (flag on) | SC |
|---|---|---|---|---|---|
| 1 | Single-kind change | Change one object of one kind | All definitions x all members | Only definitions reading that kind, only affected members | SC-001 |
| 2 | No-op read | Change nothing any definition reads | All definitions x all members | Zero | SC-001 |
| 3 | New target | Add a new object to a targeted group | All | Affected definitions, including the new member | SC-001 |
| 4 | Membership-only | Add an existing object to a targeted group | All | Affected definitions, including the added member | SC-001 |
| 5 | Repo-code change | Merge a transform-file change | All | Only definitions whose fingerprint changed | SC-001 |
| 6 | Edit-then-revert | Edit then revert a transform file (net zero) | All | Zero | SC-005 |
| 7 | Cache-miss fallback | Force the summary cache absent or unreadable | All | All (blanket fallback, no under-execution) | SC-003 |
| 8 | Direct-merge cascade | Direct merge dispatching >=1 `execute_after_merge` generator | All | Selective generators, then artifacts sequenced after generator completion, not stale | SC-003 |

### Scale run

On the scale dataset, run scenario 1 (single small change) and a typical small multi-kind
merge. Baseline reproduces the IFC-2306 magnitude (thousands of tasks, multi-minute window).
Selective must reduce the count to the affected set and remove the multi-minute unusable
window (SC-002, SC-004).

## Acceptance thresholds

| Criterion | Threshold |
|---|---|
| SC-001 | Selective count for scenarios 1, 3, 4, 5 scales with the affected set, not instance size |
| SC-002 | No multi-minute unresponsive window on the scale run under selective |
| SC-003 | Zero under-execution across all scenarios, including fallbacks (7) and cascade (8) |
| SC-004 | Scale run shows a substantial count reduction; flag-off reproduces the baseline count exactly |
| SC-005 | Scenario 6 dispatches zero |

## Results log

Fill and commit after each run. One row per scenario per dataset.

### Baseline (before)

- Build: published demo image (pre-feature blanket path) · Date: 2026-07-13 ·
  Dataset: `infrahub-demo-edge` (read-only repo) on the base infra demo: ~48 devices,
  2 artifact definitions (20 artifacts), 4 generator definitions.
- Scenario run: single-kind change (`InfraDevice.description` on one device, `atl1-edge1`),
  merged to `main`. The blanket path is scenario-independent: it regenerates every definition
  for every member regardless of what changed, so scenarios 1-6 and 8 produce the same count by
  construction. Only scenario 1 was executed; the others are marked accordingly.

| # | Dispatched count | Window (s) | Under-execution | Notes |
|---|---|---|---|---|
| 1 | 80 regen (40 query-group + 20 artifact + 20 generator-member) + ~18 merge/orchestration | ~78 | N/A (blanket) | Measured. None needed for a one-device change |
| 2 | = #1 | ~78 | N/A | Blanket ignores that nothing relevant changed |
| 3 | = #1 | ~78 | N/A | Blanket path is scenario-independent |
| 4 | = #1 | ~78 | N/A | Blanket path is scenario-independent |
| 5 | = #1 | ~78 | N/A | Blanket path is scenario-independent |
| 6 | = #1 | ~78 | N/A | Blanket regenerates even on a net-zero edit |
| 7 | n/a | | | Fallback exists only in the feature; no baseline analogue |
| 8 | = #1 | ~78 | N/A | Blanket already regenerates artifacts after generators |
| scale-1 | deferred | | | Needs the profiling-harness scale dataset |
| scale-multi | deferred | | | Needs the profiling-harness scale dataset |

### Retest (after)

- Build commit: `__________`  Date: `__________`  Dataset: `__________`

| # | Count flag off | Count flag on | Reduction | Window flag on (s) | Under-execution | Notes |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |
| 6 | | | | | | |
| 7 | | | | | | |
| 8 | | | | | | |
| scale-1 | | | | | | |
| scale-multi | | | | | | |
