# Feature Specification: Number Pools P1 — Weighted Ranges

**Feature Branch**: `pmi-number-pools-part1`

**Created**: 2026-09-17

**Status**: Draft

**Epic**: IFC-3065 (JPD INFP-308, component card INFP-325, community issue GH #7064)

**Input**: User description: "Number Pools P1 (Epic IFC-3065). Source PRD: Notion *Number Pools - PRD, simple as possible* and its *P1 addendum: decisions settled during spec-kit*."

**Sources of truth**, in order of precedence for P1:

| Precedence | Document |
|-----------|----------|
| 1 | [P1 addendum: decisions settled during spec-kit](https://app.notion.com/p/opsmill/P1-addendum-decisions-settled-during-spec-kit-3de228b83025818e980dc8486facfa95) |
| 2 | [Number Pools - PRD, simple as possible](https://app.notion.com/p/opsmill/Number-Pools-PRD-simple-as-possible-cf5228b83025824f804c016b4f2194f6) |
| 3 | [Number Pools — PRD](https://app.notion.com/3fb228b8302582e28e1e01cafd3526f3) (base PRD, INFP-308; requirement numbers `PRD FR-nnn` below refer to it) |

Where a lower-precedence document says something this specification does not repeat, it stands. Where they differ, the higher-precedence document wins and this specification follows it.

## Scope

P1 delivers **several weighted ranges per number pool**, for pools a user creates and for pools the schema creates. It ships on its own; it does not depend on, and is not depended on by, the other slices.

| Slice | Content | In P1 |
|-------|---------|-------|
| P1 | Several weighted ranges per pool; ranges declared in the schema; single-bound shorthand kept as a deprecated spelling | Yes |
| P2 | Numbers a user gives the pool (provide, attach, detach), provenance, record lifecycle matrix, removal of the hand-set-value scan and the #10180 revert | No |
| P3 | Allocation scope on the pool and in attribute parameters (`allocation_scope`, PRD FR-043) | No |
| P4 | SDK identifier | No |
| Frontend | Range management in the pool form, pool detail per-range view | No (existing screens must tolerate the new read shape) |

### Guiding principles for P1

1. **The pool never refuses a value; the schema does.** Ranges decide where allocation draws from. Whether a value is valid is decided by the attribute's own domain (`min_value`, `max_value`, `excluded_values`) and its uniqueness constraints.
2. **Ranges are branch-agnostic**, like the pool that owns them. A range edit takes effect on every branch immediately and nothing about a range is stored per branch.
3. **One arithmetic.** Size, utilization, allocation order and fullness all come from one effective-space calculation: union of ranges, intersected with `[min_value, max_value]`, minus the excluded values that fall inside that union.
4. **What a pool knows stays as today.** P1 keeps the existing skip of values already sitting on a unique attribute, generalised over the range set. Making the pool blind to its attribute belongs to P2.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A pool over a space with gaps, drawn in the order I choose (Priority: P1)

An operator creates one pool holding VLANs 100–200 and 205–300, weights 100–200 to be drained first, allocates until it is empty, watches allocation move to 205–300, and reads a utilization figure measured against both ranges together. The pool reports itself full only when both ranges are exhausted.

**Why this priority**: This is the capability the slice exists for. Without it a number space with a gap still needs one pool per piece.

**Independent Test**: Create a two-range pool through the API, allocate through the existing allocation path, and check the returned numbers, the utilization figures and the fullness error. No other slice is involved.

**Acceptance Scenarios**:

1. **Given** a pool with ranges 100–200 (heavier) and 205–300 and nothing allocated, **When** 101 numbers are allocated one after another, **Then** they all come from 100–200 in ascending order, nothing between 201 and 204 is ever handed out, and utilization says 101 of 197.
2. **Given** a pool with 100–200 exhausted and 205–300 untouched, **When** the next number is allocated, **Then** 205 comes back and the pool does not report itself full.
3. **Given** a pool with two ranges of equal weight, or with no weight on any range, **When** numbers are allocated, **Then** the range with the lowest start is drained first and the order never depends on chance.
4. **Given** a partially drained pool, **When** the weight of a not-yet-heaviest range is raised above every other, **Then** the next allocation comes from that range, at its lowest free number.
5. **Given** a pool whose every effective range is exhausted, **When** a number is requested, **Then** the existing pool-exhausted error is raised.
6. **Given** a pool whose attribute declares `min_value`, `max_value` or `excluded_values`, **When** size and utilization are read, **Then** the size counts only the numbers inside the ranges that also sit inside `[min_value, max_value]` and are not excluded, and excluded values outside every range subtract nothing.

---

### User Story 2 - Pools that exist today keep working unchanged (Priority: P1)

A deployment upgrades. Every pool it had becomes a pool with one range covering its old span. What each pool handed out, what it reports, and the way its operators write `start_range` / `end_range` all keep working. Clients that read the two scalars get the same values as before on a single-range pool.

**Why this priority**: The customer tracking VLANs by hand is the reason a pool with no new configuration has to behave exactly as it does now. A migration that changes any figure is a release blocker.

**Independent Test**: Run the migration against a database holding pre-existing pools with allocations, then compare handed-out numbers, utilization and the scalar read values before and after.

**Acceptance Scenarios**:

1. **Given** a pool that existed before this change, **When** the migration runs, **Then** it holds one range covering its old span with no weight, and what it handed out and what it reports are unchanged.
2. **Given** a pool that already holds one range covering its old span, **When** the migration runs again, **Then** no second range is created.
3. **Given** a pool holding exactly one range, **When** `start_range` / `end_range` are read, **Then** they return that range's bounds.
4. **Given** a pool holding one range, **When** `start_range` / `end_range` are written, **Then** that same range is rewritten in place (same identity, same weight), and no second range is added.
5. **Given** a pool holding no range, **When** `start_range` / `end_range` are written, **Then** the pool's single range is created.
6. **Given** a schema written before this change that declares only `start_range` / `end_range` on a number-pool attribute, **When** it is loaded, **Then** it loads with identical meaning: one range with those bounds.
7. **Given** a schema that declares exactly one of `start_range` / `end_range`, **When** it is loaded, **Then** the other bound resolves to its former default (the lowest / highest value the attribute kind accepted before this change), so the declaration means what it meant before.

---

### User Story 3 - Grow and shrink a pool that is already in use (Priority: P2)

An operator adds a range to a pool already handing out numbers, removes a range to give part of the space to something else, and is never refused for a range edit, even when the removed range holds numbers already handed out. Numbers that fall outside every remaining range stay associated with the pool, are never handed out and do not count, and count again when a covering range is added back.

**Why this priority**: Growing and shrinking a live pool is what makes several ranges useful over time; it depends on User Story 1 existing.

**Independent Test**: On a two-range pool with allocations in both ranges, remove and re-add a range and check utilization, allocation and the persisted records after each step.

**Acceptance Scenarios**:

1. **Given** a pool in use, **When** a non-overlapping range is added, **Then** the addition succeeds, nothing already handed out changes, and the pool's size grows by the new range's effective size.
2. **Given** ranges 100–200 (fully allocated) and 205–300 with 250 allocated, **When** 205–300 is removed, **Then** the removal succeeds, 250 stays associated with the pool, utilization reports 101 of 101, and 250 is never handed out.
3. **Given** the pool from scenario 2, **When** 205–300 is re-added, **Then** 250 counts as in use again and utilization reports 102 of 197.
4. **Given** a pool holding ranges, **When** a range overlapping an existing range of the same pool, or a range whose end is below its start, is saved, **Then** the save is refused and the error names the clashing ranges.
5. **Given** two user-created pools attached to the same kind and attribute, **When** their ranges overlap, **Then** both saves are accepted; only a uniqueness constraint on the attribute refuses a collision between them.
6. **Given** a pool whose last range is removed, **When** it is read and allocated from, **Then** the pool is legal, size is 0, utilization reports 0 of 0 as 0 %, and allocation raises the existing pool-exhausted error.
7. **Given** a pool holding more than one range, **When** `start_range` / `end_range` are written, **Then** the write is refused, the error states that the shorthand applies to a pool holding at most one range and lists every range the pool holds by bounds and identifier, and the pool is left untouched.
8. **Given** a write that supplies both `start_range` / `end_range` and an explicit list of ranges, **When** it is saved, **Then** it is refused as conflicting spellings.

---

### User Story 4 - Several ranges declared in the schema (Priority: P2)

A schema author declares a number-pool attribute with a list of ranges, each with its own weight, or with the single start and end as before. The pool the schema creates carries those ranges. Editing the schema on the default branch reconciles the pool's ranges; editing the ranges directly on the pool is refused and the user is pointed at the schema. A schema change that would leave a value an object holds outside the declared ranges is refused and the objects are identified.

**Why this priority**: Schema-created pools are the second kind of pool and must gain the same capability, but they build on the range model of User Story 1.

**Independent Test**: Load a schema declaring a multi-range pool attribute, create objects, change the schema on the default branch, and attempt direct edits through both pool and range mutations.

**Acceptance Scenarios**:

1. **Given** a number-pool attribute declaring `parameters.ranges` with weights, **When** the schema loads, **Then** the pool is created with those ranges materialised, weights preserved, and is never left with only scalar bounds and no range.
2. **Given** a number-pool attribute declaring both `start_range` / `end_range` and `parameters.ranges`, **When** the schema loads, **Then** the load is refused as conflicting spellings.
3. **Given** a number-pool attribute declaring neither spelling, **When** the schema loads, **Then** the pool is created with zero ranges, which is legal. An attribute written before this change and relying on the former parameter defaults takes this path, so its pool is empty where it once spanned `1`–`sys.maxsize`.
4. **Given** a schema-created pool, **When** the default-branch schema adds, removes or reweights a range, **Then** the pool's ranges are reconciled to the new declaration and every number already handed out stays recorded.
5. **Given** a schema-created pool with objects holding numbers, **When** a schema change would leave a held value outside every declared range, **Then** the load is refused and the offending objects are identified.
6. **Given** a schema-created pool, **When** its ranges are edited through the pool's own update, **Then** the edit is refused and the error points at the schema in the default branch.
7. **Given** a schema-created pool, **When** one of its ranges is created, updated or deleted through the range's own mutations, **Then** the edit is refused and the error points at the schema in the default branch.
8. **Given** a schema-created pool holding several ranges, **When** `start_range` / `end_range` are written on it, **Then** the existing schema-pool refusal fires, taking precedence over the multi-range refusal.
9. **Given** ranges declared in the schema with `start > end` or overlapping each other, **When** the schema loads, **Then** the load is refused.

---

### User Story 5 - API consumers learn the shorthand is deprecated (Priority: P3)

An API or SDK consumer discovers, through introspection and schema-load warnings, that `start_range` / `end_range` are deprecated in favour of `ranges`, while both spellings keep working. Existing consumers tolerate a null `start_range` / `end_range` on a pool with zero or several ranges.

**Why this priority**: Deprecation is the contract half of the change; it does not block the capability but must ship with it so that removal in a later major version is announced.

**Independent Test**: Introspect the GraphQL schema, load a schema declaring the shorthand, and read a zero-range and a multi-range pool from the existing frontend and SDK code paths.

**Acceptance Scenarios**:

1. **Given** the GraphQL schema, **When** it is introspected, **Then** `start_range` and `end_range` carry a deprecation marker on the pool object type, its interface, and its create / update / upsert inputs, pointing at `ranges`.
2. **Given** a schema declaring `start_range` / `end_range` on a number-pool attribute, **When** it is loaded, **Then** the load response carries one deprecation warning per such attribute pointing at `parameters.ranges`, and the load succeeds.
3. **Given** a pool with zero ranges or more than one range, **When** `start_range` / `end_range` are read, **Then** they are null, and the existing frontend and SDK consumers display or process the pool without error.
4. **Given** a pool mutation response, **When** the shorthand was used, **Then** no deprecation signal is expected in the response body.

---

### Edge Cases

- Two ranges in one pool overlap, or a range ends below where it starts: refused, clashing ranges named.
- A range is removed, or narrowed, while numbers inside it have been handed out: succeeds; the affected records stay associated and hidden until a covering range returns.
- Two ranges carry the same weight, or no range carries one: lowest start first.
- A weight changes on a partially drained pool: the newly heaviest range is drawn from next, at its lowest free value.
- An attribute's excluded values lie entirely outside the pool's ranges: size is unchanged and no division-by-zero error occurs.
- An attribute's `min_value` / `max_value` clamp a range to nothing: that range counts as exhausted for fullness and contributes 0 to size.
- A pool ends up with zero ranges: legal; size 0, utilization 0 %, allocation raises the pool-exhausted error.
- A schema declaration drops to zero ranges while objects hold values: the load is refused and the objects identified, because every held value is then outside every range.
- Two user-created pools over the same kind and attribute have overlapping ranges: allowed; a collision is refused only by a uniqueness constraint.
- A unique attribute already holds a value nobody allocated: allocation skips it, across every range, as it does today.
- `start_range` / `end_range` written on a multi-range user pool: refused with the list of ranges; on a schema pool: the existing schema-pool refusal fires first.
- Both spellings supplied, on a pool mutation or in a schema declaration: refused.
- Exactly one of `start_range` / `end_range` declared in a schema: the other resolves to its former bound.
- A schema written before this change is loaded after it: identical meaning, plus one deprecation warning per attribute using the shorthand.
- The migration runs twice: idempotent, no duplicate range.
- A schema change moves a declared range so that a held value falls outside every range: refused, objects identified.
- A range of a schema-created pool is edited through the range's own create / update / delete mutations: refused.

## Requirements *(mandatory)*

### Functional Requirements

#### Ranges on a pool

- **FR-001**: A number pool MUST be able to hold zero, one or several ranges. Each range has a start, an end and an optional allocation weight, belongs to exactly one pool, and is branch-agnostic. *(PRD FR-001)*
- **FR-002**: Ranges MUST be addable and removable one at a time on a pool that is already in use. A range edit is never refused for what the pool has handed out, including removing a range that holds handed-out numbers. *(PRD FR-002)*
- **FR-003**: A handed-out number whose value falls outside every effective range MUST be retained and stay associated with the pool: invisible to allocation, excluded from utilization, and counted again as soon as a covering range is added. *(PRD FR-002a)*
- **FR-004**: Allocation MUST draw from the range with the highest weight first and empty it before moving to the next. A missing weight counts as zero. Ranges of equal weight are used lowest start first. Within a range the lowest free number is handed out. *(PRD FR-003)*
- **FR-005**: Ranges within one pool MUST NOT overlap, and a range's end MUST NOT be below its start. Such a range is refused when saved and the error names the clashing ranges. Ranges of different pools over the same kind and attribute MAY overlap; a collision between them is refused only by a uniqueness constraint. *(PRD FR-004, cross-pool clause dropped)*
- **FR-006**: Every pool that exists before this change MUST become a pool with one range covering its old span and no weight. The migration MUST leave what the pool handed out and its `start_range` / `end_range` values untouched, and MUST be idempotent. Utilization is carved out: FR-007 computes it from the effective space, so it moves for a pool whose span reaches outside the attribute's `[min_value, max_value]` or whose excluded values fall outside that span. That shift is a deliberate change carried by a changelog entry, not a migration effect. *(PRD FR-005, utilization carve-out from PRD FR-006)*
- **FR-007**: Size and utilization MUST be computed from the effective space: the union of the pool's ranges, intersected with the attribute's `[min_value, max_value]`, minus the excluded values that fall inside that union. Excluded values outside the union subtract nothing. *(PRD FR-006)*
- **FR-008**: A pool MUST report itself full only when every effective range is exhausted. A range that clamps to empty against the attribute's domain counts as exhausted. *(PRD FR-007)*
- **FR-009**: A pool with zero ranges MUST be legal. Its size is 0, its utilization reports 0 of 0 as 0 %, and allocation from it raises the existing pool-exhausted error.
- **FR-010**: Size, utilization, allocation order and fullness MUST all be derived from the same effective-space calculation, so that no two figures the pool reports can disagree.
- **FR-011**: The existing skip of values already present on a unique attribute MUST keep working and MUST cover every range of the pool. *(PRD FR-011 as amended by the addendum: scan kept in P1)*
- **FR-012**: Which numbers are unavailable MUST be worked out in the database across the range set. How much data sits inside a pool's ranges MUST NOT change how much memory an allocation holds. *(PRD FR-013)*

#### Single-bound shorthand

- **FR-013**: `start_range` / `end_range` on a pool MUST remain supported as an optional shorthand for a single range and MUST be marked deprecated in favour of `ranges`. Removal is out of scope for P1. *(PRD FR-005a)*
- **FR-014**: On read, `start_range` / `end_range` MUST return the bounds of the pool's range when the pool holds exactly one range, and null otherwise.
- **FR-015**: On write to a user-created pool, the shorthand MUST behave according to the pool's range count: with zero ranges it creates the pool's single range; with one range it rewrites that range's bounds in place, keeping the range's identity and weight; with more than one range it is refused, the error states the permitted usage and lists every range the pool holds by bounds and identifier, and the pool is left untouched.
- **FR-016**: Supplying the shorthand together with an explicit list of ranges in one write MUST be refused as conflicting spellings. Omitting the shorthand and supplying `ranges` is a legal write; omitting both on create is a legal write producing a zero-range pool.
- **FR-017**: On a schema-created pool, the existing refusal pointing the user at the default-branch schema MUST fire before any shorthand rule, whatever the range count.

#### Pools the schema creates

- **FR-018**: A number-pool attribute MUST accept either `start_range` / `end_range` or an explicit `parameters.ranges` list of `{start, end, weight}`. Declaring both MUST be refused. Declaring neither MUST produce a legal zero-range pool. An attribute written against the former `1` / `sys.maxsize` parameter defaults declares neither, so on upgrade it produces an empty pool where it produced a pool spanning `1`–`sys.maxsize`. This is a deliberate change, carved out of FR-019 and SC-003 and carried by a changelog entry with an upgrade note telling the author to declare the span they want. *(PRD FR-008, FR-041)*
- **FR-019**: A declaration carrying exactly one of `start_range` / `end_range` MUST resolve the other to its former default bound at validation time, so that a schema written before this change loads with identical meaning. The shorthand counts as supplied as soon as either field is set.
- **FR-020**: The schema declaration MUST be the source of truth for a schema-created pool's ranges. The pool's ranges are a runtime representation of that declaration, not a second authoring surface. *(PRD FR-037)*
- **FR-021**: When the schema creates a pool, its ranges MUST be materialised from the normalised declaration at creation. A new schema-created pool is never left with only scalar bounds and no range.
- **FR-022**: When the default-branch schema changes a number-pool attribute's ranges, the pool's ranges MUST be reconciled to the new declaration (created, updated, removed). Handed-out numbers stay recorded. A declaration with zero ranges is legal. *(PRD FR-037)*
- **FR-023**: A range declared in the schema MUST carry its own optional weight, set by the schema author and never inferred from declaration order. FR-004's rules apply unchanged. *(PRD FR-042)*
- **FR-024**: `start <= end` and intra-pool non-overlap MUST be enforced on the schema declaration as well as on the pool mutation. *(PRD FR-004)*
- **FR-025**: A schema change that would leave a value an object holds outside every declared range MUST be refused, and the offending objects identified. The check reads the values objects hold, not the pool's records. *(PRD FR-039)*
- **FR-026**: A change to `parameters.ranges` MUST pass through the same schema-change validation as a change to `start_range` / `end_range` does today, so that FR-025 cannot be bypassed by editing the list instead of the scalars.
- **FR-027**: Editing the ranges of a schema-created pool MUST be refused on every writable surface: the pool's own update carrying ranges, and the range's own create, update and delete. Each refusal points at the schema in the default branch. *(PRD FR-038)*

#### Deprecation signals

- **FR-028**: The deprecation of `start_range` / `end_range` MUST be visible: in the pool's schema definition, in the number-pool attribute parameters, as one deprecation warning per attribute declaring the shorthand in the schema-load response pointing at `parameters.ranges`, and as a deprecation marker in GraphQL introspection on the pool object type, its interface, and its create / update / upsert inputs.
- **FR-029**: A deprecation message declared on any attribute or relationship of any kind MUST reach GraphQL introspection through general propagation, not a special case for number pools.
- **FR-030**: No deprecation signal is required in mutation responses.
- **FR-031**: Both fields set in a schema declaration (shorthand and `ranges`) MUST be an error, not a silent precedence of one over the other. This is a deliberate divergence from how other deprecated attribute parameters are reconciled.

#### Compatibility

- **FR-032**: Existing frontend and API consumers MUST tolerate `start_range` / `end_range` being null on read, and MUST tolerate the pool utilization query returning one entry per range instead of one entry per pool.
- **FR-033**: The GraphQL type of `start_range` / `end_range` does not change; only their description loses its "(required)" suffix and gains the deprecation marker.

### Key Entities *(include if feature involves data)*

- **Number pool** (exists today): branch-agnostic; gains a set of ranges. Keeps `start_range` / `end_range` as deprecated single-range shorthand. Two kinds: user-created (ranges editable on the pool) and schema-created (ranges owned by the schema declaration).
- **Range** (new core kind): start, end, optional allocation weight; belongs to exactly one pool; branch-agnostic; inherits the weighted-resource generic so weight means what it means for IP pool resources. First core kind to use that generic.
- **Effective space** (derived, not stored): union of a pool's ranges ∩ the attribute's `[min_value, max_value]` − intersecting excluded values. The single source for size, utilization, allocation order and fullness.
- **Number-pool attribute parameters** (exists today, part of the published schema contract): gain `ranges` as a list of `{start, end, weight}`; `start_range` / `end_range` become optional and deprecated with no field default; single-bound resolution happens in validation.
- **Handed-out number record** (exists today): unchanged in shape. Records outside every effective range are retained and hidden.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator sets up one pool over a space with gaps and never receives a number from a gap. *(PRD SC-005)*
- **SC-002**: A space that needed one pool per piece is expressed as one pool, and the order the pieces are drawn from is the operator's choice, set by weighting them. *(PRD SC-006)*
- **SC-003**: A deployment that upgrades and changes nothing sees no change: every pre-existing pool reports the same handed-out numbers and the same `start_range` / `end_range` values as before the upgrade. Two deliberate changes are carved out and each carries a changelog entry: utilization, which FR-007 recomputes from the effective space, and a number-pool attribute declaring neither bound, which FR-018 turns into a zero-range pool. *(PRD SC-009 spirit, applied to P1)*
- **SC-004**: The migration is idempotent: a second run against a pool that already holds a covering range creates no second range.
- **SC-005**: Allocation on a fully allocated multi-range pool of 4094 numbers (a VLAN space split in several ranges) is measured, with its query plan inspected, and does not regress against the single-span walk. The figure is recorded, not gated. *(PRD SC-012, ungated in P1)*
- **SC-006**: Every refusal introduced by this slice (overlap, backwards range, conflicting spellings, shorthand on a multi-range pool, direct edit of a schema-created pool's ranges, unsafe schema change) names what the user must change and, where relevant, which ranges or objects are involved.
- **SC-007**: Every existing frontend screen and SDK call that reads a pool, or its utilization, works on a pool with zero or several ranges.
- **SC-008**: Every attribute and relationship deprecation declared in a schema appears in GraphQL introspection.

## Behaviour changes for the changelog

| Entry | Category |
|-------|----------|
| Utilization becomes sensitive to `min_value` / `max_value` and to which excluded values intersect the ranges. | Changed behaviour |
| `start_range` / `end_range` read as null on a pool with zero or more than one range. | Changed behaviour |
| A number-pool attribute declaring neither `start_range` nor `end_range` now creates a pool with zero ranges, where it created one spanning `1`–`sys.maxsize`. Declare the span the attribute needs. | Changed behaviour |
| `start_range` / `end_range` are deprecated in favour of `ranges` in the pool schema, in the number-pool attribute parameters and in GraphQL. | Deprecation |
| The shorthand is refused on a pool holding more than one range; the error lists the ranges to edit instead. | New refusal |
| Schema-created pools accept `parameters.ranges`; direct GraphQL edits of their ranges are refused. | Feature |
| A pool can hold several weighted ranges; ranges can be added and removed on a live pool. | Feature |
| The pool utilization query returns one entry per range for a number pool, each with its weight and figures, instead of one entry for the pool. | Changed behaviour |

The upgrade note addresses API consumers (nullable reads, deprecation), not only pool authors.

## Approvals needed

Using the repository's "ask first" list.

- [x] Database schema or migration change — new core kind for ranges, relationship from pool to ranges, migration creating one range per existing pool.
- [x] GraphQL change — new range kind with its generated mutations and their schema-pool guard, `ranges` relationship on the pool, deprecation markers on `start_range` / `end_range`, the shorthand refusals.
- [x] Published schema contract (ADR 0010, SDK type regeneration) — number-pool attribute parameters gain `ranges`, both scalars deprecated with no default, single-bound resolution, range-validity rules. Shared with P3's later `allocation_scope` change.
- [ ] New dependency
- [ ] CI/CD change
- [ ] Authentication or authorization change

## Assumptions

- No new frontend work ships in P1. Existing screens must keep working on the new read shape (FR-032); range management in the UI is deferred with the rest of the frontend scope.
- The former default bounds used for single-bound resolution (FR-019) are the ones the number-pool attribute parameters applied before this change: `1` for the start and the largest supported integer for the end.
- The schema that validates a number-pool attribute's ranges is the default-branch schema, consistent with the existing schema-pool refusal text.
- Weight semantics are those of the weighted-resource generic already used by IP pools: higher is drawn from first.
- Removal of `start_range` / `end_range` happens in a later major version and is not planned here.
- The hand-set-value skip on unique attributes (FR-011) is kept exactly as shipped in 1.11, generalised to the range set; its removal and the associated upgrade note belong to P2.
- The server-side log emitted when a deprecated attribute is processed was written for customer schemas; whether to restrict it to non-core namespaces or accept it firing for the core pool attributes is decided at planning time.
- The exact identifier under which the `ranges` parameter change registers for schema-change validation (FR-026) is confirmed against the existing validation code at implementation time.

## Out of scope

- P2: providing, attaching and detaching numbers; provenance; the record lifecycle matrix; deletion of the hand-set-value scan and the #10180 revert with its upgrade note.
- P3: `allocation_scope` on the pool and in attribute parameters (PRD FR-014 to FR-020, FR-043).
- P4: SDK identifier (PRD FR-032, FR-033).
- Bulk attach (PRD SC-004) and every frontend view.
- Cross-pool non-overlap between pools over the same kind and attribute (dropped from every slice).
- Removing `start_range` / `end_range`.
- Deprecation markers on GraphQL filter arguments derived from deprecated attributes (optional, not required for P1).

## Traceability to the base PRD

| PRD requirement | Spec requirement |
|-----------------|------------------|
| FR-001 | FR-001 |
| FR-002, FR-002a | FR-002, FR-003 |
| FR-003 | FR-004 |
| FR-004 (intra-pool only) | FR-005, FR-024 |
| FR-005 | FR-006 |
| FR-005a | FR-013 to FR-017 |
| FR-006 | FR-007, FR-010 |
| FR-007 | FR-008, FR-009 |
| FR-008 | FR-018 |
| FR-011 (addendum: scan kept) | FR-011 |
| FR-013 | FR-012 |
| FR-037 | FR-020 to FR-022 |
| FR-038 | FR-027 |
| FR-039 | FR-025, FR-026 |
| FR-041 | FR-018, FR-019, FR-031 |
| FR-042 | FR-023 |
| SC-005, SC-006, SC-009, SC-012 | SC-001, SC-002, SC-003, SC-005 |
