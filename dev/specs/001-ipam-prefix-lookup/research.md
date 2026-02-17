# Research: IPAM Parent Prefix Lookup

## R1: Backend Search Architecture

### Decision
Extend the existing `search_resolver` in `backend/infrahub/graphql/queries/search.py` to detect IP/prefix input and route to a new parent prefix lookup query.

### Rationale
The current resolver already has IP-awareness (`_collapse_ipv6` function) and handles query routing (UUID vs text). Adding IP detection here keeps the routing logic centralized. The existing GraphQL schema (`InfrahubSearchAnywhere`) can be extended with minimal changes.

### Alternatives Considered
- **Separate GraphQL query**: Would require a new frontend API call and duplicate context handling (branch, at-date). Rejected because the spec requires IP detection to replace text search seamlessly.
- **Frontend-only detection with separate API**: More complex wiring, harder to keep detection logic consistent between frontend and backend.

### Key Files
- `backend/infrahub/graphql/queries/search.py` — `search_resolver()`, `InfrahubSearchAnywhere` field
- `backend/infrahub/core/query/ipam.py` — Existing IPAM query patterns
- `backend/infrahub/core/utils.py` — `convert_ip_to_binary_str()`

## R2: Parent Prefix Containment Query Pattern

### Decision
Use the `possible_prefix_list` pattern from `IPPrefixReconcileQuery` to find all parent prefixes for a given IP address or prefix. This works by generating all possible binary address prefixes from prefix length N down to 0, then matching against `AttributeIPNetwork.binary_address`.

### Rationale
This pattern is already proven in production for the reconciliation flow. It leverages the existing RANGE index on `AttributeIPNetwork(binary_address)` via `av.binary_address IN $possible_prefix_list`. Unlike `STARTS WITH`, which finds children, the inverted pattern finds parents.

### Key Pattern
```
For IP 10.1.2.45 (binary: 00001010000000010000001000101101):
  - Possible parent at /32: 00001010000000010000001000101101
  - Possible parent at /31: 0000101000000001000000100010110x → 00001010000000010000001000101100
  - Possible parent at /24: 000010100000000100000010xxxxxxxx → 00001010000000010000001000000000
  - ... down to /0
Match AttributeIPNetwork where binary_address IN [list] AND prefixlen <= corresponding_length
```

### Alternatives Considered
- **STARTS WITH on binary prefix**: Only finds children, not parents. Would need to iterate multiple queries.
- **Python-side filtering**: Would require loading all prefixes into memory. Not scalable.

## R3: Cross-Namespace Lookup

### Decision
Query ALL IP namespaces simultaneously instead of requiring a namespace parameter. Return prefixes from all namespaces, each labeled with their namespace info.

### Rationale
The spec requires results across all namespaces (FR-002). The existing IPAM queries scope to a single namespace via `_get_namespace_id()`. The new query must omit the namespace filter in the initial MATCH or iterate all namespaces. Since namespaces are few (typically <10), matching all is efficient.

### Key Insight
The existing reconcile query starts with `MATCH (ip_namespace {uuid: $namespace_id})`. The new query should instead start with `MATCH (ip_namespace:BuiltinIPNamespace)` (no UUID filter) to get all namespaces, then use the same prefix containment pattern per namespace.

## R4: Frontend Integration Approach

### Decision
Add IP detection on the frontend to conditionally render a "Parent Prefixes" `SearchAnywhereGroup` component instead of the "Objects" group when an IP is detected. Also add a response field `is_prefix_lookup` to the GraphQL response so the frontend knows which result type was returned.

### Rationale
The frontend already uses `cmdk` with `shouldFilter={false}` (server-side filtering). The component architecture with separate `SearchNodes`, `SearchActions`, `SearchDocs` makes it natural to add a `SearchParentPrefixes` component that conditionally replaces `SearchNodes`.

### Key Files
- `frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere.tsx` — Main component, renders sections
- `frontend/app/src/entities/navigation/ui/search-anywhere/search-nodes.tsx` — Object results
- `frontend/app/src/entities/navigation/api/search.ts` — GraphQL query
- `frontend/app/src/entities/navigation/domain/search-anywhere.ts` — Domain types

## R5: Binary Address Storage Format

### Decision
Reuse the existing `convert_ip_to_binary_str()` utility and the binary address format already stored in Neo4j.

### Details
- **IPv4**: 32-bit binary string (e.g., `00001010000000010000001000101101` for 10.1.2.45)
- **IPv6**: 128-bit binary string
- **AttributeIPNetwork properties**: `binary_address` (str), `version` (int), `prefixlen` (int), `value` (str)
- **Indexes**: RANGE indexes on `AttributeIPNetwork(binary_address)` and `AttributeIPHost(binary_address)` in `backend/infrahub/core/graph/index.py`

## R6: Branch and Temporal Filtering

### Decision
Use `branch.get_query_filter_path()` consistent with all existing IPAM queries. The search resolver already receives branch/at context via `graphql_context.branch` and `graphql_context.at`.

### Rationale
This is the standard pattern used by `IPPrefixReconcileQuery`, `IPPrefixSubnetFetch`, and all other branch-aware queries. No custom implementation needed.
