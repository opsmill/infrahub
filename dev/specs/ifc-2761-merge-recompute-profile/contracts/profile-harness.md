# Contract: Profiling harness (internal)

**Date**: 2026-06-22 · **Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md)

No external (REST/GraphQL) surface. The "contracts" here are the harness entry points and the report format, so the counting and timing layers stay consistent and the findings are reproducible. Per `dev/rules/code-doc-style.md`, shipped source carries no spec IDs.

## 1. Synthetic dataset builder

**File**: `backend/tests/scale/merge_recompute/dataset.py`

```python
def build_profile_schema() -> SchemaRoot: ...
    # one or more kinds carrying a computed attribute, a display label, and an HFID,
    # plus a relationship so cross-node automations are exercised.

async def seed_branch(*, db, branch, changed_nodes: int) -> SeededDataset: ...
    # create `changed_nodes` nodes and mutate them on `branch` so they appear in the merge diff.
    # reuses scale stagers / SDK batch; returns ids and counts needed for assertions.
```

**Guarantees**: `changed_nodes` is the only knob that varies between scales; the schema is constant across scales; seeding is the same for the counting and timing layers (shared, not duplicated).

## 2. Counting layer

**File**: `backend/tests/scale/merge_recompute/test_merge_recompute_counts.py`

Drives a real `merge_branch` / `rebase_branch` with `BusRecorder` and `WorkflowRecorder` injected (no task worker), and returns `RecomputeCounts` per run.

**Guarantees**:
- Counts node events by type — the fan-out cardinality, this layer's primary signal — for both merge and rebase.
- Does **not** observe recompute submissions: on the merge path recompute is dispatched by the event-to-automation engine, not issued synchronously by the merge flow, so it is not visible by intercepting the merge's workflow calls. `WorkflowRecorder` is used only to neutralize the merge's own orchestration workflows. The executed recompute count comes from the timing layer (§3).
- MAY record a derived expected-recompute count by applying the dependency/automation match logic in-process (optional).
- Deterministic: identical `changed_nodes` yields identical counts; the test asserts the expected counts per scale (regression guard). The deterministic test must run where CI collects it (confirm `tests/scale/` is collected, or place it with the component/integration suite).
- Asserts the no-behavior-change invariant: derived values produced by the merge are unaffected by the harness wiring.

## 3. Timing layer

**File**: `backend/tests/integration_docker/test_merge_recompute_timing.py`

Drives the **merge** (the headline path) on the full stack with a real task worker; returns `CostCenterTiming` per run. Rebase wall-clock is deferred (the counting layer covers rebase cardinality).

**Guarantees**:
- Measures the merge critical path with a monotonic clock; sums trailing recompute durations from Prefect flow-run timestamps filtered to this run's recompute deployments and branch/related-node tags. The executed-recompute count (`recompute_flow_runs`) is the authoritative recompute count (FR-004).
- Reports `recompute_window_s` (first recompute start to last finish) separately from the critical path.
- Isolates schema-migration cost by differencing a schema-changing merge against a data-only merge of equal size; attributes the database commit / merge internals best-effort (`db_commit_s` may be `None`).
- Gated (label/timeout, like the intensive benchmarks); reports timings with a stated tolerance and asserts no hard thresholds.

## 4. Findings report

**File**: `dev/specs/ifc-2761-merge-recompute-profile/findings.md` (produced by running the profile)

**Format**: a table of `ProfileRun` rows (operation, scale, changed_nodes, counts, timings) followed by the conclusion — the dominant cost center and the per-metric growth classification (linear / super-linear / flat) — and the tolerance note.

**Guarantees**: enough to choose the coalescing design, or to redirect if the dominant cost is not the per-node fan-out. Reproducible: the counting numbers regenerate exactly; the timing numbers regenerate within tolerance.

## Out of scope

- The coalescing redesign (separate spec, gated on these findings).
- Any change to recompute behavior, events, or automations (measurement only).
- The schema-update backfill path (IFC-2759, closed), the merge correctness gap (IFC-2758), and the transform/git-import axis (IFC-2760).
