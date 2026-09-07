# Feature Specification: Resource-pool form fields — value-or-pool tabs and target-kind override

**Feature Branch**: `ple-ifc-2764-pool-kind-override`

**Created**: 2026-09-07

**Status**: Draft

**Input**: IFC-2764 — allow selecting the target object kind for "from-pool" allocations in the UI, plus the form restructuring that turned out to be required to make it comprehensible.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Allocate a chosen kind from a pool (Priority: P1)

A user fills in a field that points at a generic IP kind, which several concrete kinds can satisfy. They choose to allocate from a resource pool. The pool has a default kind, but this object needs a different one. The user picks the kind they want and saves; the object that gets created is of the kind they picked, not the pool's default.

**Why this priority**: This is the ticket. Without it a pool can only ever produce one kind of object, so a pool serving a generic relationship is unusable for any sibling kind.

**Independent Test**: With a pool whose default is kind A and a generic that also permits kind B, allocate with B chosen and confirm the created object is a B.

**Acceptance Scenarios**:

1. **Given** a pool defaulting to kind A on a field permitting kinds A and B, **When** the user allocates having chosen B, **Then** an object of kind B is created and linked.
2. **Given** the same field, **When** the user allocates without choosing a kind, **Then** an object of the pool's default kind A is created.
3. **Given** the same field, **When** a kind that the field does not permit is requested, **Then** the allocation is refused with a message naming the kinds that are permitted.
4. **Given** an allocation already made under a reservation identifier, **When** the same identifier is re-allocated asking for a different kind, **Then** it is refused rather than silently returning the original.

---

### User Story 2 - Choose between providing a value and allocating from a pool (Priority: P2)

A user meets a field that can either be filled in directly or satisfied from a pool. The two ways of filling it in are presented as an explicit choice, and that choice looks and behaves the same in every field that supports pools.

**Why this priority**: Today the pool is a small button beside the value input, and on a generic relationship the user must first choose a "Kind" that has no bearing on which pool they may pick — the two controls contradict each other. Making the two modes explicit is what removes the contradiction; doing it in only some fields would trade one inconsistency for another.

**Independent Test**: Open every field type that supports pools and confirm each presents the same two-way choice, and that a field which cannot use a pool is unchanged.

**Acceptance Scenarios**:

1. **Given** a field that supports pools, **When** it renders, **Then** the user is offered exactly two ways to fill it in: provide the value, or allocate from a pool.
2. **Given** a field that does not support pools, **When** it renders, **Then** it looks exactly as it does today, with no added chrome.
3. **Given** a field pointing at a generic kind, **When** the user chooses to allocate from a pool, **Then** they can reach and use the pool without first choosing a kind.
4. **Given** a staged value in one mode, **When** the user switches to the other mode, **Then** the staged value is discarded, because a field cannot be both provided and allocated.
5. **Given** a field the user may not edit, **When** it renders, **Then** neither mode can be used.

---

### User Story 3 - Understand what the pool will do, and what I am overriding (Priority: P3)

Having chosen a pool, the user can see what that pool would produce on its own, and can override the prefix length and the target kind. Each override says what the default is and makes clear that leaving it alone keeps that default.

**Why this priority**: An unlabelled control beside a pool reads as a required choice. Users reported not understanding where the default type came from or that it could be overridden at all.

**Independent Test**: Select a pool and confirm both overrides are labelled, show the pool's own default, and state that leaving them alone keeps it.

**Acceptance Scenarios**:

1. **Given** a chosen pool, **When** the pool panel renders, **Then** the pool is shown on its own line and both overrides share the line beneath it, each labelled.
2. **Given** a chosen pool, **When** the user inspects either override's explanation, **Then** it names the pool's default and says that leaving the control alone keeps that default.
3. **Given** a field where only one kind is possible, **When** the pool panel renders, **Then** no kind override is offered, because there is nothing to override.

---

### User Story 4 - Return to an object and find its allocation intact (Priority: P4)

A user reopens an object whose value was allocated from a pool. The form opens on the pool mode, shows which pool it came from, and does not offer to re-cut an allocation that already exists.

**Why this priority**: With an explicit two-way choice, opening on the wrong side actively misinforms the user about where a value came from — a failure mode that did not exist when the pool was merely a button.

**Independent Test**: Open an object with a pool-allocated value and confirm the pool mode is active, the pool is named, and neither override is offered.

**Acceptance Scenarios**:

1. **Given** an object whose value came from a pool, **When** the form opens, **Then** the pool mode is active and names the pool.
2. **Given** a value inherited from a profile or a template, **When** the form opens, **Then** the value mode is active and its provenance is indicated as it is today.
3. **Given** an allocation that has already been resolved, **When** the pool mode renders, **Then** no override is offered, because an existing allocation's kind and mask cannot be changed.

---

### User Story 5 - Verify every availability rule (Priority: P5)

A maintainer can determine, and prove by test, exactly when a pool and each override are offered — without reading the implementation.

**Why this priority**: The rules span three independent layers and are easy to get wrong; the layering is what made the original behaviour confusing to reason about. Enables review and prevents regression, but delivers no direct user value.

**Independent Test**: Load the harness schema and data locally and walk every row of the availability matrix by hand; run the suites and see each row asserted.

**Acceptance Scenarios**:

1. **Given** the harness schema and data, **When** a maintainer loads them locally, **Then** every combination in the availability matrix can be reached by hand in the UI.
2. **Given** the test suites, **When** they run, **Then** each row of all three layers is asserted, including the cases where nothing should be offered.

---

### Edge Cases

- A field whose relationship accepts many values rather than one: no pool is offered at all.
- A field whose target is a single concrete kind: the pool may be used, but no kind override is offered because the kind is already pinned.
- A generic target implemented by exactly one kind: pool offered, kind override withheld.
- A field whose target has nothing to do with IP addressing: no pool, no overrides.
- A value inherited from a template that itself references a pool: the pool is shown for provenance but is not the user's choice and is not submitted.
- A field that can use a pool only while creating an object, not while editing one.
- A number-valued field served by a pool of numbers: pool offered, neither override applies.
- A pool whose own default kind is not among those the field permits: the allocation still succeeds, because the default is not re-validated — only an explicit request is.
- A request that arrives by an untyped side channel rather than the documented one: validated identically.
- An object created from a template that references a pool: allocation uses the pool's default; overrides are out of scope (tracked separately).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When a field points at a generic kind that several concrete kinds satisfy, users MUST be able to choose which concrete kind a pool allocation creates.
- **FR-002**: When no kind is chosen, the system MUST allocate the pool's own default kind.
- **FR-003**: The system MUST refuse a requested kind that the field does not permit, and the refusal MUST name the permitted kinds.
- **FR-004**: The system MUST refuse to change the kind of an allocation already held under a reservation identifier.
- **FR-005**: The system MUST validate only a kind the caller explicitly requested, and MUST NOT re-validate a pool's own configured default, so that pools which work today continue to work.
- **FR-006**: The system MUST apply the same validation whether the kind arrives through the documented field or an untyped side channel.
- **FR-007**: Every field that can be satisfied from a pool MUST present the two ways of filling it in as an explicit, equally-weighted choice.
- **FR-008**: That presentation MUST be identical across all such fields, delivered together, with no field left on the previous presentation.
- **FR-009**: The change MUST NOT alter *whether* a pool is offered for any field; only how the choice is presented.
- **FR-010**: A field that cannot use a pool MUST render exactly as it does today.
- **FR-011**: For a field pointing at a generic kind, the pool MUST be reachable without the user first choosing a kind, and any kind picker used for choosing an existing object MUST NOT appear alongside the pool.
- **FR-012**: Switching between the two modes MUST discard the value staged in the abandoned mode.
- **FR-013**: The pool MUST occupy its own line, with the prefix-length and target-kind overrides sharing the line beneath it.
- **FR-014**: Each override MUST carry a visible label and an explanation naming the pool's default and stating that leaving the control alone keeps that default.
- **FR-015**: The target-kind override MUST be offered only when an override is meaningful: the allocation is still pending, the pool is an IP pool, and more than one kind is possible.
- **FR-016**: A field the user may not edit MUST NOT permit either mode to be used, including the pool.
- **FR-017**: The mode active when a form opens MUST reflect where the existing value actually came from.
- **FR-018**: A resolved allocation MUST NOT offer either override.
- **FR-019**: The two-way choice MUST be visually subordinate to the field's own label, so that the label remains the primary separation between fields.
- **FR-020**: A harness MUST exist that makes every row of the availability matrix reachable by hand locally, and every row MUST be asserted by automated tests.
- **FR-021**: Shared test and documentation helpers that encode the previous presentation MUST be updated, including regenerating any documentation imagery that shows the affected fields.

### Key Entities

- **Resource pool**: A source of values, configured with a default target kind and, for IP pools, a default prefix length. The thing a user picks in the pool mode.
- **Target kind**: The concrete kind of object an allocation creates. Defaults to the pool's configured kind; overridable per allocation when the field permits more than one.
- **Field value provenance**: Where a field's current value came from — the user, the schema, a profile, a template, or a pool. Determines which mode a form opens on and what may be changed.
- **Availability matrix**: The three-layer statement of when a pool is offered, when each override is offered, and which requested kinds are accepted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can allocate a non-default kind from a pool without reading documentation or asking for help.
- **SC-002**: Every field in the product that can use a pool presents the choice identically; a reviewer sampling them finds no field on the old presentation.
- **SC-003**: Reaching a pool on a field pointing at a generic kind takes no choice that does not affect the outcome.
- **SC-004**: For any pool-backed field, a user can state what the pool would produce by default without changing anything.
- **SC-005**: Every row of the availability matrix is reachable by hand in a local instance and asserted by an automated test.
- **SC-006**: No field the user may not edit exposes a usable pool control.
- **SC-007**: Reopening an object with a pool-allocated value shows its provenance correctly on first render.
- **SC-008**: The change introduces no regression in the existing automated gates.

## Assumptions

- The availability of a pool per field is treated as correct as it stands and is out of scope; only presentation changes. This includes the existing rule that certain attribute fields may use a pool while creating an object but not while editing one.
- Target-kind override for values allocated via object templates is out of scope and tracked separately (IFC-3135), because a template stores only a reference to the pool and has nowhere to record an override.
- Renaming the existing public prefix-length input field is out of scope and tracked separately (IFC-2945).
- Tightening validation on the previously-unvalidated prefix-pool kind input is accepted as a deliberate behaviour change; that path had no test coverage and an unrelated kind could not have produced a usable object.
- The two modes are mutually exclusive by nature, so discarding the abandoned mode's staged value on a switch is correct rather than lossy.
- Documentation imagery showing these fields will change, and regenerating it is part of the work rather than a follow-up.
- Existing behaviour already delivered on this branch (kind override plumbing, server-side validation, the first migrated field, the local trial schema) is treated as the current baseline; remaining work is the other fields, the plumbing that blocks them, and the harness.
