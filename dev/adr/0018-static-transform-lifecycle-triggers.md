# 13. Static kind-scoped lifecycle triggers for Python-transform recompute

**Status:** Accepted
**Date:** 2026-07-31
**Author:** @opsmill-team

**Source:** `specs/archive/ifc-2804-selective-recompute/research.md` (R1, R2)

## Context

Python-transform computed attributes were recomputed by a commit trigger that ran a branch-wide
setup flow on every commit. With no changed-element scope, that flow selected and recomputed
every transform-based attribute on the branch, so a change to one transform recomputed all of
them. The goal is to recompute only the attributes fed by the transform whose fingerprint
actually changed.

A per-transform automation model is tempting because it gives free teardown, the way the data-path
automations do: when a definition drops out of the gathered set, the reconciliation deletes its
automation. But gathering one automation per transform means enumerating the transforms, which
needs a database read and a setup flow to run, and that setup flow would have to react to the very
transform create and delete events it is trying to manage. A setup flow chasing its own tail.

## Decision

Replace the commit trigger with three static `BuiltinTriggerDefinition`s, one each for the
transform create, update, and delete lifecycle, each matching `infrahub.node.kind ==
CoreTransformPython`. There is exactly one create, one update, and one delete trigger for the
whole system, not one per transform. The fired flow resolves the changed transform to the computed
attribute(s) it feeds at task time from live schema, then fans out recompute only for those
attributes across all nodes of each attribute's kind, reusing the existing per-attribute recompute
flow. The transform is resolved by both its name and its UUID, because a computed attribute may
wire its transform either way, and an unexpected empty lookup defaults toward recompute rather than
a silent skip.

## Consequences

### Positive

- No per-transform lifecycle automation to create or tear down; deleting a transform never leaves
  a dangling lifecycle automation.
- No branch-wide setup sweep on every commit. Recompute is scoped to the changed transform's
  attributes.
- The transform-to-attributes mapping is resolved against current schema, which is strictly more
  correct than a gather-time snapshot.

### Negative

- The trigger resolves transform to attributes at task time, a cheap in-memory schema lookup,
  where a gathered model would have baked the mapping into the automation's parameters.
- If a single import can both create a transform and separately update its fingerprint, both
  triggers fire; the flow has to guarantee a single recompute on first import.

### Neutral

- Loop safety does not come from an origin filter. A recompute write targets the attribute's own
  node kind and field, never `CoreTransformPython` and `fingerprint`, so it cannot re-fire these
  triggers. The `origin = live` match is kept for a different reason: merge and rebase replay the
  transform's own fingerprint attribute, and those replays would otherwise match.

## Alternatives Considered

### Per-(branch, transform) gathered automations reconciled by a setup flow

Rejected as circular. Gathering one automation per transform requires a setup flow that reacts to
transform create and delete, which are the same lifecycle events the mechanism is meant to handle.
Static kind-scoped triggers break the cycle: three fixed automations match every transform, and
the per-transform resolution moves to task time.

### Parameterize the existing branch-wide setup flow with a per-transform mode

Rejected on single-responsibility grounds. That flow already couples a branch-wide scoped
recompute with the data-path automation reconciliation behind a changed-elements scoper. A
single-transform mode would tangle single-transform recompute with branch-wide scoping in one
flow. A small, separate lifecycle flow is independently testable.
