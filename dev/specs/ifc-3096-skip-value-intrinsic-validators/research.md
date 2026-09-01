# Research: Stop emitting value-intrinsic constraint validators on data-only diffs

**Feature**: IFC-3096 | **Date**: 2026-08-31

All findings below were verified against the code on branch `skip-value-intrinsic-validators-ifc-3096`. Every claim the source PRD made about existing mechanism was checked rather than assumed; where reality differs from the PRD, that is called out explicitly.

## R1 — The declaration mechanism exists and is already honoured

**Decision**: Use the existing `ConstraintCheckerInterface.triggered_by_data_change` class attribute. No new mechanism.

**Verified**:

- `infrahub/core/validators/interface.py::ConstraintCheckerInterface` declares `triggered_by_data_change: bool = True` with a comment stating the intent.
- `infrahub/core/validators/determiner.py::ConstraintValidatorDeterminer` consults it at **both** decision points:
  - `_get_property_constraints_for_one_schema` (node-level properties)
  - `_get_constraints_for_one_field` (attribute and relationship field properties)
  Both perform `checker = CONSTRAINT_VALIDATOR_MAP.get(constraint_name)` then `if checker is not None and not checker.triggered_by_data_change: continue`.
- Two checkers already declare `False`: `node/inherit_from.py::NodeInheritFromChecker` and `node/generate_profile.py::NodeGenerateProfileChecker`. The mechanism is therefore live and load-bearing, not dormant.

**Consequence**: the implementation is one class attribute per checker. No determiner change, no interface change, no wiring change.

**Alternative considered and rejected**: a new gate inside the determiner comparing the guarded property between source and destination schemas. Rejected because it re-derives what `MergeSchemaAnalyzer::get_3ways_diff_schema` already computes, and would do so from a weaker two-way comparison that cannot distinguish which branch changed the property and ignores the common ancestor.

## R2 — Ground-truth classification: 29 identifiers, 19 checker classes

**Decision**: Flip exactly **8 checker classes**, affecting **14 constraint identifiers**.

Enumerated at runtime from `infrahub/core/validators/__init__.py::CONSTRAINT_VALIDATOR_MAP` (29 entries). Classes to flip to `triggered_by_data_change = False`:

| Checker class | Identifiers it maps from |
|---|---|
| `attribute/kind.py::AttributeKindChecker` | `attribute.kind.update` |
| `attribute/optional.py::AttributeOptionalChecker` | `attribute.optional.update` |
| `attribute/regex.py::AttributeRegexChecker` | `attribute.regex.update`, `attribute.parameters.regex.update` |
| `attribute/length.py::AttributeLengthChecker` | `attribute.min_length.update`, `attribute.max_length.update`, `attribute.parameters.min_length.update`, `attribute.parameters.max_length.update` |
| `attribute/enum.py::AttributeEnumChecker` | `attribute.enum.update` |
| `attribute/choices.py::AttributeChoicesChecker` | `attribute.choices.update` |
| `attribute/min_max.py::AttributeNumberChecker` | `attribute.parameters.min_value.update`, `attribute.parameters.max_value.update`, `attribute.parameters.excluded_values.update` |
| `relationship/peer.py::RelationshipPeerChecker` | `relationship.peer.update` |

**Note the fan-out**: several checkers are registered under more than one identifier, so 8 class-attribute edits move 14 identifiers. This is intended — a checker's classification is a property of the constraint family it guards, not of any single registry key.

Unchanged, retaining `triggered_by_data_change = True` (13 identifiers): `attribute.unique.update`, `node.uniqueness_constraints.update`, `node.parent.update`, `node.children.update`, `relationship.cardinality.update`, `relationship.min_count.update`, `relationship.max_count.update`, `relationship.optional.update`, `relationship.common_parent.update`, `node.attribute.add`, `node.relationship.add`, `attribute.parameters.start_range.update`, `attribute.parameters.end_range.update`.

Already `False` and untouched (2 identifiers): `node.inherit_from.update`, `node.generate_profile.update`.

**Arithmetic check**: 14 flipped + 2 already false = 16 with no data trigger; 29 − 16 = 13 retaining. Consistent.

**Correction to the source PRD**: the PRD's classification prose lists the families correctly, but describes the change as touching "eight checkers" without noting the identifier fan-out. The count of *classes* is eight; the count of *identifiers* that stop being scheduled is fourteen. The pinning test (R6) is written over identifiers, so this distinction matters for the expected-mapping literal.

## R3 — SETTLED: the rebase schema-hash gate does not become a correctness gap

This was the open question carried out of the spec phase with instructions to promote it to a blocking dependency if it turned out to be a real gap. **It is not.** Detail below, because the argument is the safety case for the whole feature.

### The asymmetry is real

Three call sites produce data-diff constraints, and each gates its schema-diff producer differently:

| Call site | Schema-diff gate |
|---|---|
| Merge — `core/merge/graph_merger.py::GraphMerger._validate_constraints` | `await self.schema_analyzer.has_schema_changes()` — a freshly-recomputed diff-summary query over `SchemaNode`/`SchemaAttribute`/`SchemaRelationship`. Carries a code comment stating the choice is deliberate "so a schema change is never missed at merge time". |
| Proposed Change — `proposed_change/tasks.py` (schema-integrity flow) | **No gate.** `dest_schema.diff(other=candidate_schema)` then `validate_update` runs unconditionally. |
| Rebase — `core/branch/tasks.py` (rebase flow) | `user_branch.schema_differs_from_default_branch` — a cached schema-hash comparison. |

Rebase is the weakest of the three. `core/branch/models.py::Branch.schema_differs_from_default_branch` compares the branch's cached `schema_hash.main` against the origin branch's cached `schema_hash.main`, and **returns `False` when either hash is absent**.

### Why removing data-path scheduling does not create a gap

For the removal to lose a real violation, all of the following must hold simultaneously:

1. The data-diff producer schedules value-intrinsic constraint V today — which requires the (kind, field) pair to appear in the data diff.
2. Running V would find a genuine violation.
3. The schema-diff producer does not schedule V — i.e. the rebase hash gate returns `False`.

Condition 2 is the one that fails. A violation of a value-intrinsic constraint requires the candidate schema's guarded property to differ from the property the data was validated against when it was written. The candidate schema is `destination_schema.duplicate().update(schema=source_schema)` (`core/merge/schema_analyzer.py::MergeSchemaAnalyzer.get_candidate_schema`), so for a field the source branch defines, the candidate's property value comes from the source. The branch's data was validated at write time against that same source-branch property. It therefore conforms, and V has nothing to find.

Condition 3 reinforces this rather than undermining it. When the hash gate returns `False` because the hashes match, the source and origin schemas are hash-identical — so there is no guarded-property delta anywhere for V to catch.

A destination-side schema change **does** trip the gate: the comparison is source-current against origin-current, so a change landing on the destination moves the origin hash and the gate opens. This is what makes FR-002's "either source or destination" claim hold on the rebase path, and `get_3ways_diff_schema` (which sums `ancestor→source` and `ancestor→destination`) is what makes it hold once the gate is open.

### The one residual, and why it is not a blocker

The gate fails open when `schema_hash` is `None` on either branch. In that state the schema-diff producer is skipped even though a real property delta may exist, and today's data-path scheduling provides incidental cover.

That cover is not a safety net worth preserving:

- It is **partial by construction** — the data path only schedules constraints for (kind, field) pairs that happen to appear in the data diff. A guarded-property change on a field with no data changes on the branch is already uncovered today.
- It is **coincidental, not designed** — nothing in the code claims the data path backstops the hash gate.
- The `None`-hash state is a **startup-ordering edge**, not a normal operating state: `core/initialization.py` populates hashes for the default branch and every other branch at startup, and `core/branch/creator.py` calls `update_schema_hash()` at branch creation.

**Decision**: proceed. Do not block. Record the gate asymmetry as a follow-up ticket recommending rebase adopt merge's `has_schema_changes()`, which is strictly stronger than the cached-hash comparison and removes the fail-open. The knowledge page (R7) documents the reliance so the next reader does not have to re-derive this argument.

**Verified in passing**: PRD assumption #2 — "all three call sites of the data-diff producer pair it with a schema-diff producer" — holds. All three merge two producers through `ConstraintInfoMerger`.

## R4 — SETTLED: the missing `.value` on the two number-pool range keys

**Finding**: `CONSTRAINT_VALIDATOR_MAP` keys `ATTRIBUTE_PARAMETERS_START_RANGE_UPDATE` and `ATTRIBUTE_PARAMETERS_END_RANGE_UPDATE` on the enum *member* rather than `.value`, unlike all 27 other entries.

**Verified behaviourally**: `ConstraintIdentifier` is a `StrEnum`, so members hash and compare equal to their string values. A lookup by the plain string returns the checker correctly, and `{member} == {"attribute.parameters.start_range.update"}` is `True`. **There is no behavioural defect** — the two entries work identically to their `.value` siblings. Runtime inspection confirms the map's key types are a mix of `str` and `ConstraintIdentifier`.

**Decision**: normalise both keys to `.value` as part of this feature.

**Rationale**: the FR-004 pinning test enumerates exactly this dict. Leaving two keys as enum members makes the test's expected-mapping literal inconsistent with the source it pins, for no benefit, and invites a future reader to conclude the difference is meaningful. The fix is two characters, provably behaviour-preserving under `StrEnum`, and lands in the same file the pinning test targets.

**Scope note**: `.agents/rules/backend-component-design.md` says not to refactor unrelated nearby code in an unrelated change. This is judged in-scope rather than drive-by: the dict is the direct subject of a deliverable in this feature. It is not a licence to touch anything else in that module.

## R5 — Test surface: six edit sites, not three

`backend/tests/component/core/constraint_validators/test_determiner.py` is the **only** test that routes through the determiner. Every other test naming a value-intrinsic identifier invokes its checker directly with an explicit constraint request and is therefore unaffected. Verified by grepping the whole of `backend/tests/` for `get_constraints` / `Determiner` usage.

**Correction to the source PRD**: the PRD states "three assertions invert". The actual count is **six edit sites**:

| # | Site | Change |
|---|---|---|
| 1 | `person_name_node_diff` fixture | Drop `attribute.kind.update` and `attribute.optional.update`; keep `attribute.unique.update`. Shared by five tests. |
| 2 | `person_cars_node_diff` fixture | Drop `relationship.peer.update`; keep cardinality, optional, min_count, max_count. |
| 3 | `RELATIONSHIP_PROPERTIES` module constant | Drop `"peer"` from the tuple. |
| 4 | `test_uniqueness_not_triggered_by_unrelated_field` | Drop the `kind` and `optional` attribute constraints; only `unique` remains. |
| 5 | `test_generic_uniqueness_triggered_by_inherited_field` | Drop the `kind` and `optional` attribute constraints. |
| 6 | `test_node_property_constraints_included` | Drop `attribute.parameters.max_length.update`. |

This does not change scope, but the task list must cover all six or the suite fails.

**Observation that strengthens the safety case**: after these deletions, several expected sets shrink to *only* cross-node constraints — which is precisely the assertion FR-001 and FR-003 want. The existing tests become the narrowed-set assertions almost for free; the new work is the explicit data-only-diff test that names the exclusion intentionally rather than by omission.

## R6 — Pinning-test design

**Decision**: a unit test at `backend/tests/unit/core/validators/test_constraint_classification.py` asserting **full dict equality** between `{identifier: checker.triggered_by_data_change for identifier, checker in CONSTRAINT_VALIDATOR_MAP.items()}` and a literal expected mapping of all 29 identifiers.

**Rationale**:

- Full-dict equality (not `issubset`, not "every identifier is present") is what makes *adding* a checker fail the test, satisfying FR-004. A membership-style assertion would pass silently for a new entry.
- Keying on identifiers rather than classes means the expected literal doubles as human-readable documentation of the classification, satisfying the reviewability requirement in User Story 3 / FR-009's spirit.
- Unit tier, no DB — the map is a module-level dict. Per `.agents/rules/testing-python.md`, pick the cheapest tier.

**Explicitly not done**: asserting a specific checker class's attribute value in isolation. The spec's Testing Decisions call this out — such a test would pass while the determiner ignored the attribute entirely. The behavioural guarantee lives in the determiner component test; the pinning test guards against *drift*, not against the determiner regressing.

**Default-direction coverage (FR-006)**: the expected literal includes the 13 `True` entries, so a change to `ConstraintCheckerInterface`'s default flips them and fails the test. The default is pinned by consequence rather than by a separate assertion, which is the stronger form.

## R7 — Documentation

**Decision**: new knowledge page `dev/knowledge/backend/constraint-validation.md`.

**Verified**: no existing page under `dev/knowledge/backend/` covers this subsystem. The closest neighbours are `merge-recompute.md`, `selective-merge-regeneration.md` and `schema-definitions.md`, none of which describe the two constraint producers or the determiner.

**Contents** (FR-005): the two constraint producers and their three call sites with their differing gates (the R3 table), the determiner's two decision points, the constraint info merger's union-with-unrestricted-scope-winning rule, the classification with each entry's justification, and — for each value-intrinsic constraint — the write-time enforcement point being relied on. The R3 argument is recorded there so the reliance is documented rather than assumed, as the spec's Constitution Alignment requires.

**Changelog**: a `housekeeping` fragment under `changelog/`, per the spec's governance section. Existing fragments follow the `+<slug>.<type>.md` convention.

## R8 — Write-time enforcement points

FR-005 requires naming the write-time enforcement point relied on for each value-intrinsic constraint. This is the evidence for the classification and must be traced during implementation rather than asserted here — the knowledge page is not allowed to claim an enforcement site that was not confirmed.

**Decision**: treat this as an implementation task with a verification obligation, not a research conclusion. The one enforcement detail already confirmed is the strict-schema-validation interaction: `AttributeNumberChecker` declines to run under the same setting that gates its write-time counterpart, so the merge-time and write-time checks cannot desynchronise (spec edge case, PRD-supplied, consistent with the checker's `supports` logic).

If tracing finds a value-intrinsic constraint with **no** universal write-time enforcement point, that constraint must be removed from the flip list and the finding recorded — the classification is only sound where the enforcement it relies on actually exists.
