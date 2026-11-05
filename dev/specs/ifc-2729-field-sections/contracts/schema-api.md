# Contract: containers in the schema REST API

Applies to `GET /api/schema`, `GET /api/schema/{kind}` and `POST /api/schema/load`. The GraphQL
schema and queries do not change. All examples use the mockup's LAG interface; keys that this
feature does not touch are left out of the JSON.

## What GET /api/schema and GET /api/schema/{kind} return

- Nodes, generics, profiles and templates carry `containers`: a list of
  `{name, label, description, order_weight, collapsed, state, inherited}` items, `[]` when the
  kind declares none. `state` is `present` on every item a read returns, as on attributes and relationships.
  The list is the kind's view after inheritance: a node returns the containers it declares plus
  those of its generics, merged by name. A profile or template returns the containers of the node
  it was generated from. `details` and `advanced` are never listed. `inherited` is `true` on a
  copy taken from a generic and `false` on a container the kind declares itself; on a profile or
  template every item has `inherited: false`.
- Attributes and relationships carry `container`: the container name as a string, or `null` when
  the field belongs to the Details section. `"advanced"` is returned as written.
- The list order of `containers` is the stored order. On a node, the inherited containers come
  first, in the order of the generics in `inherit_from` and of each generic's list, then the
  containers the node declares itself. A node container with the same name as an inherited one
  takes the position of the inherited one.
  Clients order sections by `order_weight`, then declaration order for items without a weight.
- Both fields are present whatever the `branch` query parameter, with the values stored on that
  branch.

Example `GET /api/schema/InfraLagInterface` (abridged):

```json
{
  "name": "LagInterface",
  "namespace": "Infra",
  "kind": "InfraLagInterface",
  "containers": [
    {"name": "lacp", "label": "LACP", "description": null, "order_weight": 100, "collapsed": false, "state": "present", "inherited": false},
    {"name": "layer2", "label": "Layer 2", "description": "Switching settings of the bundle", "order_weight": 200, "collapsed": false, "state": "present", "inherited": false},
    {"name": "layer3", "label": "Layer 3", "description": null, "order_weight": 300, "collapsed": true, "state": "present", "inherited": false}
  ],
  "attributes": [
    {"name": "name", "kind": "Text", "container": null, "display": "default", "order_weight": 1000},
    {"name": "description", "kind": "Text", "container": null, "display": "default", "order_weight": 2000},
    {"name": "status", "kind": "Dropdown", "container": null, "display": "default", "order_weight": 3000},
    {"name": "role", "kind": "Dropdown", "container": null, "display": "default", "order_weight": 4000},
    {"name": "bundle_number", "kind": "Number", "container": "lacp", "display": "default", "order_weight": 5000},
    {"name": "lacp_rate", "kind": "Text", "container": "lacp", "display": "default", "order_weight": 6000},
    {"name": "lacp_mode", "kind": "Text", "container": "lacp", "display": "default", "order_weight": 7000},
    {"name": "l2_mode", "kind": "Text", "container": "layer2", "display": "default", "order_weight": 8000},
    {"name": "dot1q_id", "kind": "Number", "container": "layer2", "display": "default", "order_weight": 9000},
    {"name": "mac_address", "kind": "MacAddress", "container": "layer2", "display": "extra", "order_weight": 10000},
    {"name": "mtu", "kind": "Number", "container": "layer3", "display": "default", "order_weight": 11000}
  ],
  "relationships": [
    {"name": "device", "peer": "InfraDevice", "container": null, "order_weight": 12000},
    {"name": "tags", "peer": "BuiltinTag", "container": null, "order_weight": 13000},
    {"name": "mlag_peer_link", "peer": "InfraMlagInterface", "container": "lacp", "order_weight": 14000},
    {"name": "untagged_vlan", "peer": "InfraVLAN", "container": "layer2", "order_weight": 15000},
    {"name": "ip_addresses", "peer": "IpamIPAddress", "container": "layer3", "order_weight": 16000},
    {"name": "sub_interfaces", "peer": "InfraInterface", "container": "advanced", "order_weight": 17000}
  ]
}
```

A kind without sections returns `"containers": []` and `"container": null` on every field.

## What POST /api/schema/load accepts

- `containers` on a node or generic: a list of items with a required `name` and `label`, an
  optional `description`, `order_weight`, `collapsed` and `state`. `state` is a writable field of
  the item (`present` by default, `absent` removes the item), as on attributes and relationships;
  `inherited` is read-only, as on attributes and relationships, so a load that sends it gets a
  read-only warning and the value is dropped. An unknown key inside an item fails
  the write contract with a 422, as for any other schema key.
- `container` on an attribute or relationship: a string or `null`.
- A load that only changes containers or container assignments needs no migration and no
  constraint check; the response reports none.
- A load that leaves a container out of the list keeps it; `"state": "absent"` on the item
  removes it.
- A load that only changes the order of the containers is a schema change: the new order is
  stored. A branch merge where both branches reorder the same kind's containers differently reports
  a conflict on `containers`.

Example request body (abridged):

```json
{
  "schemas": [
    {
      "version": "1.0",
      "generics": [
        {
          "name": "LagInterface",
          "namespace": "Infra",
          "containers": [
            {"name": "lacp", "label": "LACP", "order_weight": 100},
            {"name": "layer2", "label": "Layer 2", "order_weight": 200, "description": "Switching settings of the bundle"},
            {"name": "layer3", "label": "Layer 3", "order_weight": 300, "collapsed": true}
          ],
          "attributes": [
            {"name": "bundle_number", "kind": "Number", "container": "lacp"},
            {"name": "mac_address", "kind": "MacAddress", "display": "extra", "container": "layer2"}
          ],
          "relationships": [
            {"name": "sub_interfaces", "peer": "InfraInterface", "cardinality": "many", "container": "advanced"}
          ]
        }
      ]
    }
  ]
}
```

## Rejected loads and their 422 bodies

Every rejection is a 422 whose body is
`{"data": null, "errors": [{"message": "<message>", "extensions": {"code": 422}}]}`. The messages,
with the placeholders filled from the request:

- A field references a container the kind does not have after inheritance:

```json
{"data": null, "errors": [{"message": "InfraLagInterfaceL2.attributes.mtu.container: container 'layer4' is not declared on InfraLagInterfaceL2", "extensions": {"code": 422}}]}
```

  The same shape with `relationships.<name>.container` for a relationship. When the reference is on
  an inherited field whose container was removed from the generic, the kind in the message is the
  node that fails.

- Two containers with the same name on one kind after inheritance:

```json
{"data": null, "errors": [{"message": "InfraLagInterface.containers: container names must be unique, duplicate 'lacp'", "extensions": {"code": 422}}]}
```

- A container named `details` or `advanced` in the list:

```json
{"data": null, "errors": [{"message": "InfraLagInterface.containers: 'advanced' is a built-in container and cannot be declared", "extensions": {"code": 422}}]}
```

  The message names `'details'` for that name. A field with `"container": "details"` gets the
  not-declared message above, because fields without a container already belong to Details.

- A container item without `label`, or with a `name` outside the attribute name rules: rejected by
  the write contract's Pydantic validation with the standard FastAPI `detail` body, before the
  validator runs.

## SDK and formatter

- `infrahub_sdk.schema.generated.read` gains `ContainerSchemaRead`, which carries `inherited`;
  `BaseNodeSchemaRead` gains `containers`; the attribute and relationship read models gain
  `container`. The write and contract models gain the matching fields, so the SDK's offline
  validation accepts both.
- `infrahubctl schema export` writes only the containers whose `inherited` is `false`, without
  `inherited` and `state`, as it does for attributes and relationships. A node that declares no
  container of its own has no `containers` key in the export.
- `infrahubctl schema format` places `containers` after `uniqueness_constraints` in the node key
  order and `container` as the last key before the trailing `order_weight` of an attribute or a
  relationship. Inside a container item the key order is `name`, `label`, `description`,
  `order_weight`, `collapsed`, `state`.
