# 12. Selective post-merge regeneration driven by the captured merge diff

**Status:** Accepted
**Date:** 2026-07-31
**Author:** @opsmill-team

**Source:** `specs/archive/ifc-2704-incremental-merge-regen/research.md` (D1, D2, D4, D6, D7, D9) and
that spec's `spec.md` (FR-001, FR-008, FR-010, FR-012, SC-001).

## Context

On merge, the follow-up re-ran every generator and regenerated every artifact for every group member
regardless of what the merge changed (the blanket path). On a real dataset this spawned thousands of
background tasks and left the instance effectively unusable for roughly twenty minutes after each
merge (originating incident IFC-2306).

The enriched branch diff that records what a merge changed is available at merge time but
unrecoverable afterward: the freeze marks the diff root merged and rewrites its tracking id, and the
field-summary queries exclude merged roots. The proposed-change pipeline already had
definition-level selection predicates and member-impact analysis, but they were written for a live
source branch, an artifact-id-space comparison, and live-group iteration for new members, none of
which transfer unchanged to a diff-only, member-id-filtered, post-merge target-branch context.

## Decision

Replace the two blanket post-merge triggers with a selective path, gated by
`selective_execution_after_merge` (default on; off restores the blanket path byte-for-byte).

Capture the enriched diff in the merge orchestrator before the freeze, serialized into the SDK
`NodeDiff` summary shape the existing predicates already consume, tagged with the target
(destination) branch, and cache it under a merge-scoped key derived from the stable diff-root uuid.
Thread only that key through the follow-up. The capture is best-effort and split around the merge's
point of no return, so a rolled-back merge writes nothing and a capture failure degrades to the
blanket fallback rather than failing the merge.

In the follow-up, reuse the definition-level gates and member-impact analysis (extracted to a shared
package serving both the proposed-change and merge callers) to select only affected definitions,
reconciled against the live target-branch group so that new members and membership-only additions are
covered. Selection is governed by the over-execution invariant inherited from INFP-409: whenever the
affected set cannot be determined with confidence, the path regenerates everything for that merge.
Every fallback and the flag-off path route to the exact blanket behavior.

The end-to-end flow, selection, cascade, and fallback reasons are documented in
[Selective Merge Regeneration](../knowledge/backend/selective-merge-regeneration.md).

## Consequences

### Positive

- Dispatched-task count drops from proportional to (all definitions x all members) to proportional
  to the affected set, so the instance stays responsive after a merge.
- One selection implementation serves both the proposed-change and merge paths.

### Negative

- A composite artifact that inlines another artifact's rendered content is no longer refreshed on
  merge (the diff carries no inlining edge), a behavior regression now that the flag defaults on.
- Correct new-member coverage requires bounded per-selected-definition group and subscriber fetches,
  so the "no new hot-path Cypher" property holds only at the definition level.
- The direct-merge generator-to-artifact cascade must await generators and capture their output,
  because no event machinery regenerates artifacts on generator-produced data mutations.

### Neutral

- A per-merge line records whether the merge took the selective or a named fallback path, with the
  dispatched generator and artifact counts, so silent under-execution is observable.

## Alternatives Considered

### Recompute the diff after the merge

Rejected. The freeze makes the recomputed diff return an empty set, causing under-execution.

### Reuse the changelog collector's node set

Rejected. It drops nodes whose only change was a conflict resolved to the base branch, also
under-execution.

### Derive the member filter from the diff alone

Rejected. It cannot enumerate a newly added member or a membership-only change, so member selection
reconciles against the live group instead.

### Dispatch a concurrent full-artifact regeneration for the generator cascade

Rejected. It races the generators' writes and renders artifacts against pre-generator state, so the
cascade sequences artifact regeneration after generator completion.
