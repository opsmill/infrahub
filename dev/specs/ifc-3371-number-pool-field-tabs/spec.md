# Feature Specification: Number attribute — set a number or take it from a number pool

**Feature Branch**: `ple-number-pool-field-ifc-3371`

**Created**: 2026-10-09

**Status**: Draft

**Input**: [IFC-3371](https://opsmill.atlassian.net/browse/IFC-3371) (parent epic
[IFC-3363](https://opsmill.atlassian.net/browse/IFC-3363), product card
[INFP-308](https://opsmill.atlassian.net/browse/INFP-308)). Frontend only. In the object create
and edit forms, a plain Number attribute that a number pool targets reuses the value-or-pool tabs
of the IP prefix and IP address fields ([IFC-2764](../ifc-2764-pool-field-tabs/spec.md)). The
**Value** tab takes a number and sends it alone. The **From pool** tab takes a pool and an
optional number: with a number the pool records it as used (attach), without one the pool
allocates the next free number. Backend contract:
[`from-pool-intent.md`](../ifc-3184-pool-number-attach/contracts/from-pool-intent.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Allocate the next free number from a pool (Priority: P1)

A network engineer creates a VLAN. The VLAN ID attribute is served by a number pool. They open
the **From pool** tab, pick the pool, leave the number empty and save. The VLAN gets the next free
number in the pool, and the pool counts it as used.

**Why this priority**: This is the existing allocation journey. It must keep working once the
pool tab gains a number input, because it is the most common use of a number pool.

**Independent Test**: Create a node with the pool picked and the number empty; confirm the node
holds a number from the pool's range and the pool lists it as allocated.

**Acceptance Scenarios**:

1. **Given** a create form for a kind whose Number attribute a pool targets, **When** the user
   picks the pool, leaves the number empty and saves, **Then** the node holds the next free number
   of that pool and the pool reports it as allocated.
2. **Given** the pool tab with a pool picked, **When** the number input is empty, **Then** the
   input explains that leaving it empty allocates the next free number.

---

### User Story 2 - Set a specific number and have the pool record it (Priority: P1)

The same engineer must use VLAN 42 because it already exists on the network. In the **From pool**
tab they pick the pool, type 42 and save. The VLAN holds 42, and the pool records 42 as used so it
never offers 42 to anyone else.

**Why this priority**: This is the capability the ticket exists for. Without it, manual and
automatic allocation cannot coexist in one pool (INFP-308, problem 1).

**Independent Test**: Create a node with a pool and the number 42; confirm the node holds 42 and
the pool lists 42 as used. Allocate again from the same pool and confirm 42 is not offered.

**Acceptance Scenarios**:

1. **Given** the pool tab, **When** the user picks a pool, types a number and saves, **Then** the
   node holds that number and the pool reports it as used.
2. **Given** a number already held by another node on a unique attribute, **When** the user saves
   it through the pool tab, **Then** the form shows the uniqueness error that the backend returns,
   on the field.
3. **Given** a number outside the pool's ranges, **When** the user saves it through the pool tab,
   **Then** the save succeeds, because the pool refuses no number a user provides.

---

### User Story 3 - Set a number without any pool (Priority: P2)

A user types a number in the **Value** tab and saves. No pool records it.

**Why this priority**: Unchanged behaviour for anyone who does not want a pool. It must stay
exactly as it is.

**Independent Test**: Create a node with a number in the Value tab; confirm the node holds it and
no pool lists it.

**Acceptance Scenarios**:

1. **Given** the Value tab on a create form, **When** the user types a number and saves, **Then**
   the node holds the number and no pool reports it.
2. **Given** a Number attribute that no pool targets, **When** the form renders, **Then** the
   field shows the number input alone, with no tabs, exactly as today.

---

### User Story 4 - Edit a node whose number a pool tracks (Priority: P2)

A user reopens a VLAN whose ID the pool tracks. The form opens on the **From pool** tab with the
pool picked and the current number in the number input. The user can leave it alone, change the
number, move it to another pool, or take it out of the pool.

**Why this priority**: Editing must not lose or silently change the pool's record of a number.
Showing the tracked state in the pool tab is the only place the form can show both the pool and
the number together.

**Independent Test**: Open the edit form of a node whose number a pool tracks; confirm the pool
tab is active with the pool and number shown. Save without changes and confirm nothing is sent.

**Acceptance Scenarios**:

1. **Given** a node whose number pool P tracks, **When** the edit form opens, **Then** the
   **From pool** tab is active, P is picked, the number input holds the current number, and the
   label shows that the value comes from P.
2. **Given** that form, **When** the user saves without changing anything, **Then** nothing is
   sent for the field.
3. **Given** that form, **When** the user changes the number and saves, **Then** the node holds
   the new number and P still tracks it.
4. **Given** that form, **When** the user picks pool B and keeps a number, **Then** B tracks that
   number and P no longer does.
5. **Given** that form, **When** the user picks pool B and empties the number, **Then** the node
   gets the next free number from B and P no longer tracks the node.
6. **Given** that form, **When** the user switches to the Value tab, types a number and saves,
   **Then** the node holds that number and no pool tracks it any more.
7. **Given** that form, **When** the user switches to the Value tab and back without typing
   anything, **Then** the field holds the value it opened with and nothing is sent on save.
8. **Given** a node whose number no pool tracks, **When** the edit form opens, **Then** the Value
   tab is active with the current number.
9. **Given** a node whose number no pool tracks, **When** the user picks a pool and keeps the
   current number, **Then** the pool starts tracking that number (adopt an existing number).

---

### Edge Cases

- **Pool tab, pool picked, number emptied, same pool already tracks the node**: the backend
  returns the number it already reserved for the node, so the number does not change. The form
  sends the request; the result is the existing number.
- **Pool tab, no pool picked, number typed**: the form cannot be saved with a number and no pool
  in the pool tab; the field asks for a pool. A number alone belongs in the Value tab.
- **Required attribute, pool tab, pool picked, number empty**: valid. The pool provides the
  number.
- **Template-backed field** (the `<attribute>_from_resource_pool` relationship on object
  templates): unchanged. A template stores only a reference to the pool, so the number input is
  not offered in the pool tab, the same way the IP overrides are not offered there.
- **Attribute whose kind is `NumberPool`**: unchanged. It stays read-only and accepts no number.
- **Field the user may not edit**: neither tab can be used, as today.
- **No pool targets this kind and attribute**: no tabs, as today.
- **The backend refuses a pool without a number over a held number** (contract rows 10 and 12):
  the form never sends that combination, because it always sends the number key with the pool.
  If the backend still returns the refusal, the form shows the backend message on the field.
- **Bulk update form and filter forms**: out of scope; they keep their current behaviour.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A Number attribute that at least one number pool targets (for the node's kind or a
  generic it inherits from, and for this attribute) MUST present the two tabs **Value** and
  **From pool**, using the same component, layout and tab behaviour as the IP prefix and IP
  address fields.
- **FR-002**: A Number attribute that no number pool targets MUST render as it does today, with
  no tabs.
- **FR-003**: The pool tab MUST show the pool picker on its own line and a number input below it.
  The number input MUST carry a visible label and an explanation stating that leaving it empty
  allocates the next free number from the pool.
- **FR-004**: The pool picker MUST list only the number pools that target this node's kind (or a
  generic it inherits from) and this attribute.
- **FR-005**: Saving from the pool tab with a number MUST send the number and the pool together,
  so the backend keeps the number and the pool records it as used.
- **FR-006**: Saving from the pool tab without a number MUST send the pool with an explicit empty
  number, so the backend allocates the next free number.
- **FR-007**: The form MUST NOT send a pool without the number key. This keeps the form out of the
  backend's refusal case.
- **FR-008**: Saving from the Value tab on a create form MUST send the number only.
- **FR-009**: Saving a number typed in the Value tab on an edit form, when a pool tracks the
  attribute, MUST also send an explicit empty pool, so the pool stops tracking the number. This
  applies even when the typed number equals the current one, because the user changed where the
  number comes from. When no pool tracks the attribute, it MUST send the number only.
- **FR-010**: The edit form MUST open on the pool tab when a number pool tracks the attribute,
  with that pool picked and the current number in the number input. Otherwise it MUST open on the
  Value tab.
- **FR-011**: The field label MUST show the pool as the value's source when a pool tracks the
  attribute or when a pool is staged, as the IP fields do.
- **FR-012**: Switching tabs MUST discard what the abandoned tab staged and return the field to the
  value it held when the form opened. Visiting a tab without choosing anything MUST NOT cause
  anything to be sent.
- **FR-013**: A field whose value has not changed since the form opened MUST NOT be sent.
- **FR-014**: In the pool tab, a number without a pool MUST block saving with a message on the
  field asking for a pool.
- **FR-014a**: Picking a pool MUST pre-fill the number input with the number the node holds on an
  edit form, so the held number is kept unless the user empties the input. On a create form, and
  when the current value comes from the schema default, a profile or a template, the input MUST
  start empty.
- **FR-015**: An error the backend returns for the field (uniqueness, refusal, pool not attached
  to this kind and attribute) MUST be shown to the user.
- **FR-016**: A field the user may not edit MUST NOT allow either tab to be used.
- **FR-017**: The template-backed pool path and the `NumberPool` attribute kind MUST keep their
  current behaviour.
- **FR-018**: Automated tests MUST cover each row of the submission table in the plan (create and
  edit, each tab, with and without a number, same and different pool), and the edit-mode tab
  selection.

### Key Entities

- **Number pool**: A source of numbers bound to one node kind and one Number attribute, with one
  or more ranges. The thing the user picks in the pool tab.
- **Pool record on an attribute**: The pool's record that it tracks the number held by one node's
  attribute. Created by an allocation or an attach, ended by a detach or a move to another pool.
- **Field value source**: Where the field's current value came from — the user, the schema, a
  profile, a template or a pool. Decides which tab the edit form opens on.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can save a node with a chosen number recorded in a pool in one form
  submission, without leaving the form.
- **SC-002**: Opening the edit form of a node whose number a pool tracks shows the pool and the
  number on first render, without any interaction.
- **SC-003**: Opening an edit form, visiting both tabs and saving leaves the node and the pool's
  records unchanged.
- **SC-004**: Every Number attribute that a pool targets presents the same two tabs as the IP
  fields; a reviewer comparing them finds no difference in layout or tab behaviour.
- **SC-005**: Every row of the submission table is asserted by an automated test.
- **SC-006**: The change introduces no regression in the existing frontend gates.

## Assumptions

- The backend behaviour of
  [`from-pool-intent.md`](../ifc-3184-pool-number-attach/contracts/from-pool-intent.md) is
  available on `feature-number-pools-1.12`, which this branch is based on (IFC-3226 and IFC-3227
  are Done).
- **Deliberate difference from IFC-2764 FR-017.** IFC-2764 opens every pool-backed field on the
  value tab, because an IP pool tab has no control that can show an existing allocation. A number
  pool tab can show both the pool and the number, so opening there for a tracked number shows the
  full state. This also gives the Value tab one meaning in edit mode: a number that no pool
  tracks.
- Range checks on a provided number are not done in the form, because the backend refuses no
  provided number (contract, FR-029 deleted).
- Showing allocation provenance (pool-assigned or user-set) on the pool details page is tracked in
  IFC-3328 and is out of scope.
- Detaching without changing the number (keep 42, stop tracking it) is reached by switching to the
  Value tab and saving the same number; a dedicated "remove from pool" action is out of scope.
