# Feature Specification: Incremental generator & artifact execution on merge

**Feature Branch**: `incremental-merge-regen-ifc-2704`

**Created**: 2026-07-10

**Status**: Draft

**Input**: IFC-2704 — "Make generator and artifact execution incremental on merge"

## Overview

When a branch is merged, Infrahub currently re-runs **every** generator and regenerates
**every** artifact regardless of what the merge actually changed. On a real dataset this
spawns thousands of background tasks and leaves the instance effectively unusable for
roughly twenty minutes after each merge (originating report: IFC-2306).

This feature makes post-merge execution **selective**: only the generators and artifacts
whose inputs are affected by the merge diff are run. The guiding safety rule, inherited
from the regeneration-trigger work, is that **over-execution is acceptable but
under-execution is not** — whenever the affected set cannot be determined with confidence,
the system regenerates everything rather than risk leaving a stale artifact.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Selective regeneration on merge (Priority: P1)

An operator merges a branch that changed a small number of objects. Only the artifacts and
generators whose inputs depend on those changed objects are recomputed, and only for the
affected group members. The instance stays responsive; the background-task storm is gone.

**Why this priority**: This is the core value of the feature and the direct fix for the
originating incident. Without it, nothing else matters.

**Independent Test**: Merge a branch that modifies one object of one kind, and confirm that
only definitions whose inputs include that kind are dispatched, scoped to the affected
member(s), while unrelated definitions and members are not dispatched at all.

**Acceptance Scenarios**:

1. **Given** a branch that changed a single object of a single kind, **When** it is merged,
   **Then** only definitions whose inputs include that kind are dispatched, and only for the
   affected member(s).
2. **Given** a branch that changed nothing relevant to any generator or artifact definition,
   **When** it is merged, **Then** no generator runs and no artifact is regenerated.
3. **Given** a branch merged through a proposed change **and** a branch merged directly (no
   proposed change), **When** each is merged, **Then** both take the selective path and
   produce the same affected-set decision for the same underlying diff.

---

### User Story 2 - Repository code changes still regenerate correctly (Priority: P2)

A developer changes a transform, GraphQL query, or generator file on the branch. On merge,
the definitions that depend on that code are regenerated even though the change is in
repository files rather than in graph data. A change that is later fully reverted on the
same branch regenerates nothing.

**Why this priority**: Repository-code changes are a primary reason artifacts go stale.
Missing them would be under-execution — the one failure mode the feature must never exhibit.

**Independent Test**: Merge a branch containing a transform-file change and confirm the
affected definitions regenerate; separately, merge a branch that edits then reverts the same
file and confirm nothing regenerates.

**Acceptance Scenarios**:

1. **Given** a branch that modified a transform file feeding an artifact definition,
   **When** it is merged, **Then** that artifact definition is regenerated for its members.
2. **Given** a branch that edited a repository file and then reverted it to its original
   content, **When** it is merged, **Then** no regeneration is triggered by that file.
3. **Given** a query or definition edited directly through the API (not through a repository
   import), **When** the branch is merged, **Then** the dependent definitions are still
   regenerated.

---

### User Story 3 - Safe fallback to full regeneration (Priority: P1)

When the system cannot determine the affected set with confidence — the diff is
unavailable, code fingerprints have not yet been populated, or the dependency information
is incomplete — it falls back to regenerating everything for that merge rather than risk
skipping an affected artifact.

**Why this priority**: The no-under-execution invariant is a correctness guarantee, equal in
importance to the performance win. A selective path with unsafe gaps would be worse than the
current behavior.

**Independent Test**: Force each fallback condition (missing captured diff, unpopulated
fingerprints, incomplete dependency closure) and confirm the merge falls back to full
regeneration with no affected artifact left stale.

**Acceptance Scenarios**:

1. **Given** the captured merge diff is unavailable when follow-up runs, **When** the merge
   completes, **Then** the system regenerates all definitions and members (current blanket
   behavior).
2. **Given** a repository whose code fingerprints have not been populated (pre-existing
   data) **and** a repository code change in the merge, **When** the merge completes,
   **Then** all definitions of that repository are regenerated.
3. **Given** incomplete dependency information for a definition, **When** the merge
   completes, **Then** that definition is regenerated rather than skipped.

---

### User Story 4 - Reversible rollout via configuration (Priority: P3)

An operator can turn the selective behavior off, restoring the previous full-regeneration
behavior, without a code change — for establishing a performance baseline, for scale
testing, or to roll back if a problem is discovered.

**Why this priority**: Enables safe rollout and a measurable baseline, but the feature
delivers value without operators ever touching the flag.

**Independent Test**: Toggle the configuration flag and confirm that the disabled setting
reproduces the previous full-regeneration behavior and the enabled setting takes the
selective path.

**Acceptance Scenarios**:

1. **Given** the selective-merge configuration flag is disabled, **When** a branch is
   merged, **Then** all generators run and all artifacts regenerate as before this feature.
2. **Given** the flag is enabled, **When** a branch is merged, **Then** the selective path is
   taken.

---

### Edge Cases

- **New target with no existing artifact**: A merge that adds a new member to a group must
  regenerate for that new member, even though it has no prior artifact to key off of.
- **Conflict resolved to the base branch**: A node whose only change on the branch was a
  conflict resolved in favour of the base branch is still a real change for regeneration and
  must remain in the affected set.
- **Generator output feeding artifacts on a direct merge**: Generators that run after a
  direct merge mutate default-branch data whose downstream artifacts are not part of the
  original merge diff; those dependent artifacts must still be regenerated (no
  under-execution) — see FR-011 and Assumptions.
- **Repository merge ordering**: Repository code is merged and re-imported on the default
  branch before follow-up runs; that re-import must not cause a second, redundant
  regeneration of the same definitions.
- **Relationship and membership-only changes**: A change that only adds/removes a
  relationship or group membership must be represented in the affected set.
- **Deleted target orphans a generator instance**: When a merge deletes an object that was a
  generator's target, its leftover generator instance no longer resolves to a target; the
  follow-up must skip that orphan and still run the generator for the live members rather than
  fail the whole run.
- **A generator run fails during the follow-up**: A single generator failure must not abort the
  other generators or discard the narrowing already computed; the failure regenerates all
  artifacts (so no consumer is left stale) without re-running the generators.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: On merge, the system MUST run only the generators and regenerate only the
  artifacts whose inputs are affected by the merge diff, scoped to the affected group
  members.
- **FR-002**: The affected set MUST be derived from the enriched branch diff as it exists
  **before** the merge is finalized; the system MUST NOT attempt to retrieve or recompute the
  diff after the merge has completed.
- **FR-003**: The affected set MUST include every changed node regardless of how the change
  was resolved, including nodes whose only change was a conflict resolved in favour of the
  base branch.
- **FR-004**: A repository code change (transform, GraphQL query, generator, or definition)
  present on the branch MUST cause regeneration of the definitions that depend on that code.
- **FR-005**: A repository code change that is fully reverted on the same branch (net-zero
  change) MUST NOT cause regeneration.
- **FR-006**: A query or definition modified directly through the API (not via a repository
  import) MUST still cause regeneration of the dependent definitions.
- **FR-007**: A merge that adds a new member to a group MUST regenerate the affected
  definitions for that new member, even when no artifact exists yet for that member.
- **FR-008**: When the affected set cannot be determined with confidence — including but not
  limited to an unavailable captured diff, unpopulated code fingerprints combined with a
  repository code change, or incomplete dependency information — the system MUST fall back to
  full regeneration for that merge.
- **FR-009**: Selective execution MUST apply to both direct branch merges and merges
  performed through a proposed change, producing the same affected-set decision for the same
  underlying diff.
- **FR-010**: The system MUST NOT under-execute: every artifact or generator whose output
  depends on a changed input MUST be regenerated. Over-execution (regenerating more than
  strictly necessary) is acceptable.
- **FR-011**: Data mutated by generators that run as part of the merge follow-up MUST NOT
  cause the artifacts depending on that data to be left stale. Such artifacts MUST be
  regenerated by capturing the generators' output — scoped to the members each generator
  tracks — and selecting the artifacts that read it, widening to all artifacts whenever that
  output cannot be captured or selected.
- **FR-012**: The selective behavior MUST be controllable through a configuration flag so
  that operators can disable it to restore the previous full-regeneration behavior for
  baseline measurement or rollback.
- **FR-013**: Replacing the current post-merge trigger path MUST NOT change the behavior of
  any other caller of generator or artifact regeneration outside the merge follow-up.

### Key Entities *(include if feature involves data)*

- **Merge diff (affected set)**: The set of nodes changed by the merge, each with its kind,
  the action applied (added / updated / removed, including relationship and membership
  changes), and which of its elements changed. This is the single source of truth for
  selection.
- **Artifact definition**: A definition that, combined with a group of target members,
  produces artifacts. Selected for regeneration when its inputs (data kinds, query, or
  code) are in the affected set.
- **Generator definition**: A definition that runs generation logic against target members.
  Selected to run when its inputs are in the affected set; further filtered by whether it is
  configured to execute after merge.
- **Group member (target)**: An individual object that an artifact/generator definition
  produces output for. Selection narrows execution to only affected members.
- **Code fingerprint**: A content-derived signal on transform/query/generator/definition
  objects that appears as an ordinary changed element in the diff when the underlying code
  changed, letting repository-code changes be detected from the diff without a separate
  file-level comparison.
- **Selective-merge configuration flag**: Operator-facing switch that enables or disables
  selective post-merge execution.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a merge that changes a single object of a single kind, the number of
  post-merge generator/artifact tasks dispatched is proportional to the affected definitions
  and members only — not to the total number of definitions and members in the instance.
- **SC-002**: After a small merge, the instance remains usable throughout the follow-up
  (no multi-minute period of unresponsiveness attributable to post-merge regeneration).
- **SC-003**: Zero under-execution across the test matrix: in every scenario where an
  artifact or generator depends on a changed input, it is regenerated (measured by a
  reproducible test suite covering single-kind changes, new targets, conflict-resolved-to-
  base, repository-code changes, and the fallback conditions).
- **SC-004**: A recorded before/after comparison of dispatched-task count on a representative
  dataset demonstrates a substantial reduction for typical small merges, with the flag
  disabled reproducing the prior full-regeneration count as the baseline.
- **SC-005**: An edit-then-revert of repository code on a branch dispatches zero regeneration
  tasks on merge.

## Assumptions

- **Config flag default**: The selective path ships **enabled by default**. The
  comprehensive fallback-to-full-regeneration behavior (FR-008) preserves the
  no-under-execution guarantee even when enabled, and the originating bug is severe enough
  that shipping the fix disabled would leave the problem unaddressed. The flag exists
  primarily to establish a baseline and to allow rollback. (Autonomous decision; revisit if
  scale testing surfaces a correctness gap.)
- **Fingerprint availability**: Code fingerprints only exist after a repository import on the
  branch (delivered by the fingerprint foundation work, IFC-2844 / PR #9778). The design
  must not assume fingerprints are populated; absent fingerprints combined with a repository
  code change take the full-regeneration fallback (FR-008).
- **Generator-output cascade (resolved)**: For merges via a proposed change the branch diff
  already reflects generator output. For direct merges, generators that execute after merge
  mutate default-branch data whose dependent artifacts are not in the original merge diff. The
  shipped design awaits each after-merge generator, captures the nodes those generators wrote
  (scoped to the members each generator tracks), and regenerates only the artifacts that read
  that output. It widens to regenerating every artifact when the tracked output cannot be
  captured or a generator's tracked set is unresolved, and regenerates all artifacts — without
  re-running the generators — if a generator run fails (FR-011).
- **Scope of replacement**: Only the two post-merge trigger submissions are replaced. They
  are not invoked anywhere else, so other regeneration callers (proposed-change pipeline,
  manual regeneration) are unaffected (FR-013).
- **Diff capture point**: The enriched branch diff is captured in the merge orchestrator at
  the point it is already loaded for changelog event collection, before the diff root is
  marked merged/frozen.
- **Dependencies**: This feature depends on the fingerprint foundation (IFC-2844 / PR #9778)
  and reuses the regeneration-selection predicates and dependency-closure analysis from the
  proposed-change regeneration-trigger work (IFC-2738 / PR #9700). It implements the product
  intent captured in INFP-607 and follows the over-execution-over-under-execution invariant
  from INFP-409.

### Revision: Implementation Sync 2026-07-16

- Reason: recorded the validation status of the success criteria. SC-001, SC-004, and SC-005 are
  validated on the representative dataset (`perf-validation.md` retest: flag off reproduces the
  blanket baseline, selective scales with the affected set, a net-zero change dispatches nothing),
  and SC-003 (no under-execution) held across the executed scenarios. SC-002 (no multi-minute
  unresponsive window at scale) is not yet validated — deferred pending the profiling-harness
  scale dataset.

### Revision: Implementation Sync 2026-07-24

- Reason: reconciled the generator-output cascade to the shipped design. The direct-merge cascade
  regenerates only the artifacts that read a generator's tracked output (FR-011) instead of every
  artifact; the blanket path is now the fallback for an unresolved tracked set or a capture
  failure. Recorded two edge cases surfaced during implementation — a deleted target orphaning a
  generator instance, and isolation of a single generator run failure. The open "generator-output
  cascade" assumption is now marked resolved. The config flag ships enabled by default (the
  Assumptions default was reached once the fallbacks landed).
