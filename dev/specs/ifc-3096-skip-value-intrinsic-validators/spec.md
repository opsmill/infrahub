# Feature Specification: Stop emitting value-intrinsic constraint validators on data-only diffs

**Feature Branch**: `skip-value-intrinsic-validators-ifc-3096`

**Created**: 2026-08-31

**Status**: Draft

**Input**: [IFC-3096](https://opsmill.atlassian.net/browse/IFC-3096) — "Stop emitting value-intrinsic attribute constraint validators on data-only diffs". Parent epic: [IFC-2706](https://opsmill.atlassian.net/browse/IFC-2706) — make schema validation incremental on proposed change and merge.

## Problem Statement

When a user rebases or merges a branch, or runs Proposed Change validation, the amount of validation work performed scales with how much data exists in the database rather than with what the branch actually changed. A branch that edits three attribute values on a kind with 100,000 instances pays three full-population scans that are structurally incapable of finding a violation. On large datasets this turns routine branch operations into multi-minute waits, and the wait grows as the customer's data grows even though their changes do not.

## Solution Overview

Validation on a data-only branch operation stops running the checks that a data change cannot possibly violate. Constraints that are **value-intrinsic** — enforced on every individual value at the moment it is written, such as attribute kind, mandatory-ness, regex, enum, length, numeric bounds, dropdown choices, and relationship peer kind — are no longer scheduled by the data-diff producer. They continue to run at full strength whenever the guarded schema property genuinely changes, which the schema-diff producer already owns. Constraints that span multiple nodes — uniqueness, relationship cardinality, hierarchy, common parent — are untouched, because combining two independently-valid branches genuinely can violate those.

For the user, branch operations on data-only changes get faster, and the time they take stops depending on total database size.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Data-only branch operations skip checks that cannot fail (Priority: P1)

An operator rebases, merges, or runs Proposed Change validation on a branch that changed only instance data, against a destination whose schema is unchanged for the touched fields. Validation runs only the constraints a data change can actually violate, so the operation completes in time proportional to the change rather than to the size of the database.

**Why this priority**: This is the entire user-visible benefit of the feature. Without it there is nothing to ship. Routine branch hygiene currently becomes slower as inventory grows even though the changes do not.

**Independent Test**: Build a diff containing data changes to a set of (kind, field) pairs with no schema change to any guarded property, run it through constraint determination, and assert the resulting constraint set contains none of the value-intrinsic identifiers and all of the cross-node ones.

**Acceptance Scenarios**:

1. **Given** a branch whose diff contains data changes to K (kind, field) pairs and no schema change to any guarded property, **When** the branch is rebased, merged, or validated via Proposed Change, **Then** no constraint is scheduled from any of the eight value-intrinsic checkers.
2. **Given** the same branch, **When** constraints are determined, **Then** every cross-node constraint is scheduled exactly as it is today.
3. **Given** the same branch, **When** the operation completes, **Then** its outcome — success, failure, and the set of violations reported — is identical to today's.
4. **Given** a data-only diff, **When** the number of (kind, field) pairs it touches increases, **Then** the count of scheduled value-intrinsic constraints stays at zero.

---

### User Story 2 - A genuine schema property change still validates the full population (Priority: P1)

An operator changes an attribute's kind — or its regex, enum, length, numeric bounds, or dropdown choices, or a relationship's peer — on a branch that also contains data changes. The resulting validation still checks every existing instance, so tightening a schema rule still reports which existing data violates it.

**Why this priority**: This is the safety property that User Story 1 must not regress. It is a verification journey rather than a separately shippable slice: it pins behaviour that already works and must continue to work. It shares P1 because shipping User Story 1 without it would be shipping an unverified integrity risk.

**Independent Test**: Change an attribute's kind on a branch that also edits instance data for that kind, determine constraints, and assert the kind constraint is present at unrestricted scope — sourced from the schema-diff producer, not the data-diff producer.

**Acceptance Scenarios**:

1. **Given** a branch that changes an attribute's kind and also edits instance data for that kind, **When** the branch is merged, **Then** the kind constraint is scheduled by the schema-diff producer at unrestricted scope and every existing value is checked.
2. **Given** a branch where the guarded property changed on the destination rather than the source, **When** the branch is merged, **Then** the constraint is still scheduled, because the schema comparison spans both directions from the common ancestor.
3. **Given** a branch that both changes a guarded property and edits data, **When** the two producers' outputs are combined, **Then** the unrestricted-scope entry from the schema-diff producer survives the merge of the two constraint sets.

---

### User Story 3 - The classification cannot drift silently (Priority: P2)

A developer adds a new constraint checker. The codebase forces them to state whether a data change can violate the constraint their checker guards, rather than letting the decision be inherited by accident, and the reasoning behind every existing classification is written down so they can decide correctly without re-deriving the argument.

**Why this priority**: Protects the gain from eroding. Without it, the next checker added quietly reintroduces a full-population scan on the data path and nobody notices until a customer's merge slows down again. It is P2 because the performance benefit lands without it, but the benefit is not durable.

**Independent Test**: Add a hypothetical new entry to the constraint validator registry without updating the classification record, and confirm the test suite fails.

**Acceptance Scenarios**:

1. **Given** a new constraint identifier added to the validator registry, **When** the test suite runs without the classification record being updated, **Then** a test fails naming the unclassified identifier.
2. **Given** a constraint identifier removed from the validator registry, **When** the test suite runs without the classification record being updated, **Then** a test fails — the record pins the registry in both directions, not merely that every identifier is classified.
3. **Given** a developer reading the project's internal documentation, **When** they look for why a given constraint is classified as it is, **Then** they find the rationale and, for each value-intrinsic constraint, the write-time enforcement point being relied on.

---

### Edge Cases

- **A branch containing both a genuine kind change and data changes.** The schema-diff producer contributes the constraint at unrestricted scope, the merger keeps it there, and the full scan runs correctly. The data-diff producer's silence does not subtract from it.
- **A branch that deletes a kind's schema while still holding data for that kind.** Constraint determination already skips constraints for kinds absent from the schema; this feature does not change that path.
- **The guarded property changed on the destination branch rather than the source.** Covered, because the merge schema comparison is three-way — it spans the common ancestor, the source branch and the destination branch — so it owns property changes originating on either side.
- **Strict schema validation disabled.** The numeric-bounds checker already declines to run under the same setting that gates its write-time counterpart, so the merge-time check and the write-time check cannot desynchronise.
- **Boolean-valued schema properties.** Mandatory-ness and uniqueness default to `false` rather than being absent, which is precisely why they are scheduled for every attribute in a diff today: the producer's own emptiness check cannot distinguish "not set" from "set to false". Reclassifying mandatory-ness is the fix for that half; the producer's emptiness check is deliberately left alone.
- **Profile and template kinds.** The schema comparison excludes profile and template schemas, so the schema-diff producer structurally never emits constraints for a `Profile<Kind>` or `Template<Kind>`. Today the data-diff producer does, because those kinds appear in the data diff like any other. After this change **neither** producer schedules value-intrinsic constraints for them. This is sound rather than an oversight: profile and template attribute values are written through the same attribute layer as any other, so the write-time enforcement argument applies unchanged and is the only thing these kinds ever relied on. It is called out because the general claim "the schema-diff producer picks it up instead" is *not* true for these kinds, and a reader checking that claim against a profile would otherwise find a contradiction.
- **Pre-existing invalid data in the database.** The full-population scans being removed would incidentally surface values that were already invalid before the branch existed. This is not treated as a capability being lost — pre-existing invalid data is owned by migrations, not by merge-time validation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST NOT schedule value-intrinsic attribute or relationship constraints from the data-diff producer.
  *Verify*: the constraint-determination component test asserts the narrowed set for a data-only diff.
- **FR-002**: The system MUST continue to schedule and run every value-intrinsic constraint via the schema-diff producer, at unrestricted scope, whenever the guarded property changes on either the source or the destination branch.
  *Verify*: a component test that composes the **schema-diff producer** with the constraint merger — not the data-diff producer, which by design contributes nothing here — changing an attribute kind on a branch that also has data changes, and asserting the kind constraint is present at unrestricted scope. Plus one end-to-end case through the real rebase/merge path.
- **FR-003**: The system MUST continue to schedule all cross-node constraints from the data-diff producer unchanged — attribute uniqueness, node uniqueness constraints, relationship cardinality, minimum and maximum count, relationship optionality, common parent, and hierarchy.
  *Verify*: constraint-determination component test asserts each is still present for a data-only diff.
- **FR-004**: The classification MUST be protected against silent drift, such that adding a new constraint checker fails a test until its classification is stated deliberately.
  *Verify*: unit test enumerating every constraint identifier against its data-trigger setting; adding a checker without updating it fails.
- **FR-005**: The rationale for each classification MUST be documented, including the write-time enforcement point relied on for each value-intrinsic constraint.
  *Verify*: a backend knowledge page exists covering constraint validation and the classification.
- **FR-006**: The default classification for a checker that does not state one MUST remain "a data change can violate this", so that a forgotten declaration is a wasted-work bug rather than a silent under-validation bug.
  *Verify*: the classification pinning test covers the default, and no checker relies on an inverted default.

### Key Entities

All existing. No new entities, no new persisted state, no new configuration.

- **Constraint checker**: the component that knows how to verify one family of schema constraints against the database. It already carries an explicit declaration of whether a data change can violate the constraint it guards, and that declaration is already honoured. Eight checkers change their declaration; no checker changes its logic.
- **Constraint validator determiner**: the component that decides which constraints to schedule for a given diff. Unchanged — it already consults the checker's declaration at both its node-level and its field-level decision points.
- **Merge schema analyzer**: the component that computes which schema properties changed for a merge. Unchanged — it already performs a three-way comparison spanning the common ancestor, the source branch and the destination branch, so it owns property changes originating on either side.
- **Constraint info merger**: the component that combines the two producers' outputs. Unchanged — it unions constraints from both producers with unrestricted scope winning, so removing entries from one producer leaves the other's intact.

### Classification

Declared as having **no** data trigger (value-intrinsic — enforced on every individual value at the moment it is written):

| Constraint family | Guarded properties |
|---|---|
| Attribute kind | `attribute.kind.update` |
| Attribute optionality | `attribute.optional.update` |
| Attribute regex | `attribute.regex.update`, `attribute.parameters.regex.update` |
| Attribute length bounds | `attribute.min_length.update`, `attribute.max_length.update`, `attribute.parameters.min_length.update`, `attribute.parameters.max_length.update` |
| Attribute enum | `attribute.enum.update` |
| Attribute dropdown choices | `attribute.choices.update` |
| Attribute numeric bounds and excluded values | `attribute.parameters.min_value.update`, `attribute.parameters.max_value.update`, `attribute.parameters.excluded_values.update` |
| Relationship peer | `relationship.peer.update` |

Retaining their data trigger (cross-node — combining two independently-valid branches genuinely can violate them):

| Constraint family | Guarded properties |
|---|---|
| Attribute uniqueness | `attribute.unique.update` |
| Node uniqueness constraints | `node.uniqueness_constraints.update` |
| Node hierarchy | `node.parent.update`, `node.children.update` |
| Relationship cardinality and count | `relationship.cardinality.update`, `relationship.min_count.update`, `relationship.max_count.update` |
| Relationship optionality | `relationship.optional.update` |
| Relationship common parent | `relationship.common_parent.update` |
| Node attribute add | `node.attribute.add` |
| Node relationship add | `node.relationship.add` |
| Attribute number pool range | `attribute.parameters.start_range.update`, `attribute.parameters.end_range.update` |

Already declared as having no data trigger before this change, and unaffected by it: node inheritance (`node.inherit_from.update`) and profile generation (`node.generate_profile.update`).

**Relationship peer** reaches the value-intrinsic conclusion by a different argument than the attribute constraints, and is recorded here because it is the least obvious entry in the table. Its effective allowed set is the declared peer kind plus, for a generic peer, the list of kinds using that generic. That list is derived from every node's inheritance declaration and is never set directly. It can only grow — which widens the allowed set and therefore cannot invalidate an existing link — or shrink, which requires either removing a generic from a node's inheritance, which the inheritance checker rejects outright regardless of data, or deleting the kind entirely, which removes its instances with it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The time to rebase, merge, or validate a data-only branch does not increase as the database's node population grows, for the value-intrinsic constraint families.
  *Measured by*: zero constraints scheduled from the eight value-intrinsic checker classes — covering fourteen constraint identifiers — for a data-only diff, independent of how many attributes or relationships it touches. Gated in CI.
- **SC-002**: For a data-only diff, total scheduled constraints fall by **2A + R + P**, where A is the number of attribute (kind, field) pairs, R the number of relationship pairs, and P the number of optional attribute parameters that are set among the value-intrinsic families.
  *Rationale for the shape*: an attribute pair unconditionally schedules `kind`, `optional` and `unique`, of which the first two are value-intrinsic — hence 2A. A relationship pair unconditionally schedules `peer`, `cardinality`, `optional`, `min_count` and `max_count`, of which only `peer` is value-intrinsic — hence R. A pair is either an attribute or a relationship, never both, so no pair contributes to more than one term. Optional parameters (regex, enum, choices, length bounds, numeric bounds) are scheduled only when set, hence the separate P term.
  *Measured by*: a parameterised assertion in the constraint-determination component test over a diff with a known A/R/P composition. Gated in CI.
- **SC-003**: No scenario that previously caught a real violation stops catching it. The existing test suite passes unchanged apart from the assertions that deliberately invert.
- **SC-004**: Before-and-after wall-clock for a data-only rebase, with the node population it was measured against, is recorded **in the knowledge page** as well as the pull request description. Reported, not gated — no baseline exists to set a defensible threshold against, and a figure that lives only in a PR description is not recoverable later.

### Rollback

This change removes validation work, so its failure mode produces no error at the time it occurs. The rollback trigger is therefore stated explicitly rather than left to judgement:

**Revert if** a constraint violation reaches the default branch that merge-time validation should have caught, for any constraint in the value-intrinsic table.

Reverting is a single-commit operation — the change is class-attribute declarations with no migration, no persisted state and no configuration — so no feature flag or staged rollout is warranted.

## Assumptions

- Every write of attribute data passes through the attribute layer, so value validation and canonical-form normalisation are universal at write time. Raw-Cypher writes performed by migrations are the acknowledged exception and are themselves schema-driven.
- All three call sites of the data-diff producer — rebase, merge, and Proposed Change validation — pair it with a schema-diff producer, so a per-checker declaration has no path that loses coverage.
- Pre-existing invalid data is owned by migrations, not by merge-time validation. The full-population scans being removed would incidentally surface such data; this is not treated as a capability being lost.
- The existing per-checker declaration mechanism is the right lever. A new gate comparing the guarded property between source and destination schemas inside the determiner was considered and rejected: it would re-derive what the schema-diff producer already computes, and would do so from a weaker two-way comparison that cannot distinguish which branch changed the property and ignores the common ancestor.

## Out of Scope

- **The attribute number pool range constraint.** Its enforcement lives in pool allocation rather than attribute validation and was not traced; it also only applies when the attribute is a number pool, so it carries none of the observed cost. It keeps its data trigger.
- **Node-scoping the constraints that still fire on the data path.** That is [IFC-2797](https://opsmill.atlassian.net/browse/IFC-2797), whose scope this ticket narrows to the constraints that remain.
- **Any framing of this work as a bug fix**, and any handling of databases carrying pre-existing invalid values.
- **A gated wall-clock performance target.** Setting one honestly requires capturing a baseline first; SC-004 reports the measurement instead.

## Dependencies and Related Work

- **Parent epic**: IFC-2706 — make schema validation incremental on proposed change and merge.
- **Builds on**: IFC-2795 (determiner field and path granularity), which established the principle this extends to field-level value-intrinsic constraints, and which delivered the per-checker declaration decision points this feature relies on.
- **Narrows**: IFC-2797 (node-scope the remaining constraint validators).
- **Precedent**: IFC-2796 introduced node-scoping for uniqueness — the same shape of fix applied to the cross-node constraint that legitimately keeps its data trigger.

## Governance Gates

Assessed against the "Ask First" list in `AGENTS.md`:

| Gate | Crossed? |
|---|---|
| Database schema or migration change | No |
| GraphQL schema modification | No |
| New dependency | No |
| CI/CD workflow change | No |
| Authentication / authorization change | No |

None crossed. A `housekeeping` changelog fragment is required.

## Open Questions

Neither question blocks this feature; both are candidates for separate tickets and are recorded so they are not lost.

- Attribute uniqueness is scheduled for every attribute in a diff because its schema property defaults to `false` rather than being absent. The check itself exits cheaply for non-unique attributes, but each scheduling still round-trips the per-constraint validation dispatch. **Resolution for this feature**: leave as-is and fold the cost question into IFC-2797, which already owns narrowing the constraints that remain on the data path.
- Rebase gates the schema-diff producer on the branch's cached schema hash, while merge deliberately recomputes the diff, with a code comment stating this is so a schema change is never missed at merge time. Today's data-path scheduling incidentally masks that asymmetry on rebase. **Resolution for this feature**: out of scope, but must be confirmed during planning that removing the data-path scheduling does not turn the asymmetry into a correctness gap on rebase — if it does, that promotes to a blocking dependency rather than a follow-up ticket.
