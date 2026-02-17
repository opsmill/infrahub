# GraphQL Contract: InfrahubSearchAnywhere (Extended)

## Current Schema (Unchanged fields)

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

## Updated Response Type

```graphql
type NodeEdges {
  count: Int!
  edges: [NodeEdge!]!
  is_prefix_lookup: Boolean  # NEW
}

type NodeEdge {
  node: Node!
}

type Node {
  id: String!
  kind: String!
}
```

### New Field: `is_prefix_lookup`

- **Type**: `Boolean` (nullable, defaults to null/false for backward compatibility)
- **Description**: When `true`, indicates the search detected a valid IP address or CIDR prefix and returned parent prefix containment results instead of text search results.
- **Behavior**:
  - `null` or `false`: Standard text search results
  - `true`: Results are IP prefixes containing the searched address/prefix, ordered by specificity (most specific first)

## Behavior by Input Type

| Input Example | Detected As | Query Executed | `is_prefix_lookup` |
|---------------|-------------|----------------|---------------------|
| `10.1.2.45` | IPv4 address | Parent prefix lookup | `true` |
| `10.1.2.0/24` | IPv4 prefix | Parent prefix lookup | `true` |
| `2001:db8::1` | IPv6 address | Parent prefix lookup | `true` |
| `2001:db8::/32` | IPv6 prefix | Parent prefix lookup | `true` |
| `10.1.2` | Partial (not valid IP) | Text search | `null` |
| `router-core-01` | Text | Text search | `null` |
| `abc123-uuid` | UUID | UUID lookup | `null` |

## Example Queries

### IP Address Search (New Behavior)

```graphql
query Search($search: String!) {
  InfrahubSearchAnywhere(q: $search, limit: 4, partial_match: true) {
    count
    is_prefix_lookup
    edges {
      node {
        id
        kind
      }
    }
  }
}
```

**Variables**: `{"search": "10.1.2.45"}`

**Response**:
```json
{
  "data": {
    "InfrahubSearchAnywhere": {
      "count": 3,
      "is_prefix_lookup": true,
      "edges": [
        {"node": {"id": "uuid-1", "kind": "BuiltinIPPrefix"}},
        {"node": {"id": "uuid-2", "kind": "BuiltinIPPrefix"}},
        {"node": {"id": "uuid-3", "kind": "BuiltinIPPrefix"}}
      ]
    }
  }
}
```

### Text Search (Unchanged Behavior)

**Variables**: `{"search": "router-core-01"}`

**Response**:
```json
{
  "data": {
    "InfrahubSearchAnywhere": {
      "count": 2,
      "is_prefix_lookup": null,
      "edges": [
        {"node": {"id": "uuid-a", "kind": "InfraDevice"}},
        {"node": {"id": "uuid-b", "kind": "InfraInterface"}}
      ]
    }
  }
}
```

## Backward Compatibility

- The `is_prefix_lookup` field is nullable and defaults to `null` for non-IP searches.
- Existing clients that don't query `is_prefix_lookup` will continue to work without changes.
- The `limit` parameter still applies to prefix lookup results.
- The `partial_match` and `case_sensitive` parameters are ignored for prefix lookups (containment is an exact binary match).
