# Feature Specification: Display List, JSON, Any and Password attributes in table views

**Feature Branch**: `ple-complex-attribute-cells-ifc-2498`
**Created**: 2026-11-06
**Status**: Implemented
**Input**: [INFP-567](https://opsmill.atlassian.net/browse/INFP-567), implemented by [IFC-2498](https://opsmill.atlassian.net/browse/IFC-2498)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Show a List, JSON, Any or Password attribute as a column (Priority: P1)

A user views a table of nodes whose schema has an attribute of kind List, JSON, Any, Password or
HashedPassword. Today these attributes are not offered in the column picker, so the user has to
open each node one by one to read the value. With this feature, the user turns the attribute on in
the column picker and reads its value for every node in the table.

**Why this priority**: Without it, the other stories have no column to render in.

**Independent Test**: In a table of nodes whose schema has a List attribute, open the column
picker, turn the attribute on, and check that the column appears with each node's value.

**Acceptance Scenarios**:

1. **Given** a schema with a List, JSON, Any or Password attribute, **When** the user opens the
   column picker, **Then** the attribute is offered and is off by default.
2. **Given** the user turns such an attribute on, **When** the table loads, **Then** the column
   shows the value of each node, and the column stays on when the link is shared or reloaded.
3. **Given** a table with no column picked, **When** it loads, **Then** it shows the same columns
   as before this feature.

### User Story 2 - Read list and JSON values without opening the node (Priority: P1)

The user scans a column of List, JSON or Any values and understands each value from the cell, and
opens the full JSON value when the preview is not enough.

**Why this priority**: The values are only useful if they can be read in the table.

**Independent Test**: Load a table where one node holds a long list, a nested JSON object and Any
values of each shape, and check each cell.

**Acceptance Scenarios**:

1. **Given** a List value, **When** the cell renders, **Then** it shows the list elements on one
   line, clipped at the cell edge, and the total element count.
2. **Given** a JSON value, **When** the user activates the cell's trigger with the mouse or the
   keyboard, **Then** a dialog shows the full value, formatted and indented.
3. **Given** an Any value, **When** the cell renders, **Then** an array renders like a List, an
   object renders like a JSON value, and any other value renders as text.
4. **Given** a List value with more elements than the table cell or the detail view shows,
   **When** the user activates the "more" indicator with the mouse or the keyboard, **Then** every
   element is shown, without opening the edit form.

### User Story 3 - Know that a password is set without reading it (Priority: P2)

The user checks which nodes have a password or a hashed password set.

**Why this priority**: It completes the set of attribute kinds, with less value than lists and JSON.

**Independent Test**: Load a table with one node that has a password and one that has none.

**Acceptance Scenarios**:

1. **Given** a Password or HashedPassword value, **When** the cell renders, **Then** it shows masked
   characters and never the value.
2. **Given** no value, **When** the cell renders, **Then** it shows `-`.

### Edge Cases

- An empty list, an empty JSON object or array, and a null value each render `-`.
- A list with one very long element, or many elements, stays on one line and does not widen the row.
- A JSON value that is a string, a number or `false` renders its preview like any other JSON value.
- A JSON value with thousands of lines opens in the dialog, which scrolls.
- A list element that is a number, a boolean or null renders as monospace text with its type. An
  object or an array opens its own JSON. An object with a string `id` and the `__typename` of a
  kind in the schema renders as a link to that object.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The column picker MUST offer attributes of kind List, JSON, Any and Password, turned
  off by default. It MUST NOT offer HashedPassword attributes.
- **FR-002**: The default columns of every table MUST stay the same as before this feature.
- **FR-003**: When the user turns such a column on, the table MUST fetch the attribute's value and
  render it.
- **FR-004**: A List cell MUST show the list elements on one line and the total element count. The
  cell clips elements at its edge, so the count of hidden elements depends on the column width.
- **FR-004a**: In the table and in the detail view, the user MUST be able to view every element of
  a List value from the place where it is shown, without opening the edit form.
- **FR-005**: A JSON cell MUST show a trigger that opens a dialog with the full, formatted value,
  reachable with the keyboard.
- **FR-006**: An Any cell MUST render an array as a List, an object as a JSON value, and any other
  value as text.
- **FR-007**: A Password or HashedPassword cell MUST show masked characters when a value exists and
  MUST NOT show the value.
- **FR-008**: An empty or null value MUST render `-`, as for the other kinds.
- **FR-009**: Every cell MUST stay on one line, so the row height does not change.
- **FR-010**: Filters, relationship tabs and the other views that use the default column list MUST
  keep their current behavior. A column of these kinds MUST NOT offer a filter or a sort.
- **FR-011**: The user documentation that describes how each attribute kind displays in the web
  interface MUST describe the new behavior.

### Key Entities

- **Attribute kind**: the kind set in the schema (List, JSON, Any, Password, HashedPassword), which
  decides how a cell renders.
- **Column picker choice**: the set of columns the user turned on, kept in the page link.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every attribute of kind List, JSON, Any and Password can be shown as a column, and a
  cell with a value is never empty.
- **SC-002**: A user reads a list or JSON value for 10 nodes from one table, without opening any
  node.
- **SC-003**: No table shows a new column unless the user turns it on.
- **SC-004**: No password value appears in a table cell.
- **SC-005**: A user views all elements of a 300-element list from the table or the detail view
  without opening the edit form.

## Assumptions

- The design step chose badges for List values, the start of the value as the JSON trigger, and one
  dialog for List and JSON values. In that dialog, List elements show as a table with their
  position, value, type and a copy button.
- Sorting and filtering on these kinds stay out of scope; [INFP-567](https://opsmill.atlassian.net/browse/INFP-567)
  lists them as an open question.
- The detail view is out of scope, except for List values: they show up to 10 elements as badges
  and "View all" (FR-004a), decided in the design step. The TextArea, ID, NodeKind and Checkbox
  kinds are out of scope.
- HashedPassword was removed from the column picker on 2026-11-06 (Paul Leménager): its column would
  fetch every row's hash only to show masked characters, and the detail view does not show it either.
- No change to the backend or to the GraphQL schema: the values are already available.
- The people who use these tables work on a desktop screen.
