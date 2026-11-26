# Feature Specification: Selective regeneration of transform-based computed attributes on git updates

**Feature Branch**: `selective-recompute-ifc-2804`

**Created**: 2026-07-16

**Status**: Extracted

**Input**: Jira epic IFC-2804 - "Recompute a Python transform-based computed attribute only when the transform that feeds it actually changed, instead of on every commit to any linked repository". First consumer of the definition fingerprint foundation (IFC-2844).

## Overview

Today, a commit to any linked Git repository triggers a recompute of **every** Python transform-based computed attribute, for **every** node of each attribute's kind, whether or not the commit touched anything that feeds that attribute. The commit event carries no diff, so the recompute scoper cannot tell what changed and falls back to "recompute everything", then fetches all nodes of each kind. A README edit, an unrelated helper module, or a change to a completely different transform all trigger the same full recompute sweep.

This feature replaces the commit-event-driven trigger for Python transform computed attributes with triggers on the **transform's own lifecycle**, using the branch-aware `fingerprint` attribute delivered by IFC-2844 as the change signal:

- A newly imported transform (**created**) drives the initial setup and first computation of the attribute(s) tied to it.
- A transform whose `fingerprint` changes (**updated**) recomputes **only** the attribute(s) that transform feeds, across all nodes of each attribute's kind.
- A deleted transform (**deleted**) reconciles away the node-input recompute automations tied to it, so nothing keeps firing for a transform that no longer exists.

The transform lifecycle also owns a second duty inherited from the removed commit trigger: reconciling the **node-input recompute automations**. These are a separate axis from the content (fingerprint) change this feature scopes. A node-input recompute automation refreshes a computed attribute when a **node feeding the transform's query** changes, not when the transform's own content changes. On every lifecycle event (create / update / delete) the flow rebuilds or refreshes these automations, so a transform-only import (which does not change the schema) never leaves them unbuilt or orphaned.

Because the fingerprint is a content hash of everything that determines a transform's output, an unchanged fingerprint means the output cannot have changed, so the recompute can be skipped. When a fingerprint changes, only the attributes fed by that one transform recompute. The narrowing is from "every transform's attributes on every commit" to "only the changed transform's attributes".

This feature covers **only** Python transform-based computed attributes (`TRANSFORM_PYTHON`). USER-kind attributes are entered by hand and never derived. JINJA2-kind attributes render from inline schema templates, are git-independent, and already skip via an existing `template_hash` check.

### Non-negotiable invariant (inherited from IFC-2844 / INFP-409)

**Over-regeneration is acceptable; under-regeneration is not.** A computed attribute that should recompute but does not leaves stale data in production. Every fallback and error path in this feature MUST default toward recompute, never toward skipping. Concretely: a null fingerprint (a pre-feature transform not yet re-imported) means "unknown" and MUST be treated as changed; a transform with no `watch` declaration keeps per-commit recompute behaviour (scoped to its own attributes only); any indeterminate or error state recomputes. This invariant governs every requirement and success criterion below.

## User Scenarios & Testing *(mandatory)*

The "users" of this feature are (a) operators who maintain schemas with Python transform-based computed attributes and whose unrelated commits should stop triggering needless dataset-wide recomputes, and (b) operators who edit a transform and expect exactly the attributes it feeds to refresh, no more and no fewer. Each user story is an independently deliverable and testable slice.

### User Story 1 - An unrelated commit triggers no recompute (Priority: P1)

An operator commits a change to a linked repository that does not touch anything feeding a given Python transform computed attribute (for example, a README edit, an unrelated helper module, or a change to a different transform). That attribute is not recomputed and no recompute jobs are queued for it.

**Why this priority**: This is the reported defect and the whole reason for the feature. Today any commit to any linked repository recomputes every transform-based computed attribute for every node of its kind. On large datasets this is slow, wasteful, and buries the work that actually matters.

**Independent Test**: On a branch with several Python transform computed attributes whose transforms declare a `watch`, commit and import a change that touches no input of any of them. Verify zero recompute jobs are produced for those attributes.

**Acceptance Scenarios**:

1. **Given** a Python transform computed attribute whose transform declares a `watch` and has a stored fingerprint, **When** a commit changes only a file that is not in that transform's dependency closure and the repository is imported, **Then** the transform's fingerprint is unchanged, no update event fires for it, and the attribute is not recomputed.
2. **Given** two Python transforms A and B feeding two different computed attributes, **When** a commit changes only an input of transform A and the repository is imported, **Then** only attribute A's fingerprint changes and only attribute A is recomputed; attribute B is not recomputed.
3. **Given** a repository whose commit touches only documentation or unrelated files, **When** the repository is imported, **Then** no transform fingerprint changes and no transform-based computed attribute is recomputed.

---

### User Story 2 - A transform change recomputes only the attributes it feeds (Priority: P1)

An operator changes a transform - its query, a file in its dependency closure, its own source, or an output-affecting manifest field. On the next import, exactly the computed attribute(s) that transform feeds are recomputed, across all nodes of each attribute's kind. Attributes fed by other transforms are untouched.

**Why this priority**: Scoping must not sacrifice correctness. When a transform's output-determining inputs change, every node's value for the attributes it feeds may change, so all instances of those attributes must recompute. But only those attributes - not every transform-based attribute on the branch.

**Independent Test**: Define two Python transform computed attributes fed by two different transforms. Change one input of the first transform, import, and verify the first attribute is recomputed for all nodes of its kind while the second attribute is not recomputed at all.

**Acceptance Scenarios**:

1. **Given** a Python transform feeding a computed attribute on type A, **When** the transform's connected query changes and the repository is imported, **Then** the transform's fingerprint changes, an update event fires, and the attribute is recomputed for every node of type A.
2. **Given** the same transform, **When** a file in its dependency closure (including its own source file) changes and the repository is imported, **Then** the transform's fingerprint changes and the attribute is recomputed for every node of type A.
3. **Given** the same transform, **When** an output-affecting manifest field of the transform changes and the repository is imported, **Then** the fingerprint changes and the attribute is recomputed.
4. **Given** a transform that feeds more than one computed attribute, **When** its fingerprint changes, **Then** every attribute it feeds is recomputed and no attribute fed by a different transform is recomputed.

---

### User Story 3 - An edit followed by its revert triggers no recompute (Priority: P1)

An operator changes a transform and then reverts it to identical content across separate commits. Because the fingerprint is content-derived, the reverted state hashes to the same value it started at, so no net change is seen and no recompute happens for the revert.

**Why this priority**: This proves the change signal is content-based, not commit-based. It is the clearest demonstration that no-op churn stops driving work, and it directly protects against the over-recompute the feature exists to remove.

**Independent Test**: Import a transform (fingerprint stored). Change its content and import (fingerprint changes, one recompute). Revert the content to the original bytes and import. Verify the fingerprint returns to its original value and no recompute is triggered by the revert import.

**Acceptance Scenarios**:

1. **Given** an imported transform with a stored fingerprint, **When** its content is edited and later reverted to identical content, with each state imported, **Then** the revert import produces a fingerprint equal to the original and no update event fires for the revert.
2. **Given** the revert import, **When** it completes, **Then** no recompute job is queued for the attribute(s) that transform feeds as a result of the revert.

---

### User Story 4 - A transform without a `watch` keeps per-commit recompute, scoped to its own attributes (Priority: P2)

A transform that declares no `watch` cannot be trusted to have a complete auto-detected dependency closure, so its fingerprint folds in the commit id and changes on every commit (the IFC-2844 safe default). This feature honours that: such a transform still recomputes on every commit, but the recompute is scoped to only the attribute(s) that one transform feeds, not every transform-based attribute on the branch.

**Why this priority**: This is the correctness floor for the invariant. A no-watch transform must never be starved of recomputes, because its closure may silently miss a dependency. But even in this conservative case, the feature still delivers value: it stops the change from fanning out to unrelated attributes.

**Independent Test**: Define two Python transform computed attributes, one fed by a no-watch transform and one fed by a watch-declared transform. Commit an unrelated change and import. Verify the no-watch attribute is recomputed (per-commit safe default) while the watch-declared, unaffected attribute is not.

**Acceptance Scenarios**:

1. **Given** a Python transform with no `watch` declaration, **When** any commit is made and the repository is imported, **Then** the transform's fingerprint changes (commit id folded in), an update event fires, and the attribute(s) it feeds are recomputed.
2. **Given** a no-watch transform A and a watch-declared, unaffected transform B on the same branch, **When** a commit unrelated to both is imported, **Then** only A's attributes are recomputed; B's attributes are not.

---

### User Story 5 - Deleting a transform stops its recompute and reconciles away its node-input automations (Priority: P2)

An operator deletes a Python transform (or removes it from a repository so it is deleted on import). After the delete, no recompute fires for the attribute(s) it used to feed, and the node-input recompute automations tied to that transform are reconciled away, so nothing keeps firing for a transform that no longer exists.

**Why this priority**: A dangling node-input automation for a deleted transform is a resource leak and a source of spurious or failing jobs. The delete lifecycle event MUST reconcile the automation set so it stays aligned with the transforms that actually exist.

**Independent Test**: Import a transform feeding a computed attribute (node-input automations created). Delete the transform and import. Verify no further recompute fires for the attribute(s) it fed, and the node-input recompute automation for the removed transform no longer exists.

**Acceptance Scenarios**:

1. **Given** an imported Python transform feeding a computed attribute, with its node-input recompute automations in place, **When** the transform is deleted and the deletion is imported, **Then** no recompute is triggered for the attribute(s) it used to feed.
2. **Given** the same deletion, **When** it is reconciled, **Then** the node-input recompute automation that fired for the removed transform no longer exists (the desired automation set no longer contains it, so it is dropped).
3. **Given** a deleted transform, **When** subsequent node changes and commits are imported, **Then** no recompute is triggered for the attribute(s) the deleted transform used to feed.

---

### User Story 6 - Upgrade path: null fingerprints self-heal with one recompute per transform (Priority: P2)

After upgrading to this feature, transforms imported before IFC-2844 have a null fingerprint. The first import of each repository after upgrade stamps a fingerprint on each transform. That null-to-value transition is itself an update event, which self-heals each transform with exactly one recompute of its attributes. This is a one-time cost at first import, not a full branch-wide recompute per commit.

**Why this priority**: The upgrade must be safe (null must be treated as changed to avoid stale data) and bounded (one pass per transform, not a repeated full sweep). Getting this wrong either leaves stale values or reintroduces the very over-recompute the feature removes.

**Independent Test**: Start from transforms with null fingerprints (pre-feature state). Import each repository once. Verify each transform gets a fingerprint and its attribute(s) are recomputed exactly once. Import again with no change and verify no further recompute.

**Acceptance Scenarios**:

1. **Given** a Python transform with a null fingerprint (pre-feature, never re-imported), **When** the repository is imported for the first time after upgrade, **Then** the null is treated as changed, the fingerprint is stamped, an update event fires, and the attribute(s) that transform feeds are recomputed once.
2. **Given** the same transform after its first post-upgrade import, **When** the repository is imported again with no content change and the transform declares a `watch`, **Then** the fingerprint is unchanged and no further recompute is triggered.
3. **Given** a repository with many transforms, **When** it is imported for the first time after upgrade, **Then** the total recompute cost is one recompute pass per transform, not a branch-wide full recompute repeated per commit.

---

### Edge Cases

- **Branch merge / rebase replay**: merging or rebasing a branch replays attribute changes, including fingerprint changes, onto the target branch. This must NOT be seen as a live edit and must NOT trigger a second recompute here; merge/rebase recompute is handled by its own dedicated path. The trigger reacts only to live edits.
- **Recompute-write replay**: writing a recomputed value back can itself emit node/attribute change events. Those replays must NOT re-fire the recompute trigger, or a single change would loop. The trigger reacts only to live edits, not to recompute writes.
- **New transform on import (create)**: a newly imported transform that feeds a computed attribute must drive the initial setup and first computation of that attribute, so a brand-new transform's attribute is populated without waiting for a later unrelated commit.
- **GraphQL query edited directly via the API**: editing a transform's query through the API does not refresh the transform's fingerprint, because the fingerprint is recomputed only at repository import. Today's commit-based trigger also does not recompute on an API query edit, so behaviour is unchanged (parity holds). This is a **known limitation, deferred and out of scope** for this feature; it is documented, not fixed here.
- **Read-only / pinned-commit repositories**: the import path must stamp fingerprints for read-only and pinned-commit repositories the same way it does for writable ones, so the create/update/delete triggers behave identically regardless of repository mode.
- **Transform feeding no computed attribute**: a transform that feeds no computed attribute produces no recompute; its fingerprint changes are inert for this feature. This case MUST be resolved cheaply (a name/id lookup that yields the empty set) without fetching any nodes.
- **Node-input change after a transform-only import**: importing a new transform does not change the schema, so the schema path does not run. The node-input recompute automations for that transform MUST still be built by the transform-lifecycle flow. Otherwise, a later change to a node feeding the transform's query would silently fail to recompute the attribute, leaving stale data.
- **Transform referenced by UUID instead of name**: a computed attribute may wire its transform by either name or UUID. Resolving a changed transform to its attributes MUST handle both. If the lookup finds nothing when a recompute might be needed, the flow MUST default toward recompute (log loudly), never silently skip.
- **Null fingerprint after upgrade (mid-rollout)**: until a repository's first post-upgrade import, its transforms have null fingerprints; any recompute decision made in that window MUST treat null as changed (recompute), never as unchanged (skip).

## Requirements *(mandatory)*

### Functional Requirements

#### Trigger set

- **FR-001**: The system MUST drive recompute of Python transform-based computed attributes from the transform's own lifecycle (created / updated / deleted), NOT from the commit event on a linked repository.
- **FR-002**: When a transform that feeds a computed attribute is newly imported (**created**), the system MUST perform the initial setup and first computation of the attribute(s) that transform feeds.
- **FR-003**: When a transform's `fingerprint` changes (**updated**), the system MUST resolve the transform to the computed attribute(s) it feeds and recompute **only** those attribute(s).
- **FR-004**: On an **updated** trigger, the system MUST recompute the affected attribute across **all** nodes of that attribute's kind, because a transform change can change every node's output.
- **FR-005**: When a transform is **deleted**, (a) no recompute MUST fire for the attribute(s) it fed, and (b) the node-input recompute automations tied to that transform MUST be reconciled away, so nothing survives for a transform that no longer exists.
- **FR-006**: The transform lifecycle MUST reconcile the node-input recompute automations on every lifecycle event (create / update / delete), so they are never left unbuilt or orphaned. These automations recompute an attribute when a **node feeding the transform's query** changes (a different axis from the transform's own content change). A transform-only import does not change the schema, so the schema path does not build them; the lifecycle flow MUST. Removing the commit trigger MUST NOT drop this reconciliation, because the lifecycle flow now owns it.

#### Change signal and scoping

- **FR-007**: The system MUST use the transform's branch-aware `fingerprint` attribute (delivered by IFC-2844) as the change signal; an unchanged fingerprint MUST mean the transform's output cannot have changed and its attributes MUST NOT be recomputed on that account.
- **FR-008**: The update trigger MUST be filtered to the `fingerprint` attribute changing; changes to other, non-output-affecting attributes of the transform MUST NOT trigger a recompute.
- **FR-009**: Recompute triggered by a transform change MUST be scoped to only the attribute(s) that transform feeds; it MUST NOT recompute attributes fed by other transforms (no branch-wide full recompute).
- **FR-010**: Resolution of a changed transform to the attribute(s) it feeds MUST handle a transform referenced by either name or id, because a computed attribute may wire its transform either way. If the lookup finds nothing when a recompute might be needed, the system MUST default toward recompute (log loudly), never silently skip (the over-regenerate invariant).
- **FR-011**: The system MUST NOT trigger recompute of Python transform computed attributes from the commit event on a linked repository once this feature is in place (the commit-driven full-sweep trigger for these attributes is removed). The node-input automation reconciliation the commit trigger did as a side effect is preserved by the transform lifecycle (FR-006).

#### Live-edit-only reaction

- **FR-012**: The recompute trigger MUST react only to live edits. It MUST NOT fire for fingerprint changes replayed by a branch merge or rebase, which are handled by their own recompute path.
- **FR-013**: The recompute trigger MUST NOT fire for change events produced by a recompute write itself, so a single change cannot loop into repeated recomputes.

#### Null and no-watch safety (the invariant)

- **FR-014**: A null `fingerprint` MUST be treated as "unknown" and therefore as changed; the transform's attribute(s) MUST be recomputed rather than skipped when the fingerprint is null.
- **FR-015**: The first import of a transform after upgrade MUST stamp its fingerprint (a null-to-value transition), and that transition MUST itself be an update event that recomputes the transform's attribute(s) exactly once (the self-heal path). The import MUST write each transform exactly once per import (create XOR update), so a first import produces exactly one recompute per transform.
- **FR-016**: A transform that declares no `watch` MUST keep per-commit recompute behaviour (its fingerprint folds in the commit id and changes on every commit), but the recompute MUST be scoped to only that transform's own attribute(s).
- **FR-017**: Any fallback, indeterminate, or error path in the trigger or scoping logic MUST default toward recompute, never toward skipping a recompute that may be needed (over-regenerate, never under-regenerate).

#### Scope and parity

- **FR-018**: This feature MUST apply only to Python transform-based (`TRANSFORM_PYTHON`) computed attributes; it MUST NOT change the recompute behaviour of USER-kind or JINJA2-kind computed attributes.
- **FR-019**: The import path MUST stamp fingerprints for read-only and pinned-commit repositories identically to writable repositories, so the create / update / delete triggers behave the same regardless of repository mode.
- **FR-020**: The system MUST NOT recompute on a GraphQL query edited directly through the API (the fingerprint refreshes only at import); this matches today's commit-based behaviour and is a documented, deferred limitation, not addressed by this feature.

#### Rollout

- **FR-021**: The upgrade MUST NOT cause a full branch-wide recompute per commit; the only added cost of adopting fingerprints MUST be one recompute pass per transform at that transform's first post-upgrade import.
- **FR-022**: The one-time first-import recompute cost and the deferred API-query-edit limitation MUST be documented in release notes.

### Key Entities

- **Computed attribute (transform-based)**: an attribute whose value is produced by running a Python transform over a query; stored per node. Only `TRANSFORM_PYTHON` attributes are in scope. Each is fed by exactly one transform definition.
- **Transform definition**: the Python transform node imported from a Git repository. Its lifecycle (created / updated / deleted) drives recompute of the attribute(s) it feeds. Carries the `fingerprint` attribute.
- **Fingerprint (the change signal)**: the branch-aware content hash on the transform (from IFC-2844) of everything that determines the transform's output. Unchanged fingerprint means unchanged output; a changed or null fingerprint means recompute. Stamped on every import through the standard mutation path.
- **Node-input recompute automation**: the mechanism that recomputes a transform's attribute(s) when a **node feeding the transform's query** changes (a different axis from the transform's own content change). Reconciled on every transform lifecycle event: built or refreshed on create / update, dropped on delete. The requirement is that these are never left unbuilt after a transform-only import, and never orphaned after a delete.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A commit that touches nothing a given Python transform feeds (and whose transform declares a `watch`) produces zero recompute jobs for that transform's attribute(s).
- **SC-002**: For a commit that changes the inputs of exactly K out of N transforms on a branch, only the attributes fed by those K transforms are recomputed and no others.
- **SC-003**: The amount of recompute work after a commit scales with the number of changed transforms, not with the total number of Python transform computed attributes on the branch.
- **SC-004**: A transform edit followed by its exact revert yields a net-zero change: the revert import produces no recompute for the affected attribute(s).
- **SC-005**: Every Python transform computed attribute whose transform's output-determining inputs change is recomputed and converges to the correct value; no permanently stale values result (correctness preserved across User Stories 2, 4, and 6).
- **SC-006**: A branch merge or rebase that replays a fingerprint change does not produce a duplicate recompute via this trigger (no double-fire), and a recompute write does not re-fire the trigger.
- **SC-007**: After deleting a transform, subsequent node/data changes and commits produce zero recompute for the attribute(s) the deleted transform fed, and the node-input recompute automation for the removed transform no longer exists.
- **SC-008**: On the null-fingerprint upgrade path, each transform's first post-upgrade import recomputes its attribute(s) exactly once, and a subsequent no-op import of a watch-declared transform produces zero further recompute.
- **SC-009**: No-watch transforms retain per-commit recompute (never starved), verified by every commit recomputing a no-watch transform's attribute(s) while leaving unrelated, watch-declared attributes untouched - confirming no regression on the safe fallback path.
- **SC-010**: After importing a new transform (no schema change), changing a node that feeds that transform's query recomputes the attribute. The node-input recompute automation is built by the transform-lifecycle flow even when the schema path never runs.
- **SC-011**: A computed attribute that wires its transform by UUID resolves to the same attribute(s) as one that wires it by name; both recompute correctly on a transform change.
- **SC-012**: A transform's first import produces exactly one recompute for that transform (a single create-or-update write, never a create and a separate update double-firing in the same import).

## Assumptions

- **IFC-2844 has landed** (the definition fingerprint foundation): the `fingerprint` attribute exists on the transform, is branch-aware, nullable, and is computed and stored on every repository import through the standard mutation path. This feature consumes that signal and does not recompute or store fingerprints itself.
- **A fingerprint change emits an ordinary attribute-change event** on the transform node, tagged as a live edit, distinguishable from merge/rebase replays and recompute writes. An edit-then-revert yields an identical fingerprint and therefore no event and no work.
- **Each Python transform computed attribute is fed by exactly one transform**, so resolving a changed transform to the attributes it feeds is well defined. A computed attribute may reference its transform by either name or UUID; resolution must handle both.
- **The existing per-node recompute mechanism and per-branch isolation are reused unchanged**; this feature changes only what triggers a recompute and how it is scoped, not how a single attribute value is computed.
- **The node-input recompute automations already exist** (they recompute an attribute when a node feeding the transform's query changes). This feature moves their reconciliation from the per-commit sweep to the transform lifecycle, so they are built or refreshed on create / update and dropped on delete. The requirement is that a transform-only import never leaves them unbuilt and a delete never leaves them orphaned.
- **Read-only and pinned-commit repositories are imported through the same import path** that stamps fingerprints, so no separate handling is needed for the trigger to work on them.
- **Per repo convention**, no Jira / spec / issue IDs appear in source comments, docstrings, or test names; those belong in the commit message, PR description, and changelog fragment.

## Out of Scope

- **The fingerprint fields, their computation, and their storage** - delivered by IFC-2844; this feature only consumes the signal.
- **Artifact-definition and generator consumers** of the fingerprint - separate tickets; this feature covers only Python transform computed attributes.
- **Dropping the manifest file (`.infrahub.yml`) from the dependency closure** - IFC-2775; out of scope here.
- **Jinja2 computed attributes** - git-independent, render from inline schema templates, already skip via `template_hash`; unchanged by this feature.
- **USER-kind computed attributes** - entered by hand, never derived; not affected.
- **Recompute on a GraphQL query edited directly via the API** - deferred known limitation (parity with today's behaviour); documented, not fixed.
- **Prefect scheduling and throughput tuning** - how recompute jobs are scheduled and rate-limited is not changed by this feature.
