# Feature Specification: Number pool create and edit forms with weighted ranges

**Feature Branch**: `ple-number-pool-form-ifc-3361`

**Created**: 2026-10-08

**Status**: Draft

**Input**: Jira [IFC-3361](https://opsmill.atlassian.net/browse/IFC-3361) (epic [IFC-3065](https://opsmill.atlassian.net/browse/IFC-3065), idea [INFP-308](https://opsmill.atlassian.net/browse/INFP-308)). A user who manages number pools needs to create a pool with several weighted ranges and an allocation scope, and later change the name, description and ranges of that pool, from the web interface. Prototype: branch `bab-proto-number-pool`, `frontend/app/src/pages/proto/number-pool` (sample data only).

Related specs: [`dev/specs/ifc-3065-number-pool-ranges`](../ifc-3065-number-pool-ranges/spec.md) (ranges and their GraphQL contract), [`dev/specs/ifc-3185-scoped-number-pools`](../ifc-3185-scoped-number-pools/) (allocation scope).

## Clarifications

### Session 2026-10-08

- Q: When the server refuses a range right after the pool was created, what does the create form do? → A: The form stays open and switches to editing the newly created pool: it reloads the stored ranges, keeps the rows not yet saved, and shows the server message; saving again applies only the remaining differences.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create a number pool with several ranges (Priority: P1)

A network engineer creates a number pool for a node kind and one of its number attributes (for example the VLAN ID of an interface). They give it a name, an optional description, and one or more ranges. Each range has a start, an end and an optional weight. The pool hands out numbers from the range with the highest weight first.

**Why this priority**: Today the form accepts only one start and one end value, so a pool with several ranges can be created only through GraphQL or the SDK. This is the core of the ticket.

**Independent Test**: Open the create form for a number pool, fill in node kind, attribute, name and two ranges with different weights, save, and view the new pool with both ranges.

**Acceptance Scenarios**:

1. **Given** the create form is open, **When** the user selects a node kind, a number attribute, enters a name and adds two ranges 100–199 (weight 10) and 300–399 (no weight), and saves, **Then** the pool exists with both ranges and their weights, and the form closes.
2. **Given** the create form, **When** the user adds a range whose end is lower than its start, **Then** the row shows an error and the form cannot be saved.
3. **Given** the create form with two ranges 100–199 and 150–250, **Then** both rows show that they overlap each other, naming the other range, and the form cannot be saved.
4. **Given** the create form, **When** the user removes every range, **Then** the form can still be saved and shows a hint that the pool cannot hand out numbers until it has a range.
5. **Given** the selected attribute accepts 1–4094, **When** the user enters a range 0–5000, **Then** the row shows a hint that the range is clipped to 1–4,094 by the attribute limits, and saving is still allowed.

---

### User Story 2 - Change the ranges of an existing pool (Priority: P1)

An operator opens an existing user-created pool to add a range, remove one, resize one or change its weight. They can also change the name and description. They view what the pool allocates (node kind, attribute, allocation scope) as read-only text, in the same layout as in the create form.

**Why this priority**: Pools fill up and requirements change; without this the operator has to call the API for every range change.

**Independent Test**: Open the edit form of a pool with one range, add a second range, change the weight of the first, save, and view both ranges with the new weight.

**Acceptance Scenarios**:

1. **Given** an existing pool with ranges 100–199 and 300–399, **When** the user opens the edit form, **Then** both ranges are listed as editable rows, and the node kind, attribute and allocation scope are displayed as read-only text and badges with no controls to change them.
2. **Given** the edit form, **When** the user removes 300–399, adds 500–599, changes the weight of 100–199 and saves, **Then** the pool has ranges 100–199 (new weight) and 500–599.
3. **Given** the edit form, **When** the user changes only the name or description and saves, **Then** the ranges are unchanged.
4. **Given** a save in which one range change is refused by the server, **Then** the form stays open, shows the server message, and reloads the ranges as they are stored, so the user sees which changes were applied.

---

### User Story 3 - Set the allocation scope when creating a pool (Priority: P2)

When creating a pool, the engineer can choose fields of the node kind that divide the pool's number space (for example one sequence per device). Only required fields can be chosen. Fields that cannot be used are listed with the reason.

**Why this priority**: The allocation scope can only be set at creation from this form; it is a smaller audience than ranges, and the server-side behaviour for scoped allocation is still being delivered ([IFC-3349](https://opsmill.atlassian.net/browse/IFC-3349)).

**Independent Test**: Create a pool for a node kind with a required relationship, choose that relationship as the scope, save, and view the scope on the pool.

**Acceptance Scenarios**:

1. **Given** the create form with a node kind selected, **When** the user opens the scope picker, **Then** the kind's fields are listed; required fields can be chosen; optional, list and JSON fields are listed but cannot be chosen, each with the reason.
2. **Given** the user has chosen one or more scope fields, **When** they change the node kind, **Then** the chosen scope is cleared.
3. **Given** a pool created with a scope, **When** the user opens its edit form, **Then** the scope is displayed as badges, in the same place and layout as the create form, with no controls.
4. **Given** the user selects no scope, **Then** the pool is created without a scope.

---

### User Story 4 - View the ranges of a pool defined in the schema (Priority: P3)

Some pools are created from the schema. Their ranges can be changed only by changing the schema on the default branch. The user can still change the name and description.

**Why this priority**: Prevents the user from preparing range changes that the server always refuses.

**Independent Test**: Open the edit form of a pool created from the schema and check that ranges are displayed as text with the reason.

**Acceptance Scenarios**:

1. **Given** a pool defined in the schema, **When** the user opens the edit form, **Then** its ranges are displayed as read-only text, with a note that they are changed in the schema on the default branch, and name and description stay editable.

---

### Edge Cases

- Two rows with identical bounds are reported as overlapping.
- A start or end that is empty or not a whole number is an error on that row.
- A weight that is empty is allowed and means lowest priority; a weight that is not a whole number or is negative is an error.
- A save that moves two ranges past each other (for example 1–10 and 11–20 becoming 1–15 and 16–20) may be refused part way by the server; the form reports it as in Story 2, scenario 4. Accepted for this version.
- Removing a range from which numbers are already allocated is allowed without a warning; numbers already assigned stay on their objects.
- The create form submits the pool first; if the pool is created but a range is then refused, the form switches to editing that pool (FR-015), so a second save does not create a duplicate pool.
- When the selected attribute is unique on its own and a scope is chosen, the scope picker shows a warning that numbers cannot repeat across scopes, as in the prototype; saving is still allowed.
- A node kind with no required fields shows an empty scope picker with an explanation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The create form MUST collect node kind, number attribute, name, optional description, optional allocation scope, and zero or more ranges.
- **FR-002**: Each range row MUST have a start, an end and an optional weight, and the user MUST be able to add and remove rows.
- **FR-003**: The form MUST refuse to save when a row has an empty or non-integer start or end, an end lower than its start, a negative or non-integer weight, or overlaps another row; each error MUST be shown on the affected row, and an overlap MUST name the other range.
- **FR-004**: The form MUST show a non-blocking hint on a row whose bounds fall outside the minimum or maximum of the selected attribute, stating the bounds it is clipped to.
- **FR-005**: The form MUST show a non-blocking hint when the pool has no range, stating that it cannot hand out numbers until a range is added.
- **FR-006**: The edit form MUST let the user change name, description and ranges of a user-created pool.
- **FR-007**: The edit form MUST display node kind, attribute and allocation scope as read-only text and badges, in the same layout and position as the inputs of the create form.
- **FR-008**: On save, the edit form MUST apply only the differences between the stored ranges and the form: remove deleted ranges, update changed ranges, add new ranges. It MUST apply them in this order: removals, then ranges that become smaller, then ranges that become larger, then additions.
- **FR-009**: When the server refuses any part of a save, the form MUST stay open, show the server message, stop applying further changes, and reload the stored pool and ranges.
- **FR-010**: The scope picker MUST list the fields of the selected node kind, allow only required fields to be chosen, and show the reason next to each field that cannot be chosen (optional, list, JSON).
- **FR-011**: Changing the node kind in the create form MUST clear the chosen attribute and scope.
- **FR-012**: For a pool defined in the schema, the edit form MUST display the ranges as read-only text with a note that they are changed in the schema on the default branch.
- **FR-013**: The forms MUST NOT show the deprecated single start and end range fields.
- **FR-015**: When the server refuses a range after the pool was created, the create form MUST stay open, switch to editing the created pool, reload the stored ranges, keep the rows not yet saved, and show the server message; a second save MUST apply only the remaining differences.
- **FR-016**: The scope picker MUST treat a relationship of cardinality many as a field that cannot be chosen, with the reason.
- **FR-017**: Range rows MUST be listed on load by weight (highest first) then by start; rows added by the user MUST be appended at the end, and rows MUST NOT reorder while the user types.
- **FR-014**: The existing end-to-end tests that use the single start and end range fields MUST be updated to the new form, and one end-to-end test MUST create a pool with several ranges and then edit it.

### Key Entities

- **Number pool**: name, description, node kind, number attribute, allocation scope (list of field names of the node kind), pool type (user-created or defined in the schema), ranges.
- **Number pool range**: start, end, optional weight; belongs to one pool. Ranges of one pool cannot overlap. Higher weight is used first; no weight means lowest priority.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can create a pool with three ranges and a scope from the web interface without using GraphQL or the SDK, in under 2 minutes.
- **SC-002**: Every invalid range entry listed in FR-003 is reported on its row before any request reaches the server.
- **SC-003**: After any refused save, the ranges displayed in the form match the ranges stored on the server.
- **SC-004**: The create and edit forms display the "what it allocates" block in the same layout; only the values differ (inputs versus text and badges).

## Assumptions

- The allocation scope is stored as a list of field names in the notation of uniqueness constraints; the server does not validate it on this branch ([IFC-3348](https://opsmill.atlassian.net/browse/IFC-3348) in review), so the form applies the "required fields only" rule itself.
- FR-016 and FR-017 were decided during clarification without a user question: FR-016 follows the uniqueness-constraint notation that the scope reuses, which addresses a relationship of cardinality one; FR-017 keeps the prototype's ordering (weight, then start) without moving rows during typing. The plan must confirm FR-016 against the backend.
- Ranges are saved one by one after the pool; the server has no all-or-nothing save for a pool and its ranges.
- The allocation scope cannot be changed after creation from this form, although the server accepts an update (decision by Paul Leménager, 2026-10-08).
- The pool details page, usage figures and allocations list from the prototype are out of scope ([IFC-3329](https://opsmill.atlassian.net/browse/IFC-3329), [IFC-3347](https://opsmill.atlassian.net/browse/IFC-3347)).
- No warning is shown when a range from which numbers were allocated is removed (decision by Paul Leménager, 2026-10-08).
