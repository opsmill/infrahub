# Quickstart: IPAM Parent Prefix Lookup

## What This Feature Does

Extends the search anywhere dialog (Cmd+K) to detect IP address and CIDR prefix queries and return all containing parent prefixes in a dedicated "Parent Prefixes" section.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ Frontend: SearchAnywhere component                              │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ SearchActions     │  │ SearchParent │  │ SearchNodes      │  │
│  │ (menu/schema)     │  │ Prefixes NEW │  │ (objects)        │  │
│  └──────────────────┘  └──────┬───────┘  └──────────────────┘  │
│                               │                                 │
└───────────────────────────────┼─────────────────────────────────┘
                                │
                 GraphQL: InfrahubSearchAnywhere
                 (q, limit, partial_match, case_sensitive)
                                │
┌───────────────────────────────┼─────────────────────────────────┐
│ Backend: search_resolver()    │                                 │
│                               ▼                                 │
│  1. UUID check (existing)                                       │
│  2. IPv6 normalization (existing)                               │
│  3. IP/CIDR detection → IPParentPrefixLookupQuery (NEW)         │
│  4. Text search (existing, always runs)                         │
│                                                                 │
│  Response: { edges: [...], parent_prefixes: [...] | null }      │
└─────────────────────────────────────────────────────────────────┘
                                │
                    Neo4j: binary_address matching
                    (existing index on AttributeIPNetwork)
```

## Files Changed

### Backend

| File | Change |
|------|--------|
| `backend/infrahub/graphql/queries/search.py` | Add `parent_prefixes` field to `NodeEdges`, add `_try_parse_ip_or_prefix()` helper, extend `search_resolver()` to detect IP/CIDR and run parent prefix lookup |
| `backend/infrahub/core/query/ipam.py` | Add `IPParentPrefixLookupQuery` class and `IPParentPrefixResult` dataclass |

### Frontend

| File | Change |
|------|--------|
| `frontend/app/src/entities/navigation/api/search.ts` | Add `parent_prefixes` to GraphQL query |
| `frontend/app/src/entities/navigation/domain/search-anywhere.ts` | Add `parentPrefixes` to domain type |
| `frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere.tsx` | Add `SearchParentPrefixes` component |
| `frontend/app/src/entities/navigation/ui/search-anywhere/search-parent-prefixes.tsx` | New component rendering parent prefix results |
| `frontend/app/src/entities/navigation/ui/queries/search-anywhere.query.ts` | Update query options for new field |

### Tests

| File | Change |
|------|--------|
| `backend/tests/unit/graphql/queries/test_search.py` | Unit tests for `_try_parse_ip_or_prefix()` |
| `backend/tests/component/graphql/queries/test_search.py` | Component tests for parent prefix lookup via search resolver |
| `backend/tests/unit/core/query/test_ipam.py` | Unit tests for `IPParentPrefixLookupQuery` result parsing |
| `frontend/app/tests/e2e/search-parent-prefixes.spec.ts` | E2E tests for the full search workflow |

## Key Design Decisions

1. **Single query, dual response**: One GraphQL call returns both text search results (`edges`) and parent prefix results (`parent_prefixes`). No separate API needed.

2. **Reuse existing IPAM query patterns**: `IPParentPrefixLookupQuery` adapts the binary prefix matching from `IPPrefixReconcileQuery._build_possible_parent_prefixes()`.

3. **Reuse existing UI components**: Parent prefix results use the same `NodesOptions` component as regular search results (satisfies FR-008).

4. **No schema changes**: Operates on existing `BuiltinIPPrefix`, `AttributeIPNetwork`, and `BuiltinIPNamespace` nodes with existing indexes.

5. **Additive only**: Non-IP queries return `parent_prefixes: null` and follow the exact same code path as before (FR-010, FR-012).
