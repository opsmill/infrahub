# Feature Specification: Export the Running Schema

**Feature Branch**: `schema-export-infp-723`

**Created**: 2026-10-26

**Status**: Draft

**Input**: Jira idea [INFP-723](https://opsmill.atlassian.net/browse/INFP-723) (read on 2026-10-26), the
engineering story [IFC-2964](https://opsmill.atlassian.net/browse/IFC-2964)
([opsmill/infrahub#10094](https://github.com/opsmill/infrahub/issues/10094)) and the design document
[INFP-723 · Export the running schema](https://app.notion.com/p/opsmill/INFP-723-Export-the-running-schema-401228b83025812589c6e6664594db35)
(Notion, status "Draft", last edited 2026-10-23, read in full on 2026-10-26). Decision numbers (D1 to D12)
refer to section 3 of the design document. The comparison of schemas between instances is a separate card,
[INFP-751](https://opsmill.atlassian.net/browse/INFP-751), and depends on this export.

## Summary

**Problem.** A schema owner cannot take the schema that an Infrahub instance runs and load it into another
instance. `GET /api/schema` returns the processed schema, with IDs, hashes, inherited elements and generated
relationships, so it does not load as it is. `infrahubctl schema export` removes part of that on the client,
but its rules are a hand-maintained copy of the server's internals that drifts from the schema model
([IFC-2964](https://opsmill.atlassian.net/browse/IFC-2964)), and it keeps the generated `object_template`
relationship, so the load likely fails for nodes that use templates (not tested, design document section 2).

**What is needed.**

- Download the running schema of a branch from Infrahub as one document in the schema file format.
- Load that document into an empty instance without editing it and get the same user-defined schema, with
  no warnings.
- Choose between a short export that leaves out derived values (`BRIEF`, the default) and a complete export
  that writes them (`FULL`), so that a load into an instance that already has some of the same nodes
  overwrites that instance's values.
- Keep using `infrahubctl schema export`, which calls the new endpoint instead of applying its own rules.
- Have CI fail when a field is added to the schema models without a decision about how the export handles it.

**Not decided yet.**

- The names of the export mode parameter, its values and the Infrahub version field. The design document
  says they are not final (D6, D7). The plan fixes them.
- Whether a `FULL` export that changes a setting Infrahub cannot update, such as `branch` on an attribute or
  relationship, is refused or ignored by the load. The design document says it is not known (D6).
- Whether `order_weight` can be left out and generated again identically, and whether the deprecated
  NumberPool `start_range` and `end_range` are converted into `ranges`. The design document lists both as
  checks to make during implementation.

## Clarifications

### Session 2026-10-26

- Q: Does the export offer the `BRIEF` and `FULL` modes suggested in D6? → A: Yes. `BRIEF` is the default,
  on the endpoint and in `infrahubctl schema export`. The `IDS` mode stays deferred (FR-014 to FR-016).
- Q: With a namespace filter, when the selected namespaces reference kinds in a namespace outside the
  selection, what does the export do? → A: It exports only the selected namespaces and returns a warning
  that names the referenced namespaces, following the engineering recommendation in the design document.
  Replaced by the answer on where the warning appears, below: the export has no warning.
- Q: Is a download of the export from the UI part of this spec? → A: No. The export is available from the
  API and `infrahubctl` only. The estimate on INFP-723 does not include a UI action.
- Q: Where does the namespace warning appear in the export response? → A: Nowhere. The export returns no
  warning. A filtered export contains only the selected namespaces, and the schema owner is responsible for
  loading the namespaces they reference (FR-017).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Export the running schema and load it into an empty instance (Priority: P1)

A schema owner downloads the schema that a branch of their instance runs, as one document in the schema
file format, and loads it into an empty instance without editing it. The target instance then has the same
user-defined schema as the source instance. The schema owner no longer keeps a separate copy of the schema
files to set up the next instance (INFP-723, "Impact").

**Why this priority**: It is the need stated on INFP-723 and the base that INFP-751 depends on. Every other
story uses the export it produces.

**Independent Test**: Load a schema into an instance, call the export endpoint, load the response into an
empty instance with `POST /api/schema/load`, and compare the user-defined schema of both instances, ignoring
IDs.

**Acceptance Scenarios**:

1. **Given** an instance with a user-defined schema loaded on `main`, **When** the schema owner calls the
   export endpoint without parameters, **Then** they receive one document in the schema file format that
   contains the user-defined nodes and generics of `main`, the schema file format version `"1.0"` and the
   Infrahub version that produced it.
2. **Given** that export, **When** the schema owner loads it into an empty instance as one entry of the
   `schemas` list of `POST /api/schema/load`, **Then** the load succeeds with no warnings and the
   user-defined schema of the target instance is identical to the source instance's, ignoring IDs.
3. **Given** the target instance from scenario 2, **When** the schema owner exports its schema, **Then** the
   document is identical to the first export apart from the Infrahub version field.
4. **Given** a node that uses object templates, **When** its schema is exported and loaded into an empty
   instance, **Then** the load succeeds, because the generated `object_template` relationship is not in the
   export.
5. **Given** a branch with schema changes that are not on `main`, **When** the schema owner calls the export
   endpoint with that `branch`, **Then** the export contains the schema of that branch.
6. **Given** a node that took `icon`, `human_friendly_id` or another property from its generic without
   setting it, **When** the schema is exported, **Then** the property is written on the node, as described
   in the documentation's known limitations (D4).

---

### User Story 2 - Export the schema with `infrahubctl` (Priority: P1)

A schema owner runs `infrahubctl schema export` and gets YAML files they can commit to a Git repository or
load into another instance. The command calls the export endpoint, so its output follows the server's rules
and does not drift from the schema model.

**Why this priority**: `infrahubctl schema export` is how schema owners export today. Without this story, the
CLI keeps its own rules and the two exports differ.

**Independent Test**: Run `infrahubctl schema export --directory <dir>` against an instance with several
namespaces, check that it writes one file per namespace whose content matches the endpoint's response for
that namespace, then run `infrahubctl schema load` on those files against an empty instance.

**Acceptance Scenarios**:

1. **Given** an instance with user-defined nodes in the `Network` and `Dcim` namespaces, **When** the schema
   owner runs `infrahubctl schema export --directory out`, **Then** the command writes `out/network.yml` and
   `out/dcim.yml`, as it does today.
2. **Given** the same instance, **When** the schema owner runs the command with the single-file option,
   **Then** the command writes one YAML file that contains all namespaces, with the same content as the
   endpoint's response.
3. **Given** the files from scenario 1 or 2, **When** the schema owner runs `infrahubctl schema load` on them
   against an empty instance, **Then** the SDK schema validation accepts the Infrahub version field and the
   load succeeds.
4. **Given** a server on a release without the export endpoint, **When** the schema owner runs
   `infrahubctl schema export`, **Then** the command fails with a message that names the server version it
   needs.

---

### User Story 3 - Export every value to update an instance that already has the schema (Priority: P2)

A schema owner loads an export into an instance that already has some of the same nodes, for example a
staging instance that drifted from production. With the default `BRIEF` export, a value the export leaves out
because it equals the derived value does not overwrite the target's value when the field has no default, for
example `label`, `branch` or `order_weight`. The schema owner requests a `FULL` export instead, which writes
those values so the load overwrites them.

**Why this priority**: The design document's promise (D1) covers only an empty target instance. This story
extends it to the values Infrahub can update on an existing instance, which is the case of moving a schema
between running instances named on INFP-723.

**Independent Test**: On a target instance, load a schema with `label: Hostname` on an attribute. On a source
instance, load the same schema with no label on that attribute. Export the source in `FULL` mode, load the
export into the target, and check that the attribute's label on the target is the derived label.

**Acceptance Scenarios**:

1. **Given** a source instance where an attribute `hostname` has the derived label and a target instance
   where the same attribute has `label: Hostname`, **When** the schema owner loads a `BRIEF` export of the
   source into the target, **Then** the target keeps `Hostname`.
2. **Given** the same instances, **When** the schema owner loads a `FULL` export of the source into the
   target, **Then** the target's label becomes the source's derived label.
3. **Given** any schema, **When** the schema owner requests a `FULL` export, **Then** the export still leaves
   out IDs, hashes, inherited attributes and relationships, generated relationships, profile and template
   schemas, and extensions to kinds in restricted namespaces.
4. **Given** any schema, **When** the schema owner does not set a mode, **Then** the export is in `BRIEF`
   mode.

---

### User Story 4 - Export only some namespaces (Priority: P3)

A schema owner exports only the namespaces they own, for example to load one namespace into an instance that
already has the others. The export contains only the selected namespaces, even when they reference kinds in a
namespace outside the selection. Infrahub does not warn about those references, so an export of one namespace
that references another does not load into an empty instance on its own.

**Why this priority**: `infrahubctl schema export --namespaces` already offers this. The other stories work
without a namespace filter.

**Independent Test**: Load a schema where a node in `Network` has a relationship to a node in `Dcim`. Export
only `Network`, check that the export contains only `Network`, and load it into an instance that already has
the `Dcim` schema.

**Acceptance Scenarios**:

1. **Given** a node in `Network` with a relationship to a node in `Dcim`, **When** the schema owner exports
   with `namespaces=Network`, **Then** the export contains only the `Network` nodes and generics, and no
   warning.
2. **Given** the same schema, **When** the schema owner runs `infrahubctl schema export --namespaces Network`,
   **Then** the command writes only the `Network` file.
3. **Given** the `Network` export from scenario 1, **When** the schema owner loads it into an instance that
   already has the `Dcim` schema, **Then** the load succeeds.

---

### Edge Cases

- **Load into an instance on an older release.** An instance on a release from before the Infrahub version
  field rejects the export, because its schema load reports the unknown field as an error (D7). The
  documentation states this.
- **Extensions to kinds in Core or another restricted namespace.** An instance that loaded such an extension
  before [opsmill/infrahub#10418](https://github.com/opsmill/infrahub/issues/10418) is fixed exports a schema
  without it, and the export does not warn (D2).
- **Value written by the user that equals the derived value.** In `BRIEF` mode it is left out. After the
  export is loaded into another instance, the value follows the field it is derived from, so renaming an
  attribute changes a label that was set explicitly (D3).
- **Property copied from a generic.** It is fixed on the node in the target instance, and a later change to
  the generic no longer reaches that node. To keep a node following its generic, the schema owner removes the
  copied properties from the exported file before loading it (D4).
- **Deprecated validation fields.** A schema loaded with the deprecated top-level `regex`, `min_length` or
  `max_length` is exported with those settings under `parameters` (D5).
- **`unique: true` on an attribute.** The export writes `unique: true` and leaves out the matching
  single-attribute uniqueness constraint (design document section 2, unchanged from today).
- **Instance with no user-defined schema.** Today `infrahubctl schema export` prints "No user-defined schema
  found to export." and writes no file
  ([CLI](https://github.com/opsmill/infrahub-sdk-python/blob/infrahub-develop/infrahub_sdk/ctl/schema.py)).
  The sources do not say what the endpoint returns in this case (see Assumptions).
- **`FULL` export that changes a setting Infrahub cannot update.** It is not known whether the load refuses
  the change or ignores it (D6). The plan establishes it.

## Requirements *(mandatory)*

### Functional Requirements

#### What the export contains

- **FR-001**: The export MUST return one document in the schema file format for one branch, with the existing
  schema file format field `version: "1.0"` unchanged (D7, D11).
- **FR-002**: The export MUST contain only the nodes and generics the user defines. It MUST leave out the
  restricted namespaces and the generated profile and template schemas, as `infrahubctl schema export` does
  today ([SDK export](https://github.com/opsmill/infrahub-sdk-python/blob/infrahub-develop/infrahub_sdk/schema/__init__.py#L141-L183)).
- **FR-003**: The export MUST leave out IDs, hashes, inherited attributes and relationships, and generated
  relationships, including `member_of_groups`, `subscriber_of_groups`, `profiles` and `object_template`
  (design document section 2 and D4 example).
- **FR-004**: The export MUST write an extension of a user node as ordinary attributes and relationships of
  that node, not as a separate section.
- **FR-005**: The export MUST NOT contain extensions to kinds in Core or another restricted namespace (D2).
- **FR-006**: In `BRIEF` mode, the export MUST leave out a value when processing would produce the same value
  on load, and write it otherwise. This covers values such as `optional: true` with a `default_value`, a
  `label` taken from the name, a `human_friendly_id` taken from a unique attribute, a uniqueness constraint
  generated from a `human_friendly_id`, and the `branch` setting of an attribute or relationship when it
  equals the value derived from the node or the peer (D3).
- **FR-007**: The export MUST write on the node the properties it took from a generic: `human_friendly_id`,
  `display_label`, `display_labels`, `default_filter`, `menu_placement`, `uniqueness_constraints`, `icon` and
  `order_by`. This is an exception to FR-006 (D4).
- **FR-008**: The export MUST write `unique: true` on an attribute and leave out the matching
  single-attribute uniqueness constraint.
- **FR-009**: The export MUST write validation settings (`regex`, `min_length`, `max_length`) only in
  `parameters`, never in the deprecated top-level fields (D5).
- **FR-010**: The export MUST record the Infrahub version that produced it in a field separate from
  `version` (D7).

#### Loading the export into another instance

- **FR-011**: `POST /api/schema/load` and the SDK schema validation that `infrahubctl schema load` runs MUST
  accept the Infrahub version field and ignore it (D7).
- **FR-012**: Loading an export into an empty instance MUST succeed with no warnings and give a user-defined
  schema identical to the source instance's, ignoring IDs, in both modes (D1, D12).
- **FR-013**: Exporting the schema of that target instance again MUST give a document identical to the
  first export, apart from the Infrahub version field (D12).

#### `BRIEF` and `FULL` export modes

- **FR-014**: The export MUST offer two modes: `BRIEF`, the default, which applies FR-006 to FR-009, and
  `FULL` (D6).
- **FR-015**: In `FULL` mode, the export MUST write every value of the nodes, generics, attributes and
  relationships the user defines, including derived values such as `label`, `branch`, `order_weight` and a
  `human_friendly_id` taken from a unique attribute. It MUST still apply FR-002, FR-003, FR-005 and FR-009
  (D6).
- **FR-016**: The export MUST NOT offer a mode that writes IDs. The `IDS` mode is deferred (D6).

#### Branch and namespace selection, and access

- **FR-017**: The export MUST accept the same `branch` and `namespaces` parameters as `GET /api/schema`
  (D11). When `namespaces` is set, the export MUST contain only the selected namespaces, including when they
  reference kinds in a namespace outside the selection. The export MUST NOT add the referenced namespaces or
  return a warning about them.
- **FR-018**: Any user who can call `GET /api/schema` MUST be able to export the schema. Loading the export
  still requires the permission to manage the schema on the target instance (D10).

#### Export with `infrahubctl schema export`

- **FR-019**: `infrahubctl schema export` MUST get the export from the endpoint, and the SDK MUST no longer
  apply export rules on the client (D8).
- **FR-020**: By default, `infrahubctl schema export` MUST write one YAML file per namespace, with the file
  names it uses today. A command-line option MUST write one YAML file for all namespaces (D9).
- **FR-021**: `infrahubctl schema export` MUST pass its `--branch` and `--namespaces` options to the endpoint,
  and offer a `--mode` option for `BRIEF` and `FULL`.
- **FR-022**: Against a server without the export endpoint, `infrahubctl schema export` MUST fail with a
  message that names the server version it needs (D8).

#### Tests that catch drift from the schema models, and documentation

- **FR-023**: A test MUST list every field of the node, generic, attribute, relationship and
  attribute-parameter schema models. A field that is neither covered by an export test nor marked as not
  needing one MUST fail CI (D12).
- **FR-024**: The schemas in `models/base/` and `models/examples/`, and one small schema for each export
  rule, MUST be exported, loaded into an empty instance and checked against FR-012 and FR-013 in both modes
  (D12).
- **FR-025**: The documentation MUST include a page on exporting the schema that describes the two modes, the
  single-file option and the known limitations from D2, D3 and D4 (design document section 4,
  "Follow-ups").

### Key Entities

- **Schema export**: one document in the schema file format that contains the user-defined nodes and
  generics of one branch, the schema file format version and the Infrahub version that produced it.
- **Export mode**: `BRIEF` (default) leaves out derived values. `FULL` writes them. Both leave out IDs,
  hashes, inherited and generated elements.
- **Derived value**: a value that Infrahub fills in when it processes a loaded schema, such as a label, an
  inherited attribute, a generated relationship or a uniqueness constraint generated from a
  `human_friendly_id`. Infrahub stores the processed schema and does not record whether a value was set by
  the user or derived (D1).
- **Property copied from a generic**: a node-level property that a node took from the first generic in
  `inherit_from` that sets it, when the node does not set it
  ([inheritance](https://github.com/opsmill/infrahub/blob/develop/backend/infrahub/core/schema/node_inheritance_handler.py#L17-L29)).
- **Infrahub version field**: a field of the export that records the release that produced it. The schema
  load accepts and ignores it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every schema in `models/base/`, `models/examples/` and the per-rule test schemas, in both
  modes, loading the export into an empty instance succeeds with zero warnings and gives a user-defined
  schema identical to the source, ignoring IDs.
- **SC-002**: For every schema in SC-001, a second export from the target instance is identical to the first
  apart from the Infrahub version field.
- **SC-003**: Adding a field to any of the five schema models named in FR-023 without an export decision
  fails CI every time.
- **SC-004**: A schema owner moves a schema from one instance to an empty instance with one export command
  and one load command, with no manual edit of the exported files.
- **SC-005**: The export rules exist in one place: the SDK contains no list of restricted namespaces or
  fields to remove for the export.

## Assumptions

- **Delivery order.** The SDK change (Infrahub version field in the SDK schema validation, CLI calling the
  endpoint, single-file and `--mode` options, error for older servers, removal of the client-side export)
  merges in the [SDK repository](https://github.com/opsmill/infrahub-sdk-python) first. The Infrahub change
  (endpoint, rules, tests) follows, with a bump of the `python_sdk` submodule (design document section 3,
  "Implementation").
- **Endpoint form.** The export is a REST endpoint, `GET /api/schema/export`, that returns JSON (D11). It
  changes `schema/openapi.json` and the generated frontend REST types. `infrahubctl` converts the JSON to
  YAML files.
- **Empty export.** When the selected branch and namespaces contain no user-defined schema, the endpoint
  returns a document with no nodes and no generics, and `infrahubctl schema export` keeps printing its
  current message. The sources do not state this; it is an assumption for the plan to confirm.
- **Unknown branch.** An export for a branch that does not exist fails as `GET /api/schema` does for that
  branch. The sources do not state this.
- **Out of scope.** Downloading the export from the UI (clarification of 2026-10-26); comparing schemas,
  tracked in [INFP-751](https://opsmill.atlassian.net/browse/INFP-751); rejecting extensions to kinds in
  restricted namespaces, tracked in [opsmill/infrahub#10418](https://github.com/opsmill/infrahub/issues/10418);
  reproducing the files that were loaded (D1); recording whether each value was set by the user or derived;
  the `IDS` mode; using the Infrahub version field to stop a load into an older release (D7); editing the
  schema in the UI by changing YAML (design document section 4).
- **Follow-ups outside this spec.** A file in `dev/knowledge/backend/` on schema processing and the export
  rules, and an update of [IFC-2964](https://opsmill.atlassian.net/browse/IFC-2964) with the decisions of the
  design document (design document section 4).
