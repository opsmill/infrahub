# Quickstart & Validation Scenarios: Coalesce merge and rebase recompute

**Date**: 2026-06-26 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Validate correctness first (no stale values, on the correct branch), then performance (recompute bounded by affected derived values). The profiling harness from the first task is the before/after yardstick. Rebase the branch onto current develop before implementing (research R9).

## Run

```bash
uv sync --all-groups

# Selection logic (pure; graph DB via testcontainers; no worker)
uv run pytest backend/tests/component/merge_recompute_coalescing -q

# End-to-end correctness on the full stack (real worker)
uv run pytest backend/tests/integration_docker/test_merge_recompute_coalescing.py -q

# Performance, before vs after, using the first task's harness (gated, on demand)
INFRAHUB_PROFILE_TIMING=1 INFRAHUB_TESTING_IMAGE_VER=local-dev INFRAHUB_PROFILE_SCALE=1000 \
  uv run pytest backend/tests/integration_docker/test_merge_recompute_timing.py -q -s
```

## Validation scenarios

### A. No stale values, cross-node update (P1, FR-001/002, SC-003)
Merge a branch that changes nodes other nodes read; every reader's computed attribute and display label match a from-scratch recompute.

### B. No stale values, creation (P1, FR-005, SC-003)
Merge a branch that creates nodes; each new node's computed attribute, display label, and human-friendly id match a full recompute.

### C. Transitive dependency (P1, FR-002, SC-003)
A value that reads a node that reads the changed node is consistent after merge.

### D. Reader of a deleted node (edge, FR-013, SC-003)
Merge a branch that deletes a node others read; the readers are recomputed so their values no longer reflect the deleted node.

### E. Coalescing / no duplicate work (P1, FR-003/004, SC-001)
Many changed nodes affecting the same target recompute it once; recompute job count is bounded by affected derived values, not changed-node count times automations (measured with the harness); readers are resolved by one query over the union, not one per changed node.

### F. No double processing (FR-008)
Each affected derived value is recomputed by exactly one path; the cross-node automations do not also fire for the merge's changes.

### G. Branch difference (FR-014)
A merge recomputes on the destination branch; a rebase recomputes on the user branch. Verify the recompute lands on the correct branch for each operation and not the other.

### H. Source-branch redundancy (research R5, FR-015)
With default (recompute-all) behavior, readers that exist only on the destination branch are recomputed and correct. If a skip optimization is added, prove via the trace that skipped readers were already correctly recomputed on the source branch; never leave a stale value.

### I. Performance at scale (P1, FR-011, SC-002)
Run the harness before and after at the large scale (~1000 changed read-targets); the trailing recompute window drops by a large margin versus the baseline (~11 min); merged data identical.

### J. No small-graph regression (P3, FR-009, SC-004)
A small merge (~10 changed nodes) is no slower than baseline within tolerance.

### K. Rebase parity (P2, FR-006, SC-005)
The same change via rebase shows the coalescing and the correctness guarantee, on the user branch.

## Definition of done

- Correctness A-D, G, K green on the full stack against a from-scratch recompute oracle, on the correct branch per operation.
- Coalescing E-F verified (single recompute per target; one union reader query; no double processing).
- Redundancy H: default recompute-all correct; any skip optimization backed by the trace.
- Harness shows the I reduction and the J no-regression; merged data identical (behavior-preserving).
- Existing recompute tests stay green (`backend/tests/integration_docker/test_computed_attributes.py`, `test_display_label_backfill.py`).
- `uv run invoke format lint` clean; `mypy` clean on new files. No generated-file edits, no new dependencies.
- A changelog fragment is required (user-facing performance change); confirm wording against project convention when opening the PR.
- Branch rebased onto current develop so the integration points (`core/merge/post_merge.py`, the Jinja2 loop) are the real ones.
