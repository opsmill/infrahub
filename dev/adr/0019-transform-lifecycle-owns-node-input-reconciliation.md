# 19. Transform lifecycle flow owns node-input automation reconciliation

**Status:** Accepted
**Date:** 2026-07-31
**Author:** @opsmill-team

**Source:** `specs/archive/ifc-2804-selective-recompute/research.md` (R5)

## Context

The commit trigger that drove Python-transform recompute did two jobs on every commit: the
recompute fan-out, and reconciliation of the data-path (node-input) automations. Those node-input
automations recompute an attribute when a node feeding the transform's query changes, which is a
different axis from the transform-content (fingerprint) change. The schema-change path also
reconciles them, but it fires only on a real schema diff, so it does not cover a transform-only
import.

Removing the commit trigger to scope recompute (see ADR 0018) removes that reconciliation as a
side effect. If nothing takes it over, a transform-only import leaves the node-input automations
unbuilt. A later change to a node feeding the transform's query would then silently fail to
recompute the attribute, leaving a permanently stale value. That is exactly the failure the
over-regenerate-never-under-regenerate invariant forbids.

## Decision

The transform lifecycle flow does two jobs, not one. On a create or an update it runs the
recompute fan-out; on every event, including delete, it runs the data-path reconciliation in a
`finally` block, rebuilding the desired node-input automation set from the existing gather and
applying it. A delete has nothing to recompute, so only the reconciliation runs: its
`to_delete = existing - desired` diff drops the removed transform's node-input automation, so
delete does real teardown rather than being a no-op. The `finally` placement guarantees that a
failing recompute leg never skips the teardown.

## Consequences

### Positive

- No under-regeneration hole: a transform-only import still builds the node-input automations, so
  a later change to a feeding node recomputes.
- More precise than the old sweep. Reconciliation runs on transform events only, not on every
  commit, with the same coverage.
- Delete has an observable teardown: the removed transform's node-input automation is gone from
  the reconciled set.

### Negative

- The lifecycle flow now carries two responsibilities, recompute and reconciliation. They have to
  stay together, or the hole reopens.

### Neutral

- The schema-change path is unchanged; it still reconciles and scoped-recomputes on a schema diff.
- There is no per-transform lifecycle automation to assert on in tests. The observable teardown is
  the node-input automation being absent from the reconciled set after a delete.

## Alternatives Considered

### Drop the reconciliation along with the commit trigger

Rejected. It reopens the under-regeneration hole: a transform-only import would leave the
node-input automations unbuilt and later changes to feeding nodes would silently not recompute.

### Make the delete trigger a no-op

Rejected. It leaves the removed transform's node-input automations in place, so they keep firing
for a transform that no longer exists.
