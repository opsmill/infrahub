# Phase 1 Data Model: Profile merge and rebase recompute cost at scale

**Date**: 2026-06-22 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

No persisted (Neo4j) model changes. These are in-memory measurement records (frozen dataclasses, Constitution III) produced by the harness and serialized into the findings report. The seeded graph data is synthetic and transient.

## Records

### `RecomputeCounts` (counting layer)

```python
@dataclass(frozen=True)
class RecomputeCounts:
    changed_nodes: int                      # the independent variable for this run
    node_events: dict[str, int]             # event type ("created"/"updated"/"deleted") -> count (the fan-out driver)
    expected_recompute: dict[str, int]      # OPTIONAL derived: family -> predicted recompute targets, from applying the match logic in-process
    # convenience totals
    total_node_events: int
    total_expected_recompute: int           # 0 if the derived prediction is not computed
```

`node_events` (by type) is the counting layer's primary, always-recorded signal: it is the fan-out cardinality that drives recompute. `expected_recompute` is an optional in-process prediction (apply the dependency/automation match logic to the emitted events) bucketed per derived-value family (computed attribute, display label, HFID). The counting layer does **not** record actual recompute submissions: on the merge path those are dispatched by the event-to-automation engine, not issued synchronously by the merge flow, so they are not observable by intercepting the merge's own workflow calls. The **executed** recompute count lives in `CostCenterTiming.recompute_flow_runs` (timing layer).

### `CostCenterTiming` (timing layer)

```python
@dataclass(frozen=True)
class CostCenterTiming:
    merge_critical_path_s: float            # synchronous, in-transaction merge time
    schema_migration_s: float | None        # None for a data-only merge
    db_commit_s: float | None                # where finer attribution is available
    recompute_total_s: float                 # summed durations of trailing recompute flow runs
    recompute_window_s: float                # first recompute start to last finish (degraded-instance window)
    recompute_flow_runs: int                 # number of recompute flow runs observed
```

### `ProfileRun` (one merge or rebase at one scale)

```python
@dataclass(frozen=True)
class ProfileRun:
    operation: str                          # "merge" | "rebase"
    scale_label: str                        # e.g. "small" | "medium" | "large"
    changed_nodes: int
    schema_changing: bool                    # data-only vs schema-changing merge
    counts: RecomputeCounts | None           # from the counting layer
    timing: CostCenterTiming | None          # from the timing layer (on-demand)
    tolerance_note: str                      # run-to-run variance statement for timings
```

### `FindingsReport` (aggregate, serialized to findings.md)

```python
@dataclass(frozen=True)
class FindingsReport:
    runs: list[ProfileRun]
    dominant_cost_center: str               # the conclusion
    growth_classification: dict[str, str]    # metric name -> "linear" | "super-linear" | "flat"
    notes: str
```

## Relationships

```text
synthetic dataset (N changed nodes, kinds with computed attr + display label + HFID)
        │
        ├── counting layer  (merge/rebase + BusRecorder, no worker; WorkflowRecorder neutralizes the merge's own orchestration workflows)
        │        └── RecomputeCounts  (node events by type [primary]; optional derived expected-recompute by family)
        │
        └── timing layer    (merge on full stack + real worker)
                 └── CostCenterTiming  (critical path, migration, best-effort commit, executed recompute runs + window)
                              │
                              ▼
        runs across scales ──► ProfileRun[] ──► FindingsReport ──► findings.md
```

## Invariants / validation

- `changed_nodes` is the independent variable; every metric is reported against it across at least three scales.
- Counting-layer metrics are deterministic: the same scale yields the same counts run to run (asserted).
- Timing-layer metrics are stack-relative: reported with a tolerance, never asserted as hard thresholds.
- `recompute_window_s` (first start to last finish) is reported separately from `merge_critical_path_s` so the degraded-instance window is distinguished from the in-transaction cost (FR-008).
- Producing these records must not change recompute output (FR-010): the harness is read-only with respect to recompute behavior.
