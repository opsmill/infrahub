# GraphQL Contract: Search Anywhere with Parent Prefix Lookup

## Modified Types

### NodeEdges (extended)

```graphql
type NodeEdges {
  count: Int!                              # Existing: count of text search results
  edges: [NodeEdge!]!                      # Existing: text search results
  parent_prefixes: [NodeEdge!]             # NEW: parent prefix results (null when query is not IP/CIDR)
}
```

**Breaking change**: None. `parent_prefixes` is nullable and additive.

### NodeEdge / Node (unchanged)

```graphql
type NodeEdge {
  node: Node!
}

type Node {
  id: String!
  kind: String!
}
```

## Query

### InfrahubSearchAnywhere (unchanged signature)

```graphql
type Query {
  InfrahubSearchAnywhere(
    q: String!
    limit: Int
    partial_match: Boolean
    case_sensitive: Boolean
  ): NodeEdges!
}
```

No new parameters. IP/CIDR detection is automatic based on the `q` value.

## Behavior Changes

### When `q` is a valid IP address or CIDR prefix

1. `parent_prefixes` is populated with all containing parent prefixes, ordered by prefix length DESC (most specific first), across all namespaces.
2. `edges` and `count` continue to reflect text search results (which may include exact-match IP/prefix objects per FR-013).
3. When `q` is a prefix in CIDR notation and the exact prefix exists, it appears in `edges` (via text search), NOT in `parent_prefixes`.

### When `q` is NOT a valid IP address or CIDR prefix

1. `parent_prefixes` is `null`.
2. `edges` and `count` reflect text search results (existing behavior, unchanged).

## Example Queries

### IP Address Search (User Story 1)

```graphql
query {
  InfrahubSearchAnywhere(q: "10.1.2.45", limit: 4) {
    count
    edges {
      node { id kind }
    }
    parent_prefixes {
      node { id kind }
    }
  }
}
```

**Response** (prefixes 10.0.0.0/8, 10.1.0.0/16, 10.1.2.0/24 exist):
```json
{
  "data": {
    "InfrahubSearchAnywhere": {
      "count": 1,
      "edges": [
        { "node": { "id": "uuid-ip-addr-45", "kind": "BuiltinIPAddress" } }
      ],
      "parent_prefixes": [
        { "node": { "id": "uuid-prefix-24", "kind": "BuiltinIPPrefix" } },
        { "node": { "id": "uuid-prefix-16", "kind": "BuiltinIPPrefix" } },
        { "node": { "id": "uuid-prefix-8", "kind": "BuiltinIPPrefix" } }
      ]
    }
  }
}
```

### Prefix Search (User Story 2)

```graphql
query {
  InfrahubSearchAnywhere(q: "10.1.2.0/24", limit: 4) {
    count
    edges {
      node { id kind }
    }
    parent_prefixes {
      node { id kind }
    }
  }
}
```

**Response**:
```json
{
  "data": {
    "InfrahubSearchAnywhere": {
      "count": 1,
      "edges": [
        { "node": { "id": "uuid-prefix-24", "kind": "BuiltinIPPrefix" } }
      ],
      "parent_prefixes": [
        { "node": { "id": "uuid-prefix-16", "kind": "BuiltinIPPrefix" } },
        { "node": { "id": "uuid-prefix-8", "kind": "BuiltinIPPrefix" } }
      ]
    }
  }
}
```

### Non-IP Search (User Story 3)

```graphql
query {
  InfrahubSearchAnywhere(q: "router-core-01", limit: 4) {
    count
    edges {
      node { id kind }
    }
    parent_prefixes {
      node { id kind }
    }
  }
}
```

**Response**:
```json
{
  "data": {
    "InfrahubSearchAnywhere": {
      "count": 2,
      "edges": [
        { "node": { "id": "uuid-device-1", "kind": "InfraDevice" } },
        { "node": { "id": "uuid-intf-1", "kind": "InfraInterface" } }
      ],
      "parent_prefixes": null
    }
  }
}
```
