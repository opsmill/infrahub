# Feature Specification: Export the running schema

**Feature Branch**: `schema-export-ifc-2964`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "IFC-2964 Export the running schema. Input: idea brief for IFC-2964. Design document (approved, source of truth for D1-D13): <https://app.notion.com/p/401228b83025812589c6e6664594db35>"

**Sources**:

- [Engineering design document, INFP-723 · Export the running schema](https://app.notion.com/p/401228b83025812589c6e6664594db35): approved, source of truth for decisions D1 to D13, updated 2026-11-20. Section 5 records the amendments from planning on 2026-11-26 (A1 to A5); A1 and A2 are not agreed yet.
- [INFP-723](https://opsmill.atlassian.net/browse/INFP-723): product card.
- [IFC-2964](https://opsmill.atlassian.net/browse/IFC-2964): engineering story.
- Idea brief for IFC-2964, written before this specification. It restates the design document as user journeys and draft requirements.

## Summary

A schema owner who runs more than one Infrahub instance cannot copy the schema from one instance to another today. `infrahubctl schema export` writes values Infrahub generated and elements the schema owner did not define, so the file does not load without editing. The export rules are written by hand in the SDK and fall behind the schema model.

Infrahub needs to produce the export itself, as one document in the schema file format that loads into an empty instance with no edits and with no warnings other than deprecation warnings for `display_labels` and `default_filter`. `infrahubctl schema export` uses that export and the client-side export logic in the SDK is removed.

Not decided yet:

- the names of the export parameters, of the mode values and of the Infrahub version field (D6, D7);
- whether the feature owner agrees that `BRIEF` writes a derived value next to the value it is derived from (FR-006), which differs from D3 and from the design document example;
- whether the feature owner agrees that the export leaves out kinds Infrahub defines outside the restricted namespaces, such as `IpamNamespace` (FR-003), which extends D2.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Copy the schema to an empty instance (Priority: P1)

The schema owner exports the running schema from instance A, for example a test instance, and loads the export into an empty instance B, for example a new production instance. They do not edit the export before loading it.

**Why this priority**: this is the outcome INFP-723 asks for. Without it the schema owner rewrites the export by hand or keeps the original schema files outside Infrahub.

**Independent Test**: load a test schema into an empty instance, export it, load the export into a second empty instance, and compare the user-defined schema of both instances, ignoring IDs.

**Acceptance Scenarios**:

1. **Given** instance A runs a user-defined schema and instance B has none, **When** the schema owner runs `infrahubctl schema export` against A and loads the files into B, **Then** the load gives no errors, gives no warnings other than the deprecation warnings described under Edge Cases, and the user-defined schema on B is identical to the one on A, ignoring IDs.
2. **Given** a schema owner who can view the schema of a branch, **When** they export with the `branch` parameter set to that branch, **Then** the export holds the schema of that branch.
3. **Given** an export from A loaded into B, **When** the schema owner exports from B, **Then** the second export is identical to the first, apart from the Infrahub version field.
4. **Given** a schema that was loaded with the deprecated top-level `regex`, `min_length` or `max_length`, or the deprecated NumberPool `start_range` and `end_range`, **When** the schema owner exports it and loads the export into an empty instance, **Then** the load gives no deprecation warning and the target has the same validation settings and NumberPool ranges.

---

### User Story 2 - Update an instance that has an earlier version of the schema (Priority: P2)

The schema owner exports from A in `FULL` mode and loads the export into B, which already has an earlier version of the same nodes.

**Why this priority**: an export in the default `BRIEF` mode leaves out derived values, and a value left out does not overwrite a different value on the target when the field has no default (D3). `FULL` mode writes those values so they reach the target (D6).

**Independent Test**: load the same nodes with different labels into two instances, export from the first in `FULL` mode, and check that the export holds the first instance's labels.

**Acceptance Scenarios**:

1. **Given** B has the same nodes as A with different labels, **When** the schema owner exports from A in `FULL` mode, **Then** the export contains A's labels, so a successful load replaces B's labels.
2. **Given** the same instances, **When** the schema owner exports from A in `BRIEF` mode, **Then** a label A derived from the attribute name is left out of the export.

Whether the load into B succeeds depends on the schema loader on B, which is out of scope (see Edge Cases).

---

### User Story 3 - Export selected namespaces (Priority: P3)

The schema owner exports only the `Network` namespace, which references `LocationSite`.

**Why this priority**: schema owners who split their schema by namespace can copy one part. The referenced namespaces can already exist on the target, so the export does not fail on them (decided on 2026-11-20).

**Independent Test**: export one namespace of a schema whose nodes reference a node in another namespace, and check the content of the export.

**Acceptance Scenarios**:

1. **Given** a namespace filter of `Network`, **When** the schema owner exports, **Then** the export contains only the `Network` namespace, and the relationship to `LocationSite` is written as in a full export.

The design document also asks the export to name the kinds outside the selection that it references. That part is left out of the first version (decided on 2026-11-23, see Out of Scope).

---

### User Story 4 - Keep the current file layout of the CLI (Priority: P3)

The schema owner runs `infrahubctl schema export --directory` as today and gets one file per namespace. With a new option, they get one file for all namespaces, the same document the endpoint returns (D9).

**Why this priority**: current users keep the layout they have.

**Independent Test**: run the CLI with and without the single-file option and compare the files written.

**Acceptance Scenarios**:

1. **Given** a schema with several namespaces, **When** the schema owner runs `infrahubctl schema export` without the single-file option, **Then** the CLI writes one file per namespace.
2. **Given** the same schema, **When** the schema owner uses the single-file option, **Then** the CLI writes one file that holds all exported namespaces.
3. **Given** a server that does not have the export endpoint, **When** the schema owner runs `infrahubctl schema export`, **Then** the command fails and names the server version needed (D8).

---

### Edge Cases

A correct export can still fail to load on the target in the cases below. They belong to the schema loader, not to this feature. The documentation page lists each case with the error the schema owner gets. Errors found in the loader through these cases are filed against the loader.

- The target runs an older release: it rejects the Infrahub version field, or a schema setting it does not know.
- The export references kinds the target does not have, for example kinds left out by a namespace filter.
- The same kind is a node on one instance and a generic on the other ([check](https://github.com/opsmill/infrahub/blob/develop/backend/infrahub/core/schema/schema_branch.py#L722-L728)).
- A setting Infrahub cannot update, such as `branch` on an attribute or relationship, differs. It is not known whether the load refuses such a change or ignores it (D6).
- The target's data does not meet a constraint in the export, for example a new required or unique attribute.
- The user does not have the permission to manage the schema on the target.

Cases the export handles in a defined way:

- An extension the schema owner loaded on a user node is written as ordinary attributes and relationships of that node, not as a separate section.
- An extension to a kind in Core or another restricted namespace is not exported, and the export gives no warning (D2). Loading such an extension becomes an error under [opsmill/infrahub#10418](https://github.com/opsmill/infrahub/issues/10418).
- `IpamNamespace` is defined by Infrahub in the `Ipam` namespace, which is not restricted. It is not exported, and a change or extension the schema owner made to it is not exported either, with no warning (FR-003). User kinds in the `Ipam` namespace are exported.
- A value the schema owner wrote that equals the derived value is left out in `BRIEF` mode. After the load, the value follows the field it is derived from, so renaming an attribute later changes a label that was set explicitly (D3).
- A derived value can be written in `BRIEF` mode next to the value it is derived from. Example: a node with no generic and a `unique: true` attribute gets `human_friendly_id` and `uniqueness_constraints` written, although processing would derive them from that attribute. The export loads to the same schema; it is longer than the design document example (FR-006).
- A property a node took from its generic, and whose value still equals the generic's, is written on the node. On the target, as on the source, a later change to the generic does not reach that node (D4).
- A node or generic that has the deprecated `display_labels` or `default_filter` set gives a deprecation warning when the export is loaded ([warnings](https://github.com/opsmill/infrahub/blob/develop/backend/infrahub/core/schema/__init__.py#L138-L153)). Because of FR-005, the export writes these properties on each node that took them from a generic, so the load gives the warning for each of those nodes as well as for the generic. Loading the source files gave it only where the schema owner wrote the property. Processing does not set either property on the exported schemas, so the warning appears only when the schema owner set the property on a node or a generic.
- Loaded into an instance that already has some of the same nodes, the export is merged into the existing schema and removes nothing, in both modes. Nodes, generics, attributes and relationships that the target has and the source does not stay on the target. A value the source does not set, such as a `description` removed on the source, is not written in the export, so the target keeps its own value.
- Loaded into an instance that holds an earlier version of the same schema, the export can give a different result than the schema changes on the source would have given, and the load reports no error. Example: on the source, `name` was renamed to `hostname` and a new `name` was added. The target matches attributes by name, so its existing `name` keeps its values and `hostname` is created empty (D13).

Confirmed by test on 2026-11-20 (in memory, through `POST /api/schema/load`, and after reading the schema back from the database): a change to a node property on a generic, such as `icon` or `order_by`, does not reach nodes that already took the earlier value. This happens on every instance, not only after an export. Only a node created in the same load takes the new value. This is outside this feature and needs its own issue.

## Requirements *(mandatory)*

### Functional Requirements

**Export endpoint**

- **FR-001**: `GET /api/schema/export` MUST return one JSON document in the schema file format (`version`, `nodes`, `generics`). It MUST take the `branch` and `namespaces` parameters, with the same meaning as on `GET /api/schema`, and a `mode` parameter with the values `BRIEF` (the default) and `FULL` (D6, D11).
- **FR-002**: Anyone who can call `GET /api/schema` MUST be able to call the export endpoint. No new permission is required (D10).
- **FR-003**: The export MUST leave out (D2, D6):
  - the restricted namespaces;
  - nodes and generics whose kind Infrahub defines in an unrestricted namespace, today only `IpamNamespace` (decided in planning on 2026-11-26, extends D2, needs the feature owner's agreement);
  - profile and template schemas;
  - generated relationships;
  - IDs and hashes;
  - extensions to kinds in restricted namespaces and to the kinds in the second item.
- **FR-004**: Attributes and relationships marked `inherited` MUST be written only on the generic that defines them, in both modes (D6).
- **FR-005**: The export MUST write on the node each of these properties that the node took from its generic, when the node's value equals the value of the first generic in `inherit_from` that sets it (D4):
  - `human_friendly_id`
  - `display_label`
  - `display_labels`
  - `default_filter`
  - `menu_placement`
  - `uniqueness_constraints`
  - `icon`
  - `order_by`

  A property whose value on the node differs from the generic's follows FR-006 in `BRIEF` mode. Example: processing adds a node's own `unique: true` attribute to the `uniqueness_constraints` it took from the generic, and a load produces the same merged value again.
- **FR-006**: In `BRIEF` mode, the export MUST leave out a value when processing would produce the same value on load, and write it otherwise. This applies to `order_weight` with no special rule (D3). There are two exceptions:
  - the properties in FR-005;
  - a derived value MAY be written when the export also writes the value it is derived from, for example `human_friendly_id` next to a `unique: true` attribute. The export MUST still load to the same schema (SC-001). This differs from D3 and needs the feature owner's agreement (decided in planning on 2026-11-26).
- **FR-007**: In `FULL` mode, the export MUST write every value of the user-defined nodes, generics, attributes and relationships, including derived values such as `label`, `branch`, `order_weight` and a `human_friendly_id` taken from a unique attribute. The exclusions in FR-003 and FR-004 still apply (D6).
- **FR-008**: The export MUST write validation settings (`regex`, `min_length`, `max_length`) only in `parameters` (D5).
- **FR-009**: The export MUST write NumberPool ranges only as `ranges`. It MUST convert the deprecated `start_range` and `end_range` into one range with the same bounds, and a bound that was not set stays unset (D5).
- **FR-010**: The export MUST record the Infrahub version that produced it in a new field. The existing `version: "1.0"` field MUST stay as it is (D7).
- **FR-011**: With a namespace filter, the export MUST contain only the selected namespaces. The values written for a node or generic MUST be the same as in an export without the filter. A namespace in the filter that does not exist on the branch, or a restricted namespace, MUST return HTTP 404 with one error message per such namespace, so every client reports it the same way (decided on 2026-11-27).

**Schema load**

- **FR-012**: `POST /api/schema/load` and the SDK schema validation that `infrahubctl schema load` runs MUST accept the Infrahub version field and ignore it (D7).

**CLI and SDK**

- **FR-013**: `infrahubctl schema export` MUST call the export endpoint and MUST offer a `--mode` option with the same values as the endpoint (D6, D8).
- **FR-014**: `infrahubctl schema export` MUST write one file per namespace by default, and MUST offer an option that writes one file for all namespaces (D9).
- **FR-015**: `infrahubctl schema export --namespaces` MUST pass the selected namespaces to the endpoint.
- **FR-016**: Against a server without the export endpoint, `infrahubctl schema export` MUST fail with a message that names the server version needed. The client-side export logic in the SDK MUST be removed (D8).

**Contract and documentation**

- **FR-017**: The export endpoint MUST be described in `schema/openapi.json`, and the generated frontend REST types MUST be regenerated from it.
- **FR-018**: The documentation MUST have a page on exporting the schema that covers:
  - the `BRIEF` and `FULL` modes;
  - the CLI option for a single file (D9);
  - the known limitations from D2, D3 and D4;
  - what a load into an instance that already has some of the same nodes does not change, as listed in Edge Cases;
  - the cases in Edge Cases where a load can fail, with the error the schema owner gets.
- **FR-019**: `dev/knowledge/backend/` MUST have a file on how the export is built from the stored schema. It covers:
  - which fields the export writes, and that a field's visibility decides it;
  - how `BRIEF` mode decides which values to leave out, and how to find out why a value was left out of an export;
  - which field definitions are marked so that `BRIEF` mode never removes them, and how CI shows a missing mark;
  - that `BRIEF` output can change between releases when schema processing changes, while the export still loads to the same schema;
  - which properties a node keeps from its generic, and where that list is kept.

### Key Entities

All entities exist already. No entity is added.

- **Schema file format** (`version: "1.0"`, `nodes`, `generics`): the format of the export. Gains one field, the Infrahub version.
- **Stored schema**: the schema after processing, and the source of the export. It does not record whether a value was set by the schema owner or derived (D1).
- **Node, generic, attribute, relationship and attribute-parameter schema models**: their fields that a schema file can set are the ones SC-004 tracks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of the test schemas (`models/base/` and the variation schemas), loading the export into an empty instance gives the same user-defined schema as the source, ignoring IDs, in both `BRIEF` and `FULL` mode.
- **SC-002**: Loading an export into an empty instance on the same release or a newer one gives zero errors, for every test schema. It gives zero warnings, except deprecation warnings for `display_labels` and `default_filter` on a node or generic where the schema owner set the property or that took it from a generic (Edge Cases).
- **SC-003**: For every test schema, exporting the target again gives a document identical to the first export, apart from the Infrahub version field.
- **SC-004**: A field that a schema file can set, added to the node, generic, attribute, relationship or attribute-parameter schema models, fails CI until a test schema uses it or it is marked as not needing a test (D12). Read-only fields are not tracked, because the export never writes them.
- **SC-005**: For every test schema exported in `FULL` mode, a check of the exported file alone finds every value written, except the ones FR-003 and FR-004 leave out and the deprecated forms FR-008 and FR-009 replace.
- **SC-006**: A test schema loaded with the deprecated NumberPool `start_range` and `end_range` gives the same ranges on the target, with no warning on load.

## Assumptions

- The stored schema is enough to produce the export. No record of where each value came from is needed (D1).
- The SDK change merges in [infrahub-sdk-python](https://github.com/opsmill/infrahub-sdk-python) first (part 1), then the Infrahub change (part 2).
- The parameter names (`mode`, `namespaces`), the mode values (`BRIEF`, `FULL`) and the name of the Infrahub version field are working names and can change in the plan (D6, D7).
- The variation schemas are new inline schemas, because each tests a shape the existing fixtures do not have.
- The realistic test schemas are `models/base/` only, as D12 in the design document states. A shape found only in `models/examples/` is covered by a variation schema.
- No end-to-end browser test is needed, because this feature changes no UI. The separate UI download card will need one.

## Out of Scope

- The `IDS` mode, which adds element IDs to `FULL` (D6).
- Downloading the export from the UI: a separate frontend card, not created yet.
- Reproducing the files that were loaded (D1).
- Exporting extensions to kinds in restricted namespaces (D2), or to other kinds Infrahub defines, such as `IpamNamespace`.
- How the schema loader handles the cases in Edge Cases.
- Exporting migrations ([INFP-719](https://opsmill.atlassian.net/browse/INFP-719), D13).
- Comparing schemas between instances ([INFP-751](https://opsmill.atlassian.net/browse/INFP-751)).
- A change to a generic not reaching existing nodes: its own issue.
- Using the Infrahub version field to stop a load into an older release (D7).
- Editing the schema as YAML in the UI and loading it.
- Naming, in a namespace-filtered export, the kinds outside the selection that it references. The design document asks for it (decided on 2026-11-20). The feature owner left it out of the first version on 2026-11-23.
- Measuring use of the export after release. No telemetry is added (decided on 2026-11-23).

## Follow-ups

- For the QA test plan after the feature ships: check that `order_weight` matches on the target after a schema has been loaded in several steps on the source.
- An issue to move `IpamNamespace` to a restricted namespace. Renaming the kind changes stored data, the GraphQL API and users' queries, so it needs a migration and a deprecation plan.
- An issue on protecting `IpamNamespace` from schema loads. No check refers to it in `backend/infrahub/core/schema/schema_branch.py`, `backend/infrahub/core/schema/manager.py` or `backend/infrahub/api/schema.py`, so a schema load can probably change it or add to it, because `Ipam` is not restricted. This is not confirmed by a test, and whether a load can delete it is not known. It is the same kind of problem as [opsmill/infrahub#10418](https://github.com/opsmill/infrahub/issues/10418).
- Storing only the schema values the schema owner set, and deriving the rest when the schema is read. It would let the export leave out every derived value (FR-006) without the reduction loop.
