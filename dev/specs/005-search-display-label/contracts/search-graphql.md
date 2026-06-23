# Contract: InfrahubSearchAnywhere GraphQL API

## Schema Change

### Before

```graphql
type SearchNode {
  id: String!
  kind: String!
}
```

### After

```graphql
type SearchNode {
  id: String!
  kind: String!
  display_label: String
}
```

## Query

```graphql
query Search($search: String!, $caseSensitive: Boolean) {
  InfrahubSearchAnywhere(q: $search, limit: 4, partial_match: true, case_sensitive: $caseSensitive) {
    count
    edges {
      node {
        id
        kind
        display_label
      }
    }
  }
}
```

## Behavior

### UUID Search

| Input | Node namespace | Returns | display_label |
| ----- | -------------- | ------- | ------------- |
| Valid UUID | Regular (e.g., Infra, Core) | Result with id, kind | Computed from node |
| Valid UUID | Schema | Result with id, kind | Computed from node |
| Valid UUID | Internal | Result with id, kind | Computed from node |
| Valid UUID | Not found | Empty results | N/A |

### Text Search (unchanged)

| Input | Returns | display_label |
| ----- | ------- | ------------- |
| Any text | Matching Node/GenericGroup results | null |

## Backward Compatibility

- The `display_label` field is nullable and additive — existing clients that don't request it are unaffected.
- The GraphQL query is opt-in: clients must add `display_label` to their selection set to receive it.
