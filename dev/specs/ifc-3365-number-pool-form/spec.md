# Feature Specification: Number pool create and edit form

**Feature Branch**: `number-pool-form-ifc-3365`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "We have a prototype for the create and edit form of a number pool at `/proto/number-pool?v=2`. We want to make it production ready and develop it." Refined in a grilling session; ticket [IFC-3365](https://opsmill.atlassian.net/browse/IFC-3365).

## User Scenarios & Testing *(mandatory)*

The users are network automation engineers who set up number pools, for example for VLAN IDs, AS numbers or subinterface unit IDs. Today they can create a pool in the UI with one range and no allocation scope. To create a scoped pool, or a pool with several weighted ranges, they send a GraphQL mutation or edit a schema file.

Both stories ship in the same release. The current form handles both create and edit and is removed, so shipping only one story would leave the other on a form that cannot handle pools with more than one range.

### User Story 1 - Create a scoped pool with several ranges (Priority: P1)

From the object list or the resource manager, the user opens the create form. They pick the node and the number attribute the pool assigns, optionally pick the fields that scope the pool, add one or more ranges with weights, and save once. The pool is created with its ranges and scope in that single save.

**Why this priority**: Creating a pool with a scope or several ranges is not possible in the UI today. It is the capability users are missing.

**Independent Test**: Create a pool from the form with a scope and two weighted ranges, then open its edit form and compare it with what was entered.

**Acceptance Scenarios**:

1. **Given** a node `InfraSubinterface` with a non-unique number attribute `unit_id`, **When** the user creates a pool on `unit_id`, scoped by `device`, with ranges 100–199 (weight 10) and 300–399, **Then** the pool's edit form shows both ranges with their weights, and "Scoped by: Device" as read-only text.
2. **Given** the user picked the node `InfraAutonomousSystem` and its unique attribute `asn`, **When** the user looks at "Scoped by", **Then** it is disabled with the reason "asn is unique, so the pool has one sequence", and any scope picked earlier is cleared.
3. **Given** the user entered ranges 100–199 and 150–250, **When** the user tries to save, **Then** both rows are marked as overlapping and nothing is sent.
4. **Given** the user entered a range 4000–5000 on an attribute that accepts 1–4094, **When** the user saves, **Then** the sheet stays open with every value kept, and the refusal message appears in one alert above the footer.

---

### User Story 2 - Edit a pool's ranges (Priority: P2)

From a pool's details page, the user opens Edit. They change the name, the description or the ranges: add a range, remove one, change its bounds or its weight. The node, the attribute and the scope are shown but cannot be changed, because they are fixed once the pool exists.

**Why this priority**: It ships with Story 1, but it is ranked second because editing ranges is already possible through the current form for pools with a single range.

**Independent Test**: Edit an existing pool's ranges from the details page, then reopen the edit form and compare it with what was entered.

**Acceptance Scenarios**:

1. **Given** an existing pool with range 100–199, **When** the user changes the end to 299 and adds 500–599, **Then** the reopened edit form shows 100–299 and 500–599, and numbers already assigned stay assigned.
2. **Given** an existing pool, **When** the user opens Edit, **Then** the node, the attribute and the scope are shown as read-only text.
3. **Given** a pool defined by a schema attribute, **When** the user opens the actions menu, **Then** Edit stays locked, as it is today.

---

### Edge Cases

- **Range outside the attribute's limits, or a range whose end is lower than its start:** the form sends it, the backend refuses the save, and the refusal message appears in the alert above the footer.
- **Scope picked on a branch for a node or a field that the default branch does not have:** the picker lists it, because it is built from the current branch's schema. The backend refuses it on save, because a pool's scope is checked against the default branch's schema. This is a known limitation of this release.
- **A range with assigned numbers is removed or its bounds change:** the save succeeds and the numbers stay assigned to their holders. Numbers that fall outside every range are no longer counted in the pool's usage. The form shows no warning about this.
- **Empty Weight field:** the pool allocates from that range the same way as from a range with weight 0.
- **Two ranges with the same weight:** allowed. The pool allocates from the one with the lower start first.
- **No ranges in the form:** the form shows "No ranges. The pool can't hand out numbers until you add one." The user can still save.
- **Rows entered out of numeric order**, for example 40–50 above 1–19: allowed. The form keeps the order the user entered.

## Requirements *(mandatory)*

### Functional Requirements

**Where the form opens**

- **FR-001**: The new form MUST open wherever a number pool is created or edited, including:
  - the "Add" button on the object list;
  - the resource manager page;
  - the Edit action on a pool's details page.

  The current number pool form is removed.
- **FR-002**: Pools defined by a schema attribute MUST keep their Edit lock.

**Node, attribute and scope**

- **FR-003**: The Node list MUST show the nodes and generics on the current branch that have at least one number attribute that is not read-only. Each entry shows the label and the kind, and the user can search by either.
- **FR-004**: The Attribute list MUST show only the chosen node's number attributes that are not read-only. Each entry shows the attribute's limits, and "Unique" where it applies.
- **FR-005**: The form MUST NOT preselect an attribute.
- **FR-006**: The "Scoped by" picker MUST list only the fields that can scope the pool, and hide the others. A field is hidden when it is:
  - the attribute the pool assigns;
  - a relationship with cardinality many;
  - a List, JSON or Any attribute;
  - optional.
- **FR-007**: When the chosen attribute is unique, the form MUST disable "Scoped by" with the reason "\<attribute\> is unique, so the pool has one sequence", and clear any scope already picked.
- **FR-008**: Changing the node MUST clear the attribute and the scope.
- **FR-009**: On edit, the form MUST show the node, the attribute and the scope as read-only text.

**Ranges**

- **FR-010**: Users MUST be able to add, remove and change ranges. Each range has a start, an end and an optional weight.
- **FR-011**: Before sending, the form MUST check only that:
  - each range has a start and an end;
  - start and end are whole numbers;
  - no two ranges overlap. An overlap is flagged on both rows involved.
- **FR-012**: The form MUST send ranges as entered, and leave every other range rule to the backend: attribute limits, and an end lower than the start.
- **FR-013**: The form MUST keep range rows in the order the user entered them, and MUST NOT re-sort them while it is open.
- **FR-014**: An empty Weight field MUST be saved as "no weight", and a number MUST be saved as that weight. The Weight field's placeholder shows "0".
- **FR-015**: The ranges section MUST explain the allocation order: "Highest weight is used first. Ranges with equal weight are used from the lowest start."
- **FR-016**: When the ranges list is empty, the form MUST show "No ranges. The pool can't hand out numbers until you add one." This message does not block saving.
- **FR-017**: The edit form MUST NOT warn about assigned numbers when a range is removed or its bounds change.

**Saving**

- **FR-018**: Creating a pool MUST save the pool, its ranges and its scope in one save, so the pool never exists without the ranges the user entered. Editing a pool MUST save its name, description and ranges in one save.
- **FR-019**: After a successful save, the screen that opened the form MUST decide what happens next. Users see the same result as today after creating or editing a pool.
- **FR-020**: When the backend refuses a save, the sheet MUST stay open with every value the user entered.
- **FR-021**: Every refusal from the backend MUST show as one message above the footer. The form does not parse the message to place it under a field.
- **FR-022**: The prototype at `/proto/number-pool` and its sample data MUST be removed in the same release.

### Key Entities *(include if feature involves data)*

All entities exist already. This feature adds none.

- **Number pool**: assigns numbers to one number attribute of one node. It has a name, a description, the node, the attribute, and an optional allocation scope. The node, the attribute and the scope are set when the pool is created and do not change afterwards.
- **Number pool range**: one range of a pool, with a start, an end (both included) and an optional weight. When a pool is edited, a range is identified by its start and end. Changing either bound replaces the range with a new one.
- **Allocation scope**: the ordered list of fields of the node that divide the pool into separate sequences, one sequence per combination of values. Usage is counted separately for each combination and is never added up across them.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can create a pool with a node, an attribute, a scope of one or two fields and three weighted ranges in a single save from one form, without writing a GraphQL mutation or editing a schema file.
- **SC-002**: For 100% of pools created or edited through the form, what the user entered is shown back:
  - in the pool's edit form, the ranges with their bounds and weights, the node, the attribute, and the scope fields in the order picked.
- **SC-003**: The "Scoped by" picker offers 0 fields that the backend refuses because of their type, cardinality or optional flag. The only exception is a field that exists only on the current branch.
- **SC-004**: After the release, 0 screens send a number pool with the deprecated single-range start and end fields.
- **SC-005**: Every acceptance scenario of User Story 1 and User Story 2 passes as an automated end-to-end test.

## Assumptions

- **Users:** the people who create and edit number pools have create and update permission on number pools and on number pool ranges.
- **Backend, already in place:**
  - Creating or updating a pool accepts its ranges and its scope in the same request.
  - The backend checks range overlaps, range direction, attribute limits and every scope rule, and is the final check for all of them.
  - The backend refuses any change to a pool's scope after the pool is created.
- **Allocation order:** the backend allocates from the range with the highest weight first, then from the lowest start. A range with no weight counts as weight 0.
- **Usage:** usage is reported per range and per scope combination.
- **Out of scope:**
  - Changing the node, the attribute or the scope of an existing pool.
  - Editing pools defined by a schema attribute.
  - Warnings about assigned numbers when ranges change.
  - Building the "Scoped by" picker from the default branch's schema.
  - Ranges whose end is lower than their start.
  - Changes to what the pool details page shows. The details page does not show a pool's scope yet, reads a stored scope as empty, and cannot show the ranges or usage of a scoped pool, because its utilization query refuses a scoped pool without a division. These are left for a separate ticket.
- **Dependency:** the pool details page from [IFC-3364](https://opsmill.atlassian.net/browse/IFC-3364) and [IFC-3362](https://opsmill.atlassian.net/browse/IFC-3362) is where users check the result of a save.
- **Governance gates:** this feature does not change the database schema, the GraphQL schema, CI/CD, authentication or authorization. It adds no dependency.
