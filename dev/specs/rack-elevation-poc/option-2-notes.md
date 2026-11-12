# Rack elevation POC: notes on option 2 (`rack_elevation` schema property)

Sources: [Plan 3, option 2](https://claude.ai/artifact/KvMJYdNBJ1nSUNsW8vnuVU) and [Plan 1, base branch](https://claude.ai/artifact/2SE2YYumWDDCzMEvFSaUQJ). The headings follow the list in Plan 3 so that they can be read next to the notes of option 1. The notes of option 1 were not available when this file was written.

## What was and was not run

- Passed: the 18 schema unit tests in `backend/tests/unit/core/schema/test_schema_branch_rack_elevation.py`, `uv run invoke format`, `uv run invoke lint`.
- Not run: the contract tests, the tests in `test_mapped_provider.py` and the end-to-end test. The Docker daemon did not answer in the session that wrote this branch, so no Neo4j was available. They were collected (33 component tests) and not executed, and the placement, mutation and node-class code has no database run behind it yet.
- Not measured: the two query timings below.

## Lines added outside the tests

Reproduce with `git diff --numstat bgi/rack-elevation-base -- backend/infrahub backend/templates`.

| Area | Lines added | Files |
|---|---|---|
| Schema model and validation | 205 | `rack_elevation_schema.py`, `rack_elevation_validator.py`, `definitions/internal.py`, `node_inheritance_handler.py`, `basenodeschema_imports.j2` |
| Attribute generation | 57 | `add_rack_elevation_attributes` in `schema_branch.py`, the constants it uses |
| Mapping helper | 138 | `rack_elevation/mapped/mapping.py` |
| Provider | 206 | `rack_elevation/mapped/provider.py`, the factory in `rack_elevation/provider.py` (28 lines of the base stub removed) |
| Standard mutations | 127 | `graphql/mutations/rack_elevation_mapped.py`, the base class choice in `graphql/manager.py` |
| Node class | 57 | `core/node/rack.py`, `identify_node_class` in `core/manager.py`, the registration in `core/initialization.py` |

Generated files, counted apart: 6 lines in `core/schema/generated/base_node_schema.py`, 78 in `schema/openapi.json`, 26 in the schema reference pages under `docs/docs/reference/schema/`.

`python_sdk` changes, counted apart: 8 lines in `infrahub_sdk/schema/generated/{read,write}.py`, committed on the local submodule branch `bgi/rack-elevation-option-2`. They are not pushed to the SDK repository.

## Query timings

Not known. The `RackElevation` query for R1 and the `LocationRack` list query of 20 racks with the three calculated attributes were not run. The list query loads each rack again to calculate its totals, so N racks cost N extra loads.

## Gaps accepted for the POC

The same as option 1, so the comparison stays fair:

- A change to the height or depth of an item type, or to the height of a rack, is not checked against the items already placed.
- Deleting a rack leaves its items without a rack.
- A write made from the rack's side of the relationship is not checked.
- `RackElevationPlace` writes through the provider and does not send the node-updated event, so a move made from the elevation produces no event. The move is also saved without the user who made it.

Specific to this option:

- A schema file cannot remove a mapping. Loading a node without `rack_elevation` keeps the stored mapping, as for every other optional property. The code that removes the calculated attributes from a kind that is no longer a rack runs, but a customer has no way to trigger it by omitting the property.
- The SDK models type `rack_elevation` as a plain dictionary. The backend validates the keys when the schema loads, and the SDK does not.
- A rack kind that declares an attribute with the same name as a calculated attribute, and also marks it read-only without overriding, is treated as the generated attribute.

## What a `schema-library` user changes

- On `LocationRack`: add `rack_elevation` with the role `rack` and the path of the height attribute. The height must be a Number attribute. In the end-to-end base schema (`models/base`), `LocationRack.height` is a Text attribute, so that kind needs a data change, not only a property.
- On `DcimDeviceType` and `DcimRackAccessoryType`: add `rack_elevation` with the role `mountable_type` and the paths of the height (Number), full depth (Boolean) and weight (Number) attributes.
- On the mountable kinds: add `rack_elevation` with the role `mountable`, the rack relationship, and the position (Number) and face (Dropdown with the choices `front` and `rear`) attributes. In the test schema, `DcimPhysicalDevice` has the position and face attributes and the `location` relationship, as Plan 3 describes for `schema-library`. It is not known whether `schema-library` itself matches, because it was not read.
- `type` forced the mapping to be repeated on each node. A generic cannot name `type`, because `device_type` and `accessory_type` are relationships of the nodes. The node's own mapping replaces the generic's mapping as a whole, so each node repeats `rack`, `position` and `face`. For that reason the `type` key is optional on a generic and required on a node.
- The generic in the test schema, `DcimPhysicalDevice`, also carries the `name` attribute. The plan lists only `position` and `rack_face` on it, but the display label `name__value` set on the generic must resolve on the generic itself.
- The end-to-end fixture loads the test schema on a stack without `schema_base`. On top of `schema_base`, `LocationRack` has a Text height and a mandatory parent site, and the loaded schema would conflict with it.

## Validation errors a customer can see

Each message starts with the kind and the key. The examples come from the unit tests.

| Mistake | Message |
|---|---|
| Path to an attribute that does not exist | `DcimDevice.rack_elevation.position: positon__value is invalid on schema DcimDevice` |
| Path to an attribute of the wrong kind | `DcimDevice.rack_elevation.position: attribute 'name' is a Text, expected a Number` |
| Path that crosses a relationship | `DcimDevice.rack_elevation.position: this property only supports attributes, not relationships` |
| Path that does not end with `__value` | `DcimPhysicalDevice.rack_elevation.face: the path must end with '__value'` |
| Face Dropdown without both choices | `DcimDevice.rack_elevation.face: dropdown 'rack_face' must have the choices front, rear` |
| Relationship that does not exist | `DcimDevice.rack_elevation.rack: relationship 'site' does not exist` |
| Relationship of cardinality many | `DcimDevice.rack_elevation.type: relationship 'device_type' must have a cardinality of one` |
| Peer without the expected role | `DcimDevice.rack_elevation.type: the peer 'DcimDeviceType' of relationship 'device_type' must have the rack_elevation role 'mountable_type'` |
| Node without `type` | `DcimDevice.rack_elevation.type: a node must name its type relationship` |
| Rack kind with a calculated attribute name | `LocationRack.rack_elevation: attribute 'rack_utilization' is calculated by Infrahub on a rack kind and cannot be declared` |

At save time, a refused placement returns `ATTRIBUTE_CONSTRAINT_VIOLATION` with the constraint of the shared rules, and the field name is the customer's: `position`, `rack_face` or `location` in the test schema.
