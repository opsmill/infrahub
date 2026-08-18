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


## Running the after-measurement (T061)

Not yet recorded: two attempts were made and neither produced a number. What they established, so
the next attempt does not repeat them:

1. **Sweep before starting.** The first attempt failed in 13 s with every infra container healthy
   and all five app containers stuck in `Created`. A stack left behind by an earlier run was still
   holding the ports. The fixture raises before its `yield`, so its teardown never runs and the
   orphan survives the failure that it caused. Clear it first:

   ```bash
   docker compose ls -a
   docker compose -p <project> down -v --remove-orphans
   ```

2. **Capture the whole log, not a tail.** Piping the run through `tail -30` discarded the compose
   exception and left only RabbitMQ boot noise, which reads like a message-queue problem and is
   not one. Redirect to a file.

3. **Expect a long run and watch it from outside.** The second attempt reached 28 minutes with the
   stack healthy before it was interrupted, and the test prints only at the end, so there is no
   progress signal in its own output. Both `_wait_idle` and the measurement window carry 3600 s
   deadlines, which means a coalesced pass that never completes looks identical to one that is
   merely slow. Watch the worker instead:

   ```bash
   P=$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep infrahub-test | head -1)
   docker compose -p $P logs task-worker --tail 20
   ```

   Recompute activity on `computed_attribute_process_transform` means progress; only periodic
   `refresh.git.fetch` lines means the run is idle and something is stuck.

4. **Sweep again afterwards.** An interrupted run leaves its stack up, which is what causes
   failure 1 on the next attempt.

## Two live runs, and what they showed (T061 still open)

Both were interrupted before the harness printed, so neither is a recorded measurement. Both were
read directly off the running stack instead, which is where the findings below come from.

### Run A — the mechanism works

Queried after the merge completed:

| Query | Result |
|---|---|
| `computed_attribute_process_transform`, all | 21 |
| same, filtered on `branch: "main"` | 0 |
| `TestingTShirt.pitch` on main | refreshed, post-merge values |

21 runs is 20 live ones from creating 20 owners plus **one** coalesced run for the merge, where the
per-node path would have produced 20. That is the collapse this feature is for, observed end to end.

The zero is what led to the branch-tag fix: a tag added from inside a run never reaches the task
filter, so the coalesced submissions were invisible to every branch-scoped query. The harness waits
on exactly that count, which is why it hung rather than finished.

### Run B — explained: the harness measured an empty population

Same scale, image rebuilt with the tag fix:

| Signal | Value |
|---|---|
| `computed_attribute_process_transform` runs | 0 |
| `TestingTShirt.pitch` | null, before and after the merge |
| Coalesced submission | `trigger_update_python_computed_attributes`, i.e. **widened** |
| `query_transform_targets` runs | 20 |

**Explained by a third run.** The `COALESCED_PYTHON selected targets` record added for FR-020
answered it in one line:

```text
COALESCED_PYTHON selected targets  branch=main considered=1 selected=0 targets=[] widened=0
```

The pass **dropped** the target; it did not widen. The `trigger_update_python_computed_attributes`
run that looked like a widening fired before the merge, from the schema-driven pass on schema load.

The cause is a single one, upstream of all three symptoms. Registering the Python automations races
with the owner creations that follow it. When the automations lose, no owner ever runs its
transform, so no query group membership is ever created. The merge then changes peers rather than
owners, which leaves the resolver with no owner-axis hit and a subscriber lookup over groups that do
not exist. Dropping the target there is correct: the per-node path finds no reader either, so this
is not under-recompute against the behaviour being replaced.

The harness now asserts the baseline was computed before it measures, so a race turns into an
immediate failure naming the cause instead of an hour of measuring nothing.

The three symptoms, for the record:

1. **The initial live computation never fired.** Pitch was null before any merge, so the owner-axis
   automation did not run when the owners were created. Run A did compute it. The likely candidate
   is a race between creating the owners and `computed_attribute_setup_python` registering the
   automations, which is not something this feature introduced, but it invalidates the run.
2. **The pass widened.** The read-field index came back without an entry for the pair, and the
   transform does exist in the database. Worth tracing `DatabaseReadFieldIndex.for_branch` against
   a live stack before trusting the narrowing at scale.
3. **The widened flow produced nothing.** `trigger_update_python_computed_attributes` completed and
   submitted no `process_transform` at all, though 20 owners exist on the branch it was given.

The tag fix is unrelated to any of this: it touches only the submission path. Run A remains the only
end-to-end evidence that the collapse happens, and it is not a measurement. What is still needed is
one clean run, with the baseline guard in place, at 100 and 1000.


## After, at 100 changed nodes (T061)

First clean run, with the baseline guard in place. Feature on, image built from the branch.

```text
[python-merge-recompute-timing] changed_nodes=100 control_family_runs=0
CostCenterTiming(merge_critical_path_s=9.37, recompute_window_s=17.44,
                 recompute_flow_runs=1, recompute_nodes_written=100)
```

| Metric | Before | After | Change |
|---|---|---|---|
| Trailing recompute window | 51.0 s | 17.4 s | −66% |
| Recompute flow runs | ~200 (2.0 per changed node) | 1 | 200x fewer |
| Nodes written | 100 | 100 | unchanged |
| Control family runs | 0 | 0 | unchanged |

The node count is the part that matters as much as the timing: every owner reading a changed peer
still refreshed, so the reduction comes from removing duplicate dispatch rather than from doing less
work. The test asserts this itself, so a faster run that refreshed fewer nodes would fail.

Against the T062 gate: the window improves by 66%, over the 50% floor, and transform executions did
not rise. Both conditions hold at this scale. The 1000-node run is what the 90% success criterion is
actually stated against.


## After, at 1000 changed nodes (T061)

```text
[python-merge-recompute-timing] changed_nodes=1000 control_family_runs=0
CostCenterTiming(merge_critical_path_s=120.98, recompute_window_s=102.13,
                 recompute_flow_runs=4, recompute_nodes_written=1000)
```

| Metric | Before | After | Change |
|---|---|---|---|
| Trailing recompute window | 498.2 s | 102.1 s | -79.5% |
| Recompute flow runs | ~2000 (2.0 per changed node) | 4 | 500x fewer |
| Nodes written | 1000 | 1000 | unchanged |
| Merge critical path | 73.3 s | 121.0 s | **+65%, worse** |

Four submissions rather than one, so the chunk limit engages at this scale as intended and no single
flow-run parameter carries a thousand ids.

## T062 evaluation

The gate reverts the suppression if transform executions exceed the baseline, or if the window
improves by less than 50%.

- Transform executions: 1000 nodes written, the same as before. **Holds.**
- Window: 79.5% better. **Holds.**

The gate passes, so the suppression stays. The 90% target stated in SC-007 is not met: that needed
49.8 s and the run gives 102.1 s.

## A second run, and the retraction it forced

The 1000-node run was repeated with no change at all, to check the critical-path figure before
acting on it.

| Run, feature on | Merge critical path | Recompute window | Flow runs | Nodes written |
|---|---|---|---|---|
| First | 121.0 s | 102.1 s | 4 | 1000 |
| Second | 62.9 s | 88.2 s | 4 | 1000 |
| Recorded baseline | 73.3 s | 498.2 s | ~2000 | 1000 |

**The critical-path regression was not real.** Two identical configurations differ by a factor of
two, and the second run sits below the baseline it was supposed to have regressed against. The
metric carries at least +/-50% variance at this scale on this hardware, so a single sample compared
against a number measured in another session says nothing. The first write-up of this called it a
65% regression, proposed moving the resolution step off the locked path, and was wrong to do either
on one measurement.

**The window improvement is real.** 102.1 s and 88.2 s against 498.2 s, reproduced, with the flow
runs and the node count identical each time. That is a 4.9x to 5.6x improvement on the measure the
success criterion is about, and the effect dwarfs the variance rather than hiding inside it.

What this says about the numbers generally: treat the window and the flow-run count as sound, and
treat any single critical-path figure as indicative only. A claim about the critical path needs
repeated runs, ideally with the switch toggled on the same machine in the same session.

## The regression this exposed

**Retracted; kept for the reasoning, not the conclusion.** The paragraphs below were written from
the first run alone and the second run disproved them. They are left here because the mechanism they
describe is still worth knowing about, not because the effect was observed.

The merge critical path appeared to rise from 73.3 s to 121.0 s. That is the part of the merge that
runs while the global merge lock is held, so it delays every other merge on the instance, and
`plan.md` carries an explicit constraint against unbounded work in that window.

The likely cause is the resolution step. Both of its lookups, deriving the read-field index and the
chunked subscriber query, run inside `dispatch_events`, which the orchestrator calls from inside
`acquire_global_lock()`. At a thousand changed nodes that is real work in the worst possible place.

End to end the feature is still far ahead: 571.5 s of total settle time before, 223.1 s after. But
the trade is not free, and it was not the trade the plan described.

This was confirmed, and it did not hold. The resolution step does still run under the lock, so the
mechanism is real even though the cost was not measurable here; if the critical path ever does become
a problem, moving that step off the locked path is the fix, since the pass needs the change set and
not the lock.


## The switch off, same machine, same session (T060)

Run interrupted before the harness printed, so these are counts read off the live stack. The worker
was confirmed to hold `INFRAHUB_COALESCE_PYTHON_RECOMPUTE_AFTER_MERGE=false` before reading them.

| Flow, whole run at 1000 changed nodes | Switch on | Switch off |
|---|---|---|
| `computed_attribute_process_transform` | 4 for the merge recompute | 2655 |
| `query-computed-attribute-transform-targets` | 0 | 2000 |
| Owners with a computed value | 1000 | 1000 |

Turning the switch off brings the per-node fan-out straight back: two thousand reader-resolution
runs and some two and a half thousand transform runs, against four submissions with it on. The
owners are refreshed either way, which is the point; the difference is entirely in how much work it
takes to get there.

This is FR-021 and US1 AS3 observed rather than asserted. The rollback an operator would reach for
is a setting, it reaches the containers, and it restores the previous behaviour.


## Parity between the two paths (T044)

Run at 50 changed nodes in both modes, each on its own stack, comparing the final stored value of
every owner by name.

| | Owners | Result |
|---|---|---|
| Switch off, per-node path | 50 | recorded |
| Switch on, coalesced pass | 50 | identical, value for value |

This is the check the timing numbers cannot make. They show the coalesced pass is faster and writes
the same *number* of nodes; a merge that refreshed the right count with one stale value among them
would satisfy every other assertion in the suite and fail this one.

The comparison is keyed on node name because each mode needs its own stack, so the ids differ. It
compares the mappings rather than their sizes, and the run skips rather than passes when only one
side has been recorded, so half a run cannot look like a result.


## Dispatch shape on merge and rebase (T041)

Twenty changed nodes, both operations, asserted directly rather than inferred from a timing figure:
fewer transform runs than changed nodes, and all twenty owners refreshed. Both pass.

The rebase arm is the first integration coverage of the rebase wiring. Every other measurement in
this document goes through merge, so FR-003 and US1 AS3 rested on unit and component tests until
now.

The assertion is bounded on both sides. An upper bound alone would pass a pass that dispatched
nothing, which is the failure the widening investigation showed is easy to mistake for success.


## What T042 needs, for whoever picks it up

The cross-family chain test is not a test file on its own. The transform in
`backend/tests/fixtures/repos/computed-attributes-functional` queries `TestingTShirt.name` and
`TestingColor.name` and `description`, all of them plain attributes, so nothing in the current
fixture crosses between the template families and the Python one. The schema has to supply the
crossing.

**Template to Python.** Make `TestingColor.description` a Jinja2 computed attribute, for example
`{{ name__value }} shade`. Editing a colour's name then recomputes its description inline on the
save, the description lands in the write set, and the chain submitter derives the next level, where
`TestingTShirt.pitch` reads that description through the transform query. No fixture repository
change is needed, because the query already reads the field; only its provenance changes.

**Python to template.** Two versions, and they exercise different code:

- Same node: add a Jinja2 attribute on `TestingTShirt` reading `{{ pitch__value }}`. The bulk writer
  loads the whole node and recomputes its own derived values on save, so this settles inline and
  never reaches the chain submitter. Cheap, and it verifies the writer rather than the chain.
- Across a relationship: add a third kind holding a Jinja2 attribute that reads the shirt's pitch
  through a relationship. This is the one that produces a real chained level, and it is the version
  worth writing, because the depth bound and `RecomputeChainSubmitter` only come into play here.

Both directions want the assertion on the final stored value and on the chain depth reached, not
only on the value: a chain that settles by accident, because the same-node cascade did the work,
would pass a value-only assertion while leaving the chained level untested.


## The measurements above hold only for a precise read set

Every number in this document was taken with the fixture transform reading a field on each kind it
touches, so its read set is precise and the pass narrows. Measured in real conditions against a
workload that does not have that property, the branch **regresses**: roughly twenty times more
process runs than the base plus a whole-kind fan-out, and a drain window about three times longer,
for the same set of refreshed readers.

Reproduced in the repository with a second transform that reads the peer's display label, which no
read set can map to backing fields:

```text
[imprecise-read-set] changed_nodes=20 widened=1 batches=42
```

Forty-two batches for twenty changed nodes is 2.1 per node, against a per-node baseline of 2.0. In
this case the coalesced pass does more work than the path it replaces.

The cause is narrower than "widening is too eager". In `_resolve_one` the widen check runs before
anything asks whether the change is relevant, so an imprecise or missing read set refreshes its
whole kind on **every** merge, whether or not that merge touched anything the transform reads. The
subscriber lookup, which would have answered that nobody reads the changed nodes, is never called.

Do not quote the headline numbers without this qualification.


## After the widening fix

Same gate, same scale, on a rebuilt image:

| | Before | After |
|---|---|---|
| Whole-kind widenings | 1 | 0 |
| Merge dispatch batches | 42 | 2 |
| Changed nodes | 20 | 20 |

Two batches for two attributes, which is one per affected pair, with the same readers refreshed.

Two measurement traps this run walked into, both worth knowing before repeating it:

The image has to be rebuilt. A first attempt reported numbers identical to the broken run, because
the stack was still running the previously built image and none of the fix was in it. Identical
numbers after a change are a signal to check what is deployed, not to conclude the change did
nothing.

The counters have to start after the branch edits. Editing twenty peers on a branch is live work
and legitimately fans out per node; counting from before those edits attributes forty runs to the
merge that did not come from it. The first pass at this gate reported 42 for that reason alone,
and only 2 of them were the merge.


## Re-measured after the widening fix (T061, second pass)

Everything above the widening fix was measured on code that no longer exists. Re-taken here.

| 1000 changed nodes, precise read set | Before the fix (two runs) | After |
|---|---|---|
| Recompute flow runs | 4, 4 | 4 |
| Nodes written | 1000, 1000 | 1000 |
| Recompute window | 102.1 s, 88.2 s | 134.8 s |
| Merge critical path | 121.0 s, 62.9 s | 128.3 s |

The run count and the node count are unchanged, which is the result that matters here: the fix
altered only what happens when the read set cannot answer, and this fixture's always can, so the
path that already worked was not disturbed.

The window and the critical path are inside the spread this hardware has already shown on
identical code, 62.9 s to 121.0 s on the critical path alone. One post-fix sample cannot separate a
real change from that spread, and the second run was interrupted. Treat the timing here as
unconfirmed; the run counts stand.

Against the original 498.2 s baseline the window is still roughly 3.7x better.

| Gates, both legs | Result |
|---|---|
| Imprecise read set, 20 changed nodes | widened 0, batches 2 |
| Merge dispatches batches, 20 changed nodes | pass |
| Rebase dispatches batches, 20 changed nodes | pass |

The rebase leg is the one the production report measured as three times slower. It now passes the
same run-count gate as the merge leg.

Still outstanding: a second 1000-node run to put an interval around the window, and the same
comparison against the private scenario that produced the original report.
