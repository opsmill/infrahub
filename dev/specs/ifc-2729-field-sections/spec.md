# Feature Specification: Schema-defined field sections

**Feature Branch**: `ple-field-sections-ifc-2729`

**Created**: 2026-11-04

**Status**: Draft

**Input**: [IFC-2729](https://opsmill.atlassian.net/browse/IFC-2729) (delivery epic, release 1.13;
tasks [IFC-3566](https://opsmill.atlassian.net/browse/IFC-3566) schema,
[IFC-3567](https://opsmill.atlassian.net/browse/IFC-3567) schema API,
[IFC-3568](https://opsmill.atlassian.net/browse/IFC-3568) detail view,
[IFC-3569](https://opsmill.atlassian.net/browse/IFC-3569) forms,
[IFC-3570](https://opsmill.atlassian.net/browse/IFC-3570) documentation), product idea
[INFP-596](https://opsmill.atlassian.net/browse/INFP-596), prototype
[field sections mockup](https://claude.ai/artifact/NZNYnYuRGviP3X6TgYoSUS), decisions of the
[UI check-in of 2026-10-13](https://docs.google.com/document/d/1RIxR2abmaqtkr7vSy7Oggs9-xmFiifxOBA6sxrt89C0/edit).
A schema designer declares named containers on a node or generic and assigns attributes and
relationships to them. Operators then view one card per section in the node detail view and one
panel per section in the create and edit forms. The schema API returns the containers so the SDK and
other consumers can group fields the same way. Vocabulary: `containers` and `container` in the schema
and the API, "section" in the UI.

Decisions taken before this spec (not reopened here): the form uses bordered panels with the same
header as the detail-view card (mockup option B); the container description is shown as muted
text under the section title; ungrouped fields get a Details panel in the form; the `collapsed`
flag ships for the detail view; this run covers the schema, the schema API, the
detail view, the forms and the documentation; containers inherited from a generic merge by name and
the node's definition wins; the Extra toggle is per section.

## Clarifications

### Session 2026-11-04

- Q: Approve adding `containers` and `container` to the internal schema definitions (no graph migration, no GraphQL change)? → A: Approved.
- Q: Add the LACP, Layer 2 and Layer 3 containers to the `InfraLagInterface` generic of the demo schema for the end-to-end test? → A: Yes, the demo schema carries the sections.
- Q: Built-in Advanced section implicit or returned by the schema API? → A: Implicit: never stored, never returned, always accepted as a `container` value.
- Q: Copy a node's containers onto its generated profile and object template? → A: Copy them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Declare sections in the schema (Priority: P1)

A schema designer at a service provider models a LAG interface with about sixteen attributes and
relationships. They add three containers to the node, LACP, Layer 2 and Layer 3, and set
`container` on the bundle number, LACP rate, LACP mode and MLAG peer link to `lacp`, on the L2 mode,
802.1Q ID, MAC address and untagged VLAN to `layer2`, and on the MTU and IP addresses to `layer3`.
Name, description, status, role, device and tags keep no container. They load the schema, and
Infrahub accepts it. When they mistype a container name on one attribute, the load fails with a
message that names the node, the attribute and the unknown container.

**Why this priority**: Every other story depends on the schema carrying the sections. Validation at
load time is what lets the UI trust the data.

**Independent Test**: Load a schema with containers and container references through the schema
load endpoint, read it back through the schema API, and compare. Load a schema with an unknown
container reference and check the error message.

**Acceptance Scenarios**:

1. **Given** a node schema with three declared containers and attributes and relationships that
   reference them, **When** the schema designer loads it, **Then** the load succeeds and reading the
   node back returns the three containers with their name, label, description, order weight and
   collapsed flag, and each field with its container name.
2. **Given** an attribute whose `container` names a container the node does not declare, **When**
   the schema is loaded, **Then** the load is rejected and the error reads
   `<Kind>.attributes.<name>.container: container '<x>' is not declared on <Kind>`. The same holds
   for a relationship.
3. **Given** two containers with the same name on one node, **When** the schema is loaded, **Then**
   the load is rejected with `<Kind>.containers: container names must be unique, duplicate '<x>'`.
4. **Given** a container named `advanced` in the node's list, **When** the schema is loaded,
   **Then** the load is rejected with
   `<Kind>.containers: 'advanced' is a built-in container and cannot be declared`.
5. **Given** an attribute with `container: advanced` and no declared container of that name,
   **When** the schema is loaded, **Then** the load succeeds.
6. **Given** a loaded schema, **When** the schema designer loads it again with a container removed
   from the list, **Then** the container stays, because list items are merged on reload; removing it
   needs `state: absent` on the item, as for attributes and relationships.
7. **Given** a schema with containers, **When** the schema designer changes a container label or
   moves a field to another container, **Then** the change is accepted without a migration and
   without a constraint check, because sections only affect rendering.

---

### User Story 2 - Inherit sections from a generic (Priority: P1)

The LAG interface is a generic with two implementing nodes, L2 and L3 LAG interfaces. The schema
designer declares the containers once on the generic. Both nodes show the same sections. The L3 node
redeclares the `layer3` container with a different label, and that label wins on the L3 node only.

**Why this priority**: Customer schemas put shared fields on generics. Without inheritance the
designer would repeat every container on every node, and the product decision requires containers to
behave like the rest of the schema.

**Independent Test**: Load a generic with containers and a node that inherits from it, read the node
back, and compare its containers and field assignments with the generic's.

**Acceptance Scenarios**:

1. **Given** a generic with containers and a node that inherits from it and declares none,
   **When** the schema is loaded, **Then** the node returns the generic's containers and its
   inherited fields keep their container.
2. **Given** a node that declares a container with the same name as one of the generic's,
   **When** the schema is loaded, **Then** the node returns its own definition for that name and the
   generic's definitions for the other names.
3. **Given** a node that redeclares an inherited attribute with a different `container`, **When**
   the schema is loaded, **Then** the node's attribute uses the node's container, subject to the
   existing override rules of the attribute.
4. **Given** two generics in `inherit_from` that declare a container with the same name, **When**
   the schema is loaded, **Then** the first generic's definition is used, the same precedence as the
   other inherited node properties.
5. **Given** an inherited attribute whose container exists only on the generic, **When** the
   container is removed from the generic, **Then** the next load is rejected with the unknown
   container error for that node.
6. **Given** a loaded schema with inherited containers, **When** the schema is processed a second
   time without changes, **Then** the containers are the same, with no duplicates.

---

### User Story 3 - View a node by section (Priority: P1)

An operator in a run team opens the detail page of LAG interface `bond0`. They view a Details card
with name, device, description, status, role and tags, then the LACP, Layer 2 and Layer 3 cards, then
a collapsed Advanced card. They collapse Layer 2, which they do not need today. The MAC address is an
extra field inside Layer 2, so it appears only after they switch on Extra in that card.

**Why this priority**: This is the request from Eurofiber and Schneider Electric: reading an object
by section instead of as one list of sixteen rows.

**Independent Test**: Open a node whose schema declares containers and check the cards, their
order, their rows and the collapse and Extra controls. Open a node whose schema declares none and
check that the page is unchanged.

**Acceptance Scenarios**:

1. **Given** a node whose schema declares containers, **When** the operator opens its detail page,
   **Then** they view a Details card with the fields that have no container, then one card per
   container in order weight order, each titled with the container label and listing its fields in
   their order weight order, then an Advanced card last.
2. **Given** a container with `collapsed: true`, **When** the page opens, **Then** that card shows
   only its header, and selecting the header expands it.
3. **Given** a container with fields marked `display: extra`, **When** the page opens, **Then**
   those fields are hidden and the card shows its own Extra control; a card without extra fields
   shows no Extra control.
4. **Given** a node with no field assigned to a container and no field in `advanced`, **When** the
   operator opens its detail page, **Then** they view the single Details card as today.
5. **Given** a container declared on a generic for which this node has no field, **When** the
   operator opens the node, **Then** no empty card is shown.
6. **Given** a profile or an object template of a node with containers, **When** the operator opens
   it, **Then** its detail page shows the same sections as the node.

---

### User Story 4 - Edit a node by section (Priority: P2)

The same operator edits `bond0` to change the LACP rate. The edit form shows a Details panel with
the ungrouped fields, then a panel per container with the same titles and order as the detail page,
all expanded. They change the rate inside the LACP panel and save. The value is stored exactly as
when the form had no panels.

**Why this priority**: The customers' consumer users enter data through the form, so the sections
must carry into it. It ranks after the detail view because the form was the piece that blocked the
work in a previous cycle, and the product card lists it as the nice-to-have part.

**Independent Test**: Open the create and the edit form of a node with containers, check the panels,
change a value inside a panel, save, and verify the stored value. Submit the same form for a node
without containers and verify the payload is unchanged.

**Acceptance Scenarios**:

1. **Given** the create or edit form of a node with containers, **When** it opens, **Then** the
   fields are grouped into bordered panels, one per container in order weight order, each with the
   container label as its header, with fields ordered by their order weight inside the panel.
2. **Given** a container whose fields are all read-only or excluded from the form, **When** the form
   opens, **Then** no panel is shown for it.
3. **Given** the form of a node with containers, **When** the operator saves, **Then** the request
   sent is identical to the one sent without sections.
4. **Given** a node without containers, **When** the form opens, **Then** it is the flat list of
   today.
5. **Given** a container with `collapsed: true`, **When** the form opens, **Then** its panel is
   expanded, so a required field or a validation error is never hidden.
6. **Given** a form with sections, **When** a validation error is reported on a field, **Then** the
   error is shown on that field inside its panel, as today.

---

### User Story 5 - Reuse the sections outside the web interface (Priority: P2)

An automation engineer builds a simplified service-catalog form for a customer portal. They read the
node schema through the Python SDK and group the fields with the same containers the web interface
uses, without maintaining a second mapping.

**Why this priority**: Requirement 7 of the product card asks that the metadata be exposed for
downstream reuse. It costs nothing extra once the schema API returns the field.

**Independent Test**: Read a node through the schema API and the SDK and check that the containers
and each field's container are present and match the loaded schema.

**Acceptance Scenarios**:

1. **Given** a node with containers, **When** a client reads the schema API, **Then** the node
   carries its `containers` list and each attribute and relationship its `container` value, with
   `null` when unset.
2. **Given** a node without containers, **When** a client reads the schema API, **Then**
   `containers` is an empty list and each field's `container` is `null`.
3. **Given** an SDK client, **When** it loads a schema file with containers, **Then** the offline
   validation accepts it, and the formatter keeps the new keys in a fixed position.

---

### User Story 6 - Read how sections work (Priority: P3)

A schema designer new to the feature reads the schema reference and the schema guide and finds the
container properties, the built-in Advanced section, the default section for ungrouped fields, the
ordering rules, the inheritance rules and the error they get for an undeclared container.

**Why this priority**: Required for a user-visible schema change; it does not block the UI work.

**Independent Test**: Build the documentation site and check the reference pages and the guide
section render with the new properties.

**Acceptance Scenarios**:

1. **Given** the schema reference pages, **When** the designer opens the node, generic, attribute
   and relationship pages, **Then** `containers` and `container` are listed with their description.
2. **Given** the schema guides, **When** the designer looks for sections, **Then** one guide
   explains the built-in Advanced section, the default section, ordering, inheritance and the
   validation errors, with an example schema.

---

### Edge Cases

- A container name may equal an attribute name; the two are separate namespaces and both are
  allowed.
- A container name follows the same format and length rules as an attribute name.
- A container with no `order_weight` is ordered after the weighted ones, in declaration order.
  Infrahub does not fill container order weights, unlike attribute order weights.
- A field marked `display: extra` inside a container stays hidden behind that section's Extra
  control in the detail view, and is shown in the form as today.
- A field whose attribute is allocated from a resource pool follows its attribute's section.
- A relationship that is not shown in the detail view today (for example a relationship of kind
  that is only shown in a tab) stays where it is; sections do not change which fields are visible.
- The Advanced section is implicit: it is never stored, never returned in `containers` and always
  accepted as a `container` value.
- Profiles and object templates generated from a node copy the node's containers, so their fields'
  container references resolve and their views show the same sections.
- A node that declares a container but has no field in it, after inheritance, loads without error
  and shows no card for it.
- Collapsing a card is not remembered across page loads or users.

## Requirements *(mandatory)*

### Functional Requirements

Schema contract

- **FR-001**: A node or generic schema MUST accept an optional `containers` list. Each item has a
  required `name`, a required `label`, an optional `description`, an optional `order_weight` and
  an optional `collapsed` flag that defaults to false and applies to the detail view only.
- **FR-002**: An attribute or relationship schema MUST accept an optional `container` text value.
  When unset, the field belongs to the default Details section.
- **FR-003**: A container `name` MUST follow the attribute name format and length rules, MUST be
  unique within a node after inheritance, and MUST NOT be `advanced`.
- **FR-004**: Schema loading MUST reject a field whose `container` is neither a container declared
  on the node after inheritance nor `advanced`, with the messages of User Story 1.
- **FR-005**: Changing containers or container assignments MUST NOT require a migration or a
  constraint check.
- **FR-006**: Containers and container assignments MUST be stored with the schema and returned
  unchanged after a reload, including on a branch other than the default branch, and after a
  branch whose schema adds or changes containers is merged into the default branch, the default
  branch returns the merged containers.
- **FR-007**: Reloading a schema MUST merge the `containers` list by name, as other item lists are
  merged; removing an item requires `state: absent` on the item, as for attributes and
  relationships.

Inheritance

- **FR-008**: A node MUST receive the containers of each generic it inherits from, merged by name.
  A container the node declares replaces the generic's container of the same name entirely. When
  several generics declare the same name, the first generic in `inherit_from` wins.
- **FR-009**: An inherited attribute or relationship MUST keep the `container` set on the generic.
  A node that redeclares the field MAY set another container, under the existing override rules.
- **FR-010**: Processing a schema twice MUST yield the same containers.
- **FR-011**: Profiles and object templates generated from a node MUST carry the node's containers.

Schema API and SDK

- **FR-012**: The schema API MUST return `containers` on nodes, generics, profiles and templates
  (empty list when none) and `container` on attributes and relationships (`null` when unset),
  after inheritance is applied. `advanced` MUST NOT be listed.
- **FR-013**: The schema load endpoint and the SDK's offline validation MUST accept both
  properties, and the SDK schema formatter MUST place them in a fixed position.
- **FR-014**: The GraphQL data schema and queries MUST NOT change.

Detail view

- **FR-015**: The node detail page MUST show the Details card first with the fields that have no
  container, then one card per container ordered by `order_weight`, then the Advanced card last,
  and MUST omit a card that has no field.
- **FR-016**: Each section card MUST use the same header and rows as the Details card, titled with
  the container label, with its fields ordered by their `order_weight`.
- **FR-017**: Each section card MUST be collapsible from its header, start collapsed when its
  container says so, and the Advanced card MUST start collapsed.
- **FR-018**: Each section card MUST have its own Extra control, shown only when the section has a
  field marked `display: extra`, hiding those fields until switched on.
- **FR-019**: A node without containers and without `advanced` fields MUST render the single Details
  card as today. Pages that reuse the Details card for other objects MUST be unchanged.
- **FR-020**: The section header MUST show the container label and, when set, the container
  description as muted text under the label, in the detail card and in the form panel.

Forms

- **FR-021**: The create and edit forms MUST group the fields into bordered panels, one per
  container in `order_weight` order, headed with the container label, with the same header style
  as the detail card and with fields ordered by their `order_weight` inside the panel.
- **FR-022**: Ungrouped fields in a form that has at least one section MUST be shown in a Details
  panel placed before the other panels.
- **FR-023**: Form panels MUST always be expanded, including Advanced, so no required field or
  validation error is hidden.
- **FR-024**: A panel with no field left after the form's own filtering MUST be omitted.
- **FR-025**: Grouping MUST NOT change the data the form sends; a form for a node without
  containers MUST remain the flat list.

Schema viewer and documentation

- **FR-026**: The schema viewer MUST list a node's containers and show each field's container.
- **FR-027**: The generated schema reference MUST describe both properties, and a schema guide MUST
  explain sections with an example. A changelog fragment MUST describe the change.

### Key Entities

- **Container**: a named section declared on a node or generic schema; name, label, description,
  order weight, collapsed flag. Identified by its name within the node.
- **Node and generic schema**: owns a list of containers; a generic's containers are inherited by
  the nodes that implement it.
- **Attribute and relationship schema**: optionally references one container by name; `advanced`
  is a reserved reference.
- **Section**: the UI rendering of a container, plus the implicit Details and Advanced sections.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A schema designer can group the fields of a node into sections by editing only the
  schema file, with no change to the menu or to the data, and the result is visible in the detail
  page and the forms after one schema load.
- **SC-002**: On the demo's LAG interfaces, an operator views the L2 LAG interface as Details,
  LACP, Layer 2 and Advanced cards and the L3 LAG interface as Details, LACP, Layer 3 and Advanced
  cards, each listing exactly the fields the schema assigns to it, in the schema's order.
- **SC-003**: Every schema that loads today still loads unchanged, and every detail page and form
  of a node without containers renders exactly as before the change.
- **SC-004**: A schema with an undeclared container reference is rejected at load time with a message
  that names the node, the field and the container, so no page has to handle a missing section.
- **SC-005**: A client of the schema API or the SDK reads the same containers and assignments as the
  web interface renders, with no extra call.
- **SC-006**: The automated test suite covers the validation errors, inheritance, reload merge, the
  schema API, the detail-view cards, the form panels and one end-to-end flow, and all pass.

## Assumptions

- The Details section comes first on the page and in the form, as in the mockup and in today's
  single card.
- The collapsed state of a card is local to the page view and is not stored per user.
- The internal schema change (three new properties on the stored schema definitions, no graph
  migration) is approved.
- The demo schema (`models/base/dcim.yml`) gains the LACP, Layer 2 and Layer 3 containers on the LAG
  interface generic, and the L3 LAG interface node redeclares `mtu` in the Layer 3 container; the
  end-to-end test uses that data.
- The SDK formatter puts `containers` after `uniqueness_constraints` on nodes and `container` just
  before `order_weight` on attributes and relationships.
- Nothing changes for generics in the schema viewer beyond listing their containers.
- Out of scope: a grid layout for sections, configuring sections from the UI, grouping columns in the
  list view, and remembering collapsed sections per user.
