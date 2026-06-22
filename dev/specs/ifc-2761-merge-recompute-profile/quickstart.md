# Quickstart & Validation Scenarios: Profile merge and rebase recompute cost

**Date**: 2026-06-22 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

How to run the two layers and the scenarios that validate them. "Counting layer" = deterministic, graph DB only. "Timing layer" = full stack, on demand.

## Run

```bash
uv sync --all-groups

# Counting layer (deterministic; graph DB via testcontainers; no task worker)
uv run pytest backend/tests/scale/merge_recompute/test_merge_recompute_counts.py -q

# Timing layer (full distributed stack + real task worker; on demand, long)
uv run pytest backend/tests/integration_docker/test_merge_recompute_timing.py -q
# (gated like intensive benchmarks: long timeout, run explicitly, not in normal CI)

# Regression guard the harness must not disturb
uv run pytest backend/tests/integration_docker/test_computed_attributes.py backend/tests/integration_docker/test_display_label_backfill.py -q
```

## Validation scenarios

### A. Counts at a single scale (P1, FR-003)
- **Given** a branch seeded with K changed nodes across kinds carrying computed attributes, display labels, and HFIDs,
- **When** the counting layer merges it,
- **Then** it reports node events by type (the fan-out cardinality) and asserts the expected counts for K; recompute is Prefect-dispatched and not counted here (it is observed as executed runs in the timing layer). An optional derived expected-recompute count MAY also be reported.

### B. Growth across scales (P1, FR-006/007, SC-002)
- **Given** runs at ~10, ~100, ~1000+ changed nodes,
- **When** results are compared,
- **Then** the report shows node events (and any derived expected-recompute) per scale and classifies growth (linear vs super-linear) against changed-node count.

### C. Wall-clock attribution (P1, FR-004/005/008, SC-001/003)
- **Given** a merge on the full stack at the medium (~100 changed nodes) scale,
- **When** the timing layer runs,
- **Then** it reports merge critical-path time, executed recompute count, trailing recompute total and window, (by differencing) schema-migration cost, best-effort DB-commit time, and names the dominant cost center.

### D. Critical path vs degraded window (edge, FR-008)
- **Given** the timing run,
- **Then** `recompute_window_s` (first recompute start to last finish) is reported separately from the in-transaction merge time, so the ~20-minute degraded-instance window is distinguished from the merge call itself.

### E. Merge vs rebase (edge)
- **Given** the same dataset,
- **When** both a merge and a rebase are profiled,
- **Then** both are reported; if they differ materially, the report says so.

### F. Schema-changing vs data-only merge (edge)
- **Given** a data-only merge and a schema-changing merge of equal size,
- **Then** the difference attributes the schema-migration cost, keeping it separate from the per-node fan-out.

### G. Determinism / reproducibility (P2, SC-004)
- **Given** the counting layer re-run at the same scale,
- **Then** it reproduces identical counts; the timing layer reproduces within the stated tolerance.

### H. No behavior change (FR-010, SC-005)
- **Given** a merge driven through the harness,
- **Then** the derived values produced are identical to a merge without the harness wiring, and the existing recompute tests stay green.

## Definition of done

- Counting layer green and deterministic at three scales; growth classified.
- Timing layer produces a cost attribution at a representative scale on the full stack.
- `findings.md` written: per-scale table, dominant cost center, growth classification, tolerance note.
- Regression + no-behavior-change guards green.
- `uv run invoke format lint` clean; `mypy` clean on new files. No generated-file edits, no new dependencies.
- A changelog fragment is **not** required (test/measurement-only, no user-facing change) — confirm against project convention when opening the PR.
