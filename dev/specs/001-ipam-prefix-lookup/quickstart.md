# Quickstart: IPAM Parent Prefix Lookup

## Overview

This feature enhances the "search anywhere" (Cmd+K) dialog to detect IP address/prefix searches and return containing parent prefixes using binary address matching.

## Architecture

```
┌─────────────────┐     ┌───────────────────────────┐     ┌──────────────────┐
│  Frontend       │     │  Backend                  │     │  Neo4j           │
│                 │     │                           │     │                  │
│  SearchAnywhere │────▶│  search_resolver()        │────▶│  AttributeIP-    │
│  (Cmd+K dialog) │     │    ↓ detect IP input      │     │  Network nodes   │
│                 │     │    ↓ parse with ipaddress │     │  (binary_address │
│  SearchNodes    │     │    ↓ IF valid IP/prefix:  │     │   RANGE index)   │
│  OR             │◀────│      run prefix lookup    │◀────│                  │
│  SearchPrefixes │     │    ↓ ELSE:                │     │                  │
│  (new section)  │     │      run text search      │     │                  │
└─────────────────┘     └───────────────────────────┘     └──────────────────┘
```

## Key Files to Modify

### Backend
| File | Change |
|------|--------|
| `backend/infrahub/graphql/queries/search.py` | Add IP detection logic + prefix lookup in `search_resolver()`, add `is_prefix_lookup` field to `NodeEdges` |
| `backend/infrahub/core/query/ipam.py` | New `IPParentPrefixLookupQuery` class |

### Frontend
| File | Change |
|------|--------|
| `frontend/app/src/entities/navigation/api/search.ts` | Add `is_prefix_lookup` to GraphQL query |
| `frontend/app/src/entities/navigation/domain/search-anywhere.ts` | Add `isPrefixLookup` to domain type |
| `frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere.tsx` | Conditionally render `SearchPrefixes` vs `SearchNodes` |
| `frontend/app/src/entities/navigation/ui/search-anywhere/search-prefixes.tsx` | New component for parent prefix results |

## Development Flow

1. **Start with the query**: Create `IPParentPrefixLookupQuery` in `ipam.py` — this is the core algorithm
2. **Wire into resolver**: Modify `search_resolver` to detect IP input and call the new query
3. **Add unit tests**: Test IP detection, binary address generation, query results
4. **Update frontend**: Add `is_prefix_lookup` to GraphQL query, create `SearchPrefixes` component
5. **Add E2E tests**: Test the full flow in the search dialog

## Relevant Existing Code

- `convert_ip_to_binary_str()` in `backend/infrahub/core/utils.py` — Converts IP to binary string
- `IPPrefixReconcileQuery` in `backend/infrahub/core/query/ipam.py` — Uses `possible_prefix_list` pattern for parent lookup
- `_collapse_ipv6()` in `backend/infrahub/graphql/queries/search.py` — Already normalizes IPv6 input
- `IP_PREFIX_GENERIC`, `IP_ADDRESS_GENERIC` in `frontend/app/src/entities/ipam/constants.ts` — Frontend IP kind detection
