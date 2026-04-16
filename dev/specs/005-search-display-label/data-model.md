# Data Model: Search Anywhere Display Label Enrichment

## Entity Changes

### SearchResult (GraphQL `Node` type in search.py)

Current fields:
- `id` (String, required) — node UUID
- `kind` (String, required) — node kind (e.g., "InfraDevice", "SchemaNode")

New fields:
- `display_label` (String, nullable) — human-readable label for the node

### Behavioral Rules

1. `display_label` is populated for UUID-based searches where the node is found.
2. `display_label` is null/omitted for text-based search results (those use the existing `useGetObject` fetch path).
3. No database schema changes. `display_label` is computed at query time from existing node data.
4. No new entities or relationships are introduced.

### Frontend Domain Type

Current:
```
ObjectResult = { id: string; kind: string }
```

New:
```
ObjectResult = { id: string; kind: string; display_label?: string | null }
```
