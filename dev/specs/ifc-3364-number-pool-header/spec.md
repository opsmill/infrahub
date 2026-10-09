# Feature Specification: Number pool details header

**Feature Branch**: `number-pool-header-ifc-3364`

**Created**: 2026-10-08

**Status**: Implemented

**Input**: build the header of the number pool details page to production quality and use it in the app. Ticket: [IFC-3364](https://opsmill.atlassian.net/browse/IFC-3364).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand a number pool from its header (Priority: P1)

A network or automation engineer opens a number pool, from the resource manager list or from a link on another node. From the header alone, without opening another page, form or menu, they can tell:

- the kind and the attribute that the pool allocates numbers to
- the fields that divide the pool's numbers into separate scopes, or that the pool has no scope
- whether the schema or users manage the pool
- which actions they can take on the pool

Without this header, the details page shows a generic title above a property list. The engineer has to read the kind, the attribute and the pool type as separate raw rows. Nothing shows whether the schema controls the pool. Edit stays available for pools that the schema created, and the change is refused only when the engineer saves it.

**Why this priority**: this is the only story. It is the part of the new number pool page that can ship without the backend work that the rest of that page needs.

**Independent Test**: open a schema-created pool and a user-created pool. For each, check every value in the header against the stored pool and check which actions are available.

**Acceptance Scenarios**:

1. **Given** a pool that the schema created for the attribute `asn` of `InfraAutonomousSystem`, with no allocation scope, **When** the engineer opens it, **Then**:
   - the header shows the pool name and a "Managed by schema" tag
   - the header shows "Allocates to InfraAutonomousSystem attribute `asn` with no scope"
   - Edit, Groups and Delete in the Actions menu are disabled, and their tooltip names the schema attribute
2. **Given** a pool that a user created, scoped by the fields `site` and `role`, **When** the engineer opens it, **Then**:
   - the header shows no managed-by tag
   - the header shows "scoped by Site + Role", using the field labels from the schema
   - Edit, Groups and Delete are enabled when the engineer has permission to update and delete the pool
3. **Given** an engineer without permission to update or delete the pool, **When** they open the Actions menu, **Then** Edit, Groups and Delete are disabled, with the same permission message as on other detail pages.
4. **Given** a pool with a description, **When** the engineer opens it, **Then** the description appears under the name. **Given** a pool without a description, **Then** no description line appears.
5. **Given** the engineer saves a new name or description from Actions → Edit, **When** the save succeeds, **Then** the header shows the new values without a page reload.
6. **Given** the engineer deletes a pool from Actions → Delete, **When** the delete succeeds, **Then** they are taken to the resource manager list.

### Edge Cases

- The pool's kind is not in the schema of the branch the engineer is viewing (the pool exists on all branches). The header shows the kind name as stored, without a link.
- An allocation scope field is not in the schema of the current branch. The header shows the field's stored name instead of a label, so no stored value is hidden.
- A schema-created pool has a long generated name, such as `InfraAutonomousSystem.asn [<id>]`. The name is cut to one line with an ellipsis, the full name appears on hover, and the tag stays visible.
- The engineer deletes a user-created pool that the schema of a branch still uses. The deletion is refused and the engineer receives the refusal message. The header does not check this in advance.
- The pool fails to load. The page shows its existing error screen, and the header shows no error of its own.
- On a narrow window, the name is cut first so the tag stays visible, and the "Allocates to" sentence wraps onto new lines instead of being cut.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST show the new header on the details page of number pools only. IP prefix pools and IP address pools keep the current header.
- **FR-002**: The header MUST show the pool name on one line, cut with an ellipsis when too long, with the full name on hover.
- **FR-003**: The header MUST show a "Managed by schema" tag when the schema created the pool, and no tag when a user created it.
  - The tag MUST have a tooltip that names the schema attribute that created the pool.
  - Selecting the tag MUST open the schema of the pool's kind in a modal, on that attribute, without leaving the page. When the kind is not in the schema of the current branch, selecting it MUST do nothing.
- **FR-004**: The header MUST show the pool's description, and MUST leave out the description line when the pool has none.
- **FR-005**: The header MUST show the pool's full ID, with a button that copies it.
- **FR-006**: The header MUST show the sentence "Allocates to `<kind>` attribute `<attribute>`", followed by "scoped by `<fields>`" or by "with no scope".
  - The kind, the attribute and each scope field MUST share one style.
  - The kind MUST appear as stored. Selecting it MUST open the schema of that kind in a modal, without leaving the page.
  - Selecting the attribute or a scope field MUST open the same modal on that field.
  - Each scope field MUST appear by its label from the schema of the current branch, separated by "+". When the field is not in that schema, it MUST appear by its stored name.
  - When the kind or a field is not in the schema of the current branch, selecting it MUST do nothing.
- **FR-007**: The header MUST contain the reload button and the node metadata (who created or last changed the pool, and when), in the same positions as on other node detail pages.
- **FR-008**: The reload button MUST reload the pool, its utilization and its allocated resources together.
- **FR-009**: The header MUST contain an Actions menu with these sections:
  - **Actions:** Copy ID, and Copy HFID (only when the pool has an HFID)
  - **Go to:** Tasks for this pool, View schema (the number pool schema, for every pool), GraphQL sandbox, and Documentation (only when the schema defines a documentation link)
  - **Manage:** Edit, Groups and Delete
- **FR-010**: System MUST disable Edit, Groups and Delete in the Actions menu when the schema created the pool, with a tooltip that names the schema attribute, so a schema-managed pool cannot be changed from the page.
- **FR-011**: System MUST disable Edit, Groups and Delete when the engineer lacks the matching permission, with the same permission message as on other node detail pages.
- **FR-012**: After a successful edit from the Actions menu, the header MUST show the saved values without a page reload.
- **FR-013**: After a successful delete from the Actions menu, System MUST take the engineer to the resource manager list.
- **FR-014**: While the pool loads, the header MUST show placeholders for the name and for the Actions menu.

### Key Entities

- **Number pool** (existing): a pool that hands out numbers to one attribute of one kind. The header reads its name, description, pool type (created by the schema or by a user), kind, attribute and allocation scope (the fields of the kind that divide the pool's numbers).
- **Schema of the pool's kind on the current branch** (existing): provides the labels of the allocation scope fields and the target of the schema links.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An engineer who opens a number pool can name its kind, attribute, scope fields and manager without opening another page, form or menu. Automated checks verify this as follows:
  - **End-to-end**, on a schema-created pool and a user-created pool, both without a scope: the name, the managed-by tag or its absence, the kind, the attribute and "with no scope".
  - **Component tests**: the "scoped by" sentence with the scope field labels, and a scope field or a kind that is missing from the schema of the current branch. No end-to-end data sets an allocation scope.
- **SC-002**: On a schema-created pool, Edit, Groups and Delete in the header's Actions menu are disabled for every engineer, including one with full permission, and each one names the schema attribute that defines the pool.
- **SC-003**: For every number pool in the test data, each value in the header (name, description, manager, kind, attribute, scope fields) matches the stored pool, including a scope field that is missing from the schema of the current branch.
- **SC-004**: The details pages of IP prefix pools and IP address pools are unchanged. Their existing tests pass without changes.

## Assumptions

- The pool type and the allocation scope are already stored on every number pool. No change to the data model or the API is needed.
- Actions → Edit opens the existing number pool edit form.
- The page body below the header does not change. This leaves these limitations until separate work replaces the body:
  - The property list shows the ID, name, description, kind, attribute and pool type that the header also shows.
  - The Edit button on the property list ignores the schema lock, so it stays enabled for schema-created pools.
  - The property list reads the pool through a separate query that the header's reload button does not reload, so it can show old values after a reload.
- The change is visible to users, so it needs a changelog entry.

### Out of Scope

- The rest of the new number pool page: the scope picker, the ranges card, the allocations table, the range editor and the create form.
- Headers of IP prefix pools and IP address pools.
- Renaming a schema-created pool, or changing its description, from the UI.
- Updating screenshots in the user documentation. This happens once the rest of the number pool page is built.
