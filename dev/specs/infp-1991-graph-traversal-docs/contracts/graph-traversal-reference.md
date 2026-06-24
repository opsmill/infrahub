# Contract: Graph Traversal Reference Content

For a documentation feature, the "contract" is the **API the reference page must describe
exactly**. These values were read from the shipped 1.10.0 backend
(`backend/infrahub/graphql/queries/path.py` and `.../reachable.py`). The reference page
(`docs/docs/graph-traversal/reference.mdx`) MUST match this; re-verify against
`schema/schema.graphql` and the source at authoring time, as defaults/limits may shift between
releases.

> ⚠️ **Spec correction**: the feature spec assumed `max_depth` max = **20** and a single
> `max_paths` default of 10. The shipped code differs (see below). The docs MUST follow the
> code, not the spec's assumed numbers. (SC-002: zero contradictory values.)

> Argument casing is **snake_case** (`source_id`, `destination_id`, `max_depth`, …), confirming
> the release-notes prose over the earlier camelCase example.

> **Authoring constraint**: per `.agents/rules/code-doc-style.md`, the published MDX must NOT
> contain spec-kit FR IDs, ticket IDs (`infp-1991`), or internal class names beyond the public
> GraphQL type/field names. Describe the public contract only.

## Query 1 — `InfrahubPathTraversal`

Paths between two specific objects, shortest first. Only the shortest path through each
intermediate node is returned (longer routes through the same intermediate are omitted).

### Input (`data: PathTraversalInput!`)

| Field | Type | Required | Default | Limit / Notes |
|---|---|---|---|---|
| `source_id` | `String` | yes | — | UUID of the start node |
| `destination_id` | `String` | yes | — | UUID of the end node |
| `max_depth` | `Int` | no | `5` | max **30**; number of node hops |
| `max_paths` | `Int` | no | `10` | max **100**; max paths returned |
| `kind_filter` | `[String!]` | no | — | only traverse through nodes of these kinds |
| `relationship_filter` | `[String!]` | no | — | relationship **schema identifiers** (e.g. `device__interface`), NOT relationship names (e.g. `interfaces`) |
| `excluded_namespaces` | `[String!]` | no | — | unioned with always-excluded set; defaults cannot be opted out |
| `excluded_kinds` | `[String!]` | no | — | unioned with default excluded kinds (`BuiltinIPNamespace` + inheritors) |
| `included_kinds` | `[String!]` | no | — | re-include default-excluded kinds (`BuiltinIPNamespace` + inheritors); no effect on kinds also in `excluded_kinds` |

**Always-excluded namespaces** (cannot be re-included): `Core`, `Internal`, `Builtin`,
`Lineage`, `Profile`, `Template`.

### Result (`PathTraversalResultType`)

- `paths: [PathResultType!]!` — shortest first.
  - `PathResultType.hops: [PathHopType!]!`, `PathResultType.depth: Int!` (edges in this path).
  - `PathHopType.node: PathNodeType!`, `PathHopType.relationship: PathRelationshipType` (null on first hop).
- `source: PathNodeType!`, `destination: PathNodeType!`
- `count: Int!` — total paths discovered.
- `excluded_kinds: [String!]!` — effective exclusions (defaults + requested − included).

`PathNodeType`: `id`, `kind`, `label`, `display_label`, `hfid: [String!]`.
`PathRelationshipType`: `from_rel`, `from_label`, `to_rel`, `to_label`, `kind`.

## Query 2 — `InfrahubReachableNodes`

"What depends on this?" — reachable objects of given kinds from one source, with the path to each.
Used for blast-radius / impact analysis.

### Input (`data: ReachableNodesInput!`)

| Field | Type | Required | Default | Limit / Notes |
|---|---|---|---|---|
| `source_id` | `String` | yes | — | UUID of the source node |
| `target_kinds` | `[String!]` | yes | — | node kinds to search for |
| `max_depth` | `Int` | no | `5` | max **30** |
| `max_results` | `Int` | no | `50` | max **200**; distinct terminal nodes discovered |
| `max_paths` | `Int` | no | `500` | max **5000**; total paths across all terminals |
| `shortest_paths_only` | `Boolean` | no | `true` | true = shortest path(s) per target; false = every path within `max_depth` matching filters |

### Result (`ReachableNodesResultType`)

- `source: PathNodeType!`
- `dependencies: [ReachableNodeType!]!` — one entry per (node, path) pair.
  - `ReachableNodeType.node: PathNodeType!`, `.depth: Int!` (hops from source), `.path: PathResultType!`.
- `count: Int!` — number of dependency entries returned.

## Cross-cutting facts the docs MUST state

- Both queries are **read-only**, **branch- and time-aware**.
- **Permission-safe**: a path crossing an object the user cannot read is dropped entirely, not leaked.
- Available to AI agents over the **MCP server** (same GraphQL queries).

## Worked example (FR-007) — verify field names compile before publishing

```graphql
query {
  InfrahubPathTraversal(data: { source_id: "<uuid-A>", destination_id: "<uuid-B>", max_depth: 5 }) {
    count
    paths {
      depth
      hops {
        node { kind display_label }
        relationship { kind from_rel to_rel }
      }
    }
  }
}
```
