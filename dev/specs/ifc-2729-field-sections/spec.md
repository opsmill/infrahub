# Feature Specification: Schema-defined field sections

**Feature Branch**: `ple-field-sections-ifc-2729`

**Created**: 2026-11-04

**Input**: Epic [IFC-2729](https://opsmill.atlassian.net/browse/IFC-2729) (tasks
[IFC-3566](https://opsmill.atlassian.net/browse/IFC-3566) schema,
[IFC-3567](https://opsmill.atlassian.net/browse/IFC-3567) schema API,
[IFC-3568](https://opsmill.atlassian.net/browse/IFC-3568) detail view,
[IFC-3569](https://opsmill.atlassian.net/browse/IFC-3569) forms,
[IFC-3570](https://opsmill.atlassian.net/browse/IFC-3570) documentation), product idea
[INFP-596](https://opsmill.atlassian.net/browse/INFP-596),
[field sections mockup](https://claude.ai/artifact/NZNYnYuRGviP3X6TgYoSUS),
[UI check-in of 2026-10-13](https://docs.google.com/document/d/1RIxR2abmaqtkr7vSy7Oggs9-xmFiifxOBA6sxrt89C0/edit).

A schema designer declares named containers on a node or generic and assigns attributes and
relationships to them. Operators then view one card per section on the node detail page and one
panel per section in the create and edit forms. The schema API and the SDK return the containers so
other clients can group fields the same way. The schema and the API use `containers` and
`container`; the UI says "section".

## Decisions

- The schema-of-the-schema gains `containers` on nodes and generics and `container` on attributes
  and relationships. No graph migration and no GraphQL change.
- The form uses bordered panels with the same header as the detail card (mockup option B). The
  container description is muted text under the section title.
- Fields without a container form the Details section, which sits at order weight 0. A container
  with a negative `order_weight` is shown above Details; a container with a weight of 0 or more, or
  without a weight, is shown below it. The product owner added this rule on 2026-11-10; before
  it, Details was always the first section. Schemas whose containers have no negative weight keep
  their layout.
- Details is the only built-in section of a node or generic: `details` cannot be declared or
  referenced. The original
  decision also made an Advanced section implicit (never stored, never returned in `containers`,
  always accepted as a `container` value, shown last and collapsed). The product owner reversed it
  on 2026-11-10: `advanced` is an ordinary container name, and a field can reference it only when
  the node declares or inherits a container of that name.
- Container names that start with `builtin_` are reserved for the containers Infrahub generates:
  a node or generic cannot declare one. The product owner added this rule on 2026-11-10.
- `collapsed` applies to the detail view only; form panels are always expanded.
- The Extra toggle is per section.
- Containers inherited from a generic merge by name; the node's definition wins, then the first
  generic in `inherit_from`.
- Generated profiles and object templates copy the node's containers. Generated profiles also get
  a Profile container (`builtin_profile`, label Profile, order weight -100, not collapsed) that
  holds `profile_name` and `profile_priority`, so a profile shows its name and priority above
  Details. The product owner added this on 2026-11-10. Generated object templates also get a
  Template container (`builtin_template`, label Template, order weight -100, not collapsed) that
  holds `template_name`, so a template shows its name above Details. This was added on 2026-11-12.
- The demo schema (`models/base/dcim.yml`) carries LACP, Layer 2 and Layer 3 containers on the
  `InfraLagInterface` generic, and the end-to-end test uses it.

## User scenarios

### User Story 1 - Declare sections in the schema (P1)

A schema designer models a LAG interface with about sixteen attributes and relationships. They add
LACP, Layer 2 and Layer 3 containers to the node and set `container` on the matching fields. Name,
description, status, role, device and tags keep no container. The load succeeds. When they mistype
a container name, the load fails with a message that names the node, the field and the container.

1. **Given** a node with three containers and fields that reference them, **When** it is loaded,
   **Then** reading it back returns the containers with name, label, description, order weight and
   collapsed flag, and each field with its container name.
2. **Given** a field whose `container` the node does not declare, **When** it is loaded, **Then**
   the load is rejected with
   `<Kind>.attributes.<name>.container: container '<x>' is not declared on <Kind>` (or
   `relationships.<name>` for a relationship).
3. **Given** two containers with the same name on one node, **When** it is loaded, **Then** the
   load is rejected with `<Kind>.containers: container names must be unique, duplicate '<x>'`.
4. **Given** a container named `details`, **When** it is loaded, **Then** the load is rejected
   with `<Kind>.containers: 'details' is a built-in container and cannot be declared`. A container
   whose name starts with `builtin_` is rejected with
   `<Kind>.containers: '<x>' starts with the reserved prefix 'builtin_' and cannot be declared`.
5. **Given** a field with `container: advanced` and no declared container of that name, **When**
   it is loaded, **Then** the load is rejected with the unknown container error of scenario 2. With
   a declared `advanced` container, the load succeeds.
6. **Given** a loaded schema, **When** it is loaded again with a container left out of the list,
   **Then** the container stays; removing it needs `state: absent` on the item.
7. **Given** a schema with containers, **When** a container label changes or a field moves to
   another container, **Then** the load needs no migration and no constraint check.

### User Story 2 - Inherit sections from a generic (P1)

The schema designer declares the containers once on the LAG interface generic. The L2 and L3 LAG
interface nodes show the same sections.

1. **Given** a generic with containers and a node that declares none, **When** the schema is
   loaded, **Then** the node returns the generic's containers and its inherited fields keep their
   container.
2. **Given** a node that declares a container with the same name as one of the generic's, **When**
   the schema is loaded, **Then** the node returns its own definition for that name and the
   generic's for the other names.
3. **Given** a node that redeclares an inherited attribute with another `container`, **When** the
   schema is loaded, **Then** the node's attribute uses the node's container, under the existing
   override rules.
4. **Given** two generics in `inherit_from` that declare the same container name, **When** the
   schema is loaded, **Then** the first generic's definition is used.
5. **Given** an inherited field whose container exists only on the generic, **When** the container
   is removed from the generic, **Then** the next load is rejected with the unknown container error.
6. **Given** a schema with inherited containers, **When** it is processed twice, **Then** the
   containers are the same, with no duplicates.

### User Story 3 - View a node by section (P1)

An operator opens the detail page of LAG interface `bond0`. They view a Details card, then LACP,
Layer 2 and Layer 3 cards. They collapse Layer 2. The MAC address
is an extra field of Layer 2, so it appears only after they switch on Extra in that card.

1. **Given** a node with containers, **When** the detail page opens, **Then** it shows one card
   per container with a negative order weight, then a Details card with the fields without a
   container, then one card per other container, each group in order weight order and each card
   listing its fields in order weight order.
2. **Given** a container with `collapsed: true`, **When** the page opens, **Then** that card shows
   only its header, and selecting the header expands it.
3. **Given** a section with fields marked `display: extra`, **When** the page opens, **Then** those
   fields are hidden behind that card's own Extra control; a card without extra fields has none.
4. **Given** a node without sectioned fields, **When** the detail page opens, **Then** it shows the
   single Details card as before.
5. **Given** a container for which the node has no visible field, **When** the page opens,
   **Then** no card is shown for it.
6. **Given** a profile or object template of a node with containers, **When** its detail page
   opens, **Then** it shows the same sections as the node. A profile also shows a Profile card,
   with the profile name and priority, above the Details card, and an object template shows a
   Template card, with the template name, above the Details card.

### User Story 4 - Edit a node by section (P2)

The operator edits `bond0` to change the LACP rate. The form shows a Details panel, then one panel
per container with the same titles and order as the detail page, all expanded. The saved value is
the same as without panels.

1. **Given** the create or edit form of a node with containers, **When** it opens, **Then** the
   fields are grouped into bordered panels, one per container in order weight order, headed with
   the container label, and the panels of containers with a negative order weight come before the
   Details panel. The form of a profile shows the Profile panel first, and the form of an object
   template shows the Template panel first.
2. **Given** a container whose fields are all read-only or left out of the form, **When** the form
   opens, **Then** no panel is shown for it.
3. **Given** a sectioned form, **When** the operator saves, **Then** the request is identical to
   the one sent without sections.
4. **Given** a node without containers, **When** the form opens, **Then** it is the flat list.
5. **Given** a container with `collapsed: true`, **When** the form opens, **Then** its panel is
   expanded.
6. **Given** a validation error on a field, **When** it is reported, **Then** it is shown on that
   field inside its panel.

### User Story 5 - Reuse the sections outside the web interface (P2)

An automation engineer reads the node schema through the Python SDK and groups the fields of a
portal form with the same containers.

1. **Given** a node with containers, **When** a client reads the schema API, **Then** the node
   carries `containers` and each field its `container`, `null` when unset.
2. **Given** a node without containers, **When** a client reads the schema API, **Then**
   `containers` is an empty list and each `container` is `null`.
3. **Given** a schema file with containers, **When** the SDK validates it offline, **Then** it is
   accepted, and `infrahubctl schema format` writes the new keys in a fixed position.

### User Story 6 - Read how sections work (P3)

A schema designer reads the schema reference and a schema guide and finds the container
properties, the Details section, the order rules, the inheritance rules and the
errors.

1. **Given** the schema reference, **When** the designer opens the node, generic, attribute and
   relationship pages, **Then** `containers` and `container` are listed with a description.
2. **Given** the schema guides, **When** the designer looks for sections, **Then** one guide
   explains them with an example schema.

## Edge cases

- A container name and an attribute name are separate namespaces; both may be `mtu`.
- A container without `order_weight` comes after the weighted ones, in declaration order. Infrahub
  does not fill container order weights.
- A container with `order_weight: 0` is shown below Details, which also sits at 0. Only a negative
  weight places a container above Details.
- On a node, inherited containers come first, in the order the generics list them (first generic
  in `inherit_from` first), then the node's own containers. A node container with the same name
  as an inherited one takes the inherited one's position.
- A field marked `display: extra` stays behind its section's Extra control on the detail page and
  is shown in the form as before.
- A relationship shown in its own tab (for example a `Component` relationship of cardinality many)
  stays in its tab; its `container` has no effect on the detail page.
- A node that declares a container with no field loads without error and shows no card for it.
- Collapsing a card is not remembered across page loads or users.

## Requirements

### Schema contract

- **FR-001**: A node or generic schema MUST accept an optional `containers` list. Each item has a
  required `name` and `label`, an optional `description` and `order_weight`, a `collapsed` flag
  (default false, detail view only) and a `state` (default `present`, `absent` removes the item on
  reload). The API also returns a read-only `inherited` flag; a load that sends it gets a
  read-only warning and the value is not used.
- **FR-002**: An attribute or relationship schema MUST accept an optional `container` text value.
  Unset, the field belongs to Details. A reload that leaves `container` out keeps the stored
  value; `container: ""` moves the field back to Details.
- **FR-003**: A container `name` MUST follow the attribute name format and length rules, MUST be
  unique among the containers a node declares, MUST NOT be `details` and MUST NOT start with
  `builtin_`. A field MUST NOT reference `details`, only the fields of a generated profile can
  reference `builtin_profile`, and only the fields of a generated template can reference
  `builtin_template`.
- **FR-004**: Schema loading MUST reject a field whose `container` is not a container of the node
  after inheritance. For a field declared on a generic, the message names the generic.
- **FR-005**: Changing containers or container assignments MUST NOT require a migration or a
  constraint check.
- **FR-006**: Containers and assignments MUST be stored with the schema of each branch, returned
  unchanged after a reload, and carried to the default branch by a branch merge.
- **FR-007**: A reload MUST merge `containers` by name, keep the declaration order of the schema
  file, keep containers it leaves out, and remove items with `state: absent`. A load or merge that
  only reorders containers is a schema change, and two branches that reorder the same kind's
  containers differently report a conflict on `containers`.

### Inheritance

- **FR-008**: A node MUST receive the containers of its generics, merged by name. A node container
  replaces the generic's container of the same name entirely. Between generics, the first in
  `inherit_from` wins.
- **FR-009**: An inherited field MUST keep the generic's `container`. A node that redeclares the
  field MAY set another container.
- **FR-010**: Processing a schema twice MUST yield the same containers.
- **FR-011**: Generated profiles and object templates MUST carry the node's containers. Generated
  profiles MUST also carry the `builtin_profile` container (label Profile, order weight -100) and
  place `profile_name` and `profile_priority` in it. Generated object templates, of a node or of
  a generic, MUST also carry the `builtin_template` container (label Template, order weight -100)
  and place `template_name` in it.

### Schema API and SDK

- **FR-012**: The schema API MUST return `containers` on nodes, generics, profiles and templates
  (empty list when none) and `container` on attributes and relationships (`null` when unset),
  after inheritance, with `inherited: true` on each container a node takes from a generic.
  `details` MUST NOT be listed; a profile lists `builtin_profile` and a template lists
  `builtin_template`. Infrahub stores only the
  containers a node declares and rebuilds the inherited ones on load.
- **FR-013**: The schema load endpoint and the SDK offline validation MUST accept both properties.
  The SDK formatter MUST place them in a fixed position, and the SDK export MUST leave out
  inherited containers.
- **FR-014**: The GraphQL schema and queries MUST NOT change.

### Detail view

- **FR-015**: The detail page MUST show the cards of the containers with a negative
  `order_weight`, then the Details card, then the cards of the other containers, each group by
  `order_weight`, and MUST omit a card without a visible field.
- **FR-016**: Each section card MUST use the rows of the Details card, titled with the container
  label, with its fields ordered by `order_weight`.
- **FR-017**: Each container card MUST be collapsible from its header and start collapsed when its
  container says so. Details is not collapsible.
- **FR-018**: Each section card MUST have its own Extra control, shown only when the section has a
  `display: extra` field.
- **FR-019**: A node without sectioned fields MUST render the single Details card as before. The
  object detail page and the IPAM detail page render sections; the other pages that reuse the
  Details card (repository, GraphQL query, user profile) keep the single card.
- **FR-020**: The section header MUST show the container label and, when set, the description as
  muted text under it, in the detail card and in the form panel.

### Forms

- **FR-021**: The create and edit forms, including the file object form, MUST group fields into
  bordered panels, one per container by `order_weight`, with the same header as the detail card.
- **FR-022**: In a form with at least one section, fields without a container MUST be shown in a
  Details panel placed after the panels of containers with a negative `order_weight` and before
  the others.
- **FR-023**: Form panels MUST always be expanded, including those of containers with
  `collapsed: true`.
- **FR-024**: A panel with no field left after the form's own filtering MUST be omitted.
- **FR-025**: Grouping MUST NOT change the data the form sends; a form without sections MUST remain
  the flat list.

### Schema viewer and documentation

- **FR-026**: The schema viewer MUST list a node's containers and show each field's container.
- **FR-027**: The generated schema reference MUST describe both properties, a schema guide MUST
  explain sections with an example, and changelog fragments MUST describe the change.

## Success criteria

- **SC-001**: On the demo, an operator views the L2 LAG interface as Details, LACP and Layer 2
  cards and the L3 LAG interface as Details, LACP and Layer 3 cards.
- **SC-002**: Every schema that loads today still loads, and every detail page and form of a node
  without containers renders as before.
- **SC-003**: A schema API or SDK client reads the same containers and assignments as the web
  interface renders, with no extra call.

## Out of scope

- A grid layout for sections.
- Configuring sections from the UI.
- Grouping columns in the list view.
- Remembering collapsed sections per user.
- Placing an inherited field in a section without redeclaring it on the node.
