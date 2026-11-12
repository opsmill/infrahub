# Contract: containers in the schema REST API

Applies to `GET /api/schema`, `GET /api/schema/{kind}` and `POST /api/schema/load`. The GraphQL
schema and queries do not change. Examples use the LAG interface; keys this feature does not touch
are left out.

## What GET /api/schema and GET /api/schema/{kind} return

- Nodes, generics, profiles and templates carry `containers`: a list of
  `{name, label, description, order_weight, collapsible, collapsed, state, inherited}` items, `[]`
  when none.
  `state` is `present` on every item a read returns.
- On a node, the list is the result of inheritance: the inherited containers first, in the order
  of the generics in `inherit_from` and of each generic's list, then the node's own containers. A
  node container with the same name as an inherited one takes its position.
- `inherited` is `true` on a copy taken from a generic and `false` on a container the kind
  declares. Profiles and templates return the containers of their node with `inherited: false`.
  A profile also returns, first,
  `{"name": "builtin_profile", "label": "Profile", "description": null, "order_weight": -100, "collapsible": false, "collapsed": false, "state": "present", "inherited": false}`,
  and its `profile_name` and `profile_priority` attributes have `"container": "builtin_profile"`.
  A template, generated for a node or for a generic, also returns, first,
  `{"name": "builtin_template", "label": "Template", "description": null, "order_weight": -100, "collapsible": false, "collapsed": false, "state": "present", "inherited": false}`,
  and its `template_name` attribute has `"container": "builtin_template"`.
- `details` is never listed. A container named `advanced` is listed like any other container.
- Attributes and relationships carry `container`: the container name, or `null` for the Details
  section.
- Clients place Details at order weight 0: the containers with a negative `order_weight` come
  before Details, and the others after it. On each side, clients order by `order_weight`, and the
  items without a weight come last, in list order.
- Both fields are returned on every branch, with the values stored on that branch.

Example `GET /api/schema/InfraLagInterface` (abridged):

```json
{
  "kind": "InfraLagInterface",
  "containers": [
    {"name": "lacp", "label": "LACP", "description": "Link aggregation settings", "order_weight": 100, "collapsible": true, "collapsed": false, "state": "present", "inherited": false},
    {"name": "layer2", "label": "Layer 2", "description": "Switching settings of the bundle", "order_weight": 200, "collapsible": true, "collapsed": false, "state": "present", "inherited": false},
    {"name": "layer3", "label": "Layer 3", "description": "Addressing and MTU", "order_weight": 300, "collapsible": true, "collapsed": true, "state": "present", "inherited": false}
  ],
  "attributes": [
    {"name": "lacp", "kind": "Text", "container": "lacp"},
    {"name": "minimum_links", "kind": "Number", "container": "lacp"},
    {"name": "max_bundle", "kind": "Number", "container": null}
  ],
  "relationships": [
    {"name": "mlag", "peer": "InfraMlagInterface", "container": "lacp"}
  ]
}
```

`GET /api/schema/InfraLagInterfaceL2` returns the same three containers with `inherited: true`.
A kind without sections returns `"containers": []` and `"container": null` on every field.

## What POST /api/schema/load accepts

- `containers` on a node or generic: items with a required `name` and `label` and an optional
  `description`, `order_weight`, `collapsible`, `collapsed` and `state`. `"state": "absent"`
  removes the item. `collapsible` defaults to `true`.
  `inherited` is read-only: a load that sends it gets the warning
  `'containers.inherited' is a read-only field, the submitted value is ignored`. An unknown key
  inside an item fails the write contract with a 422.
- `container` on an attribute or relationship: a string or `null`. On a reload, leaving it out or
  sending `null` keeps the stored value, and `""` moves the field back to Details.
- A load that only changes containers or assignments reports no migration and no constraint
  check.
- A load that leaves a container out of the list keeps it.
- A load that only reorders containers is a schema change and stores the new order. A branch merge
  where both branches reorder the same kind's containers differently reports a conflict on
  `containers`.

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
            {"name": "lacp", "kind": "Text", "container": "lacp"},
            {"name": "max_bundle", "kind": "Number", "optional": true}
          ]
        }
      ]
    }
  ]
}
```

## Rejected loads

Each rejection is a 422 with the body
`{"data": null, "errors": [{"message": "<message>", "extensions": {"code": 422}}]}`:

- A field references a container the kind does not have after inheritance, `details`,
  `advanced` on a kind without a container of that name, or `builtin_profile` or
  `builtin_template` on a node or generic:
  `InfraLagInterfaceL2.attributes.mtu.container: container 'layer4' is not declared on InfraLagInterfaceL2`.
  A relationship gives `relationships.<name>.container`. For a field declared on a generic, the
  message names the generic.
- A kind declares the same container name twice:
  `InfraLagInterface.containers: container names must be unique, duplicate 'lacp'`.
- A container is named `details`:
  `InfraLagInterface.containers: 'details' is a built-in container and cannot be declared`.
- A container name starts with `builtin_`:
  `InfraLagInterface.containers: 'builtin_x' starts with the reserved prefix 'builtin_' and cannot be declared`.
- A container sets `collapsed: true` with `collapsible: false`:
  `InfraLagInterface.containers.summary: collapsed requires collapsible`.

A container item without `label`, or with a `name` outside the attribute name rules, fails the
write contract's Pydantic validation with the standard FastAPI `detail` body, before the validator
runs.

## SDK

- `infrahub_sdk.schema.generated` gains `ContainerSchemaRead` (with `inherited`) and
  `ContainerSchemaWrite`; the node, attribute and relationship models gain `containers` and
  `container`, so offline validation accepts both. `infrahub_sdk.schema.main` exports both
  container models.
- `infrahubctl schema export` writes only the containers whose `inherited` is `false`, without
  `inherited` and `state`. A kind without its own containers has no `containers` key.
- `infrahubctl schema format` places `containers` after `uniqueness_constraints` and `container`
  last before the trailing `order_weight` of an attribute or relationship. Container item keys are
  ordered `name`, `label`, `description`, `order_weight`, `collapsible`, `collapsed`, `state`.
