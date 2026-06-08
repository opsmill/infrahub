# Research: IPAM Parent Prefix Lookup

## R-001: How does the existing search resolver work?

**Decision**: Extend the existing `search_resolver()` in `backend/infrahub/graphql/queries/search.py` with an IP/CIDR detection step that runs a new `IPParentPrefixLookupQuery` alongside the existing text search.

**Rationale**: The resolver already has a sequential pattern: UUID check → IPv6 normalization → text search. Adding IP detection between IPv6 normalization and text search fits naturally. The resolver returns `NodeEdges` (count + edges), which needs a new field to distinguish parent prefix results from text results.

**Alternatives considered**:
- **Separate GraphQL query** (e.g., `InfrahubSearchParentPrefixes`): Would require two parallel API calls from the frontend and complicate result coordination. Rejected because the feature is tightly coupled to the search workflow.
- **REST endpoint**: Would break the GraphQL-first pattern used by all other search features. Rejected.

## R-002: How to detect valid IP/CIDR input in the search query?

**Decision**: Use Python's `ipaddress` module: try `ipaddress.ip_address(q)` first, then `ipaddress.ip_network(q, strict=False)`. If either succeeds, treat it as an IP/CIDR query.

**Rationale**: The `ipaddress` module is already imported in `search.py` and used for IPv6 normalization. `strict=False` allows inputs like `10.1.2.45/24` (host bits set) to be accepted as `10.1.2.0/24`. Both IPv4 and IPv6 are handled natively. Partial IPs like `10.1.2` will fail parsing and correctly fall through to text search.

**Alternatives considered**:
- **Regex-based detection**: More error-prone, requires maintaining patterns for IPv4, IPv6, CIDR notation. Rejected because `ipaddress` module is the stdlib solution.
- **Third-party library (netaddr, etc.)**: Unnecessary when stdlib covers all cases. Rejected per constitution Principle VII.

## R-003: How to query parent prefixes efficiently in Neo4j?

**Decision**: Create a new `IPParentPrefixLookupQuery` class that adapts the existing `_build_possible_parent_prefixes()` algorithm from `IPPrefixReconcileQuery`. Generate all possible parent prefix binary addresses (progressively shorter), then match against `AttributeIPNetwork` nodes using the `binary_address IN $possible_prefix_list` pattern with `prefixlen` filtering.

**Rationale**: The reconcile query already solves the same containment problem. The binary address approach with `STARTS WITH` / `IN` matching leverages the existing Neo4j index on `binary_address`. This avoids full table scans.

**Alternatives considered**:
- **`STARTS WITH` on single binary**: Would match all prefixes whose network address starts with the input's binary, but doesn't correctly handle prefix length constraints. Rejected.
- **Traversing the `parent__child` hierarchy**: The hierarchy stores only direct parent, not all ancestors. Would require recursive traversal. Rejected because it's less efficient and the hierarchy may not be fully reconciled for non-existent IPs.

## R-004: How to handle namespace filtering for parent prefix lookup?

**Decision**: Search across ALL namespaces by default (no namespace filter). Return the namespace ID with each result so the frontend can display it.

**Rationale**: The spec requires results from all namespaces (FR-002, FR-004, acceptance scenario 4). The reconcile query uses a single namespace because it operates within a known context, but search doesn't have that constraint. The query joins through the `ip_namespace__ip_prefix` relationship to get the namespace for each result.

**Alternatives considered**:
- **Filter to default namespace**: Would miss prefixes in other namespaces. Rejected per spec FR-002.
- **Add namespace filter parameter**: Adds complexity without spec justification. Rejected per YAGNI (Principle VII).

## R-005: How to return parent prefix results alongside text search results?

**Decision**: Add a new `parent_prefixes` field to the `NodeEdges` GraphQL type, containing a list of `NodeEdge` objects. The existing `edges` field continues to hold text search results. When an IP/CIDR is detected, run BOTH the parent prefix lookup AND the normal text search so that exact-match IP objects appear in regular results (FR-013).

**Rationale**: Using a separate field (rather than mixing into `edges`) lets the frontend render a distinct "Parent Prefixes" section (FR-008) without client-side filtering. Running both queries ensures existing IP objects are found by text search (FR-013) while parent prefixes are clearly separated.

**Alternatives considered**:
- **Single `edges` list with a `result_type` discriminator**: Would require the frontend to filter and group results. More complex for the consumer. Rejected.
- **Boolean `is_prefix_lookup` flag on `NodeEdges`**: Simpler but doesn't allow simultaneous text + prefix results as required by FR-012/FR-013. Rejected.

## R-006: Frontend approach for the "Parent Prefixes" section

**Decision**: Create a new `SearchParentPrefixes` component following the same pattern as `SearchNodes`. It reads the `parent_prefixes` field from the search response and renders each result using the existing `NodesOptions` component (which already handles IP prefix display with namespace badges). Add the component to `search-anywhere.tsx` between `SearchActions` and `SearchNodes`.

**Rationale**: Reusing `NodesOptions` satisfies FR-008's requirement that parent prefix results use the same format as regular search results. The `SearchAnywhereGroup` component already supports named sections with headings. Placing "Parent Prefixes" before "Objects" gives it visual priority for IP searches.

**Alternatives considered**:
- **New custom result component**: Would duplicate rendering logic and risk visual inconsistency. Rejected per FR-008.
- **Merge into `SearchNodes` with conditional grouping**: Would make the component too complex and harder to maintain. Rejected per Principle VII.

## R-007: How to handle the "no cap" on parent prefix results?

**Decision**: The parent prefix lookup returns all matching prefixes without a limit parameter. For a typical /24 in a /8, this means at most 24 results (IPv4) or 128 (IPv6). The frontend renders all of them since the result count is bounded by prefix depth.

**Rationale**: The spec explicitly states "no cap on result count" (FR-002). The mathematical maximum is 32 for IPv4 and 128 for IPv6, which is bounded and manageable. In practice, most deployments have 3-5 levels of hierarchy.

**Alternatives considered**:
- **Frontend pagination/virtualization**: Overkill for at most 32/128 items. Rejected.
- **Backend limit parameter**: Contradicts spec. Rejected.

## R-008: Branch context handling

**Decision**: The `IPParentPrefixLookupQuery` uses the same `branch.get_query_filter_path()` mechanism as all other IPAM queries. The branch and temporal context are already available via `GraphqlContext`.

**Rationale**: All existing queries in `ipam.py` use this pattern. The search resolver already receives branch context from the GraphQL context. No additional work needed beyond following the established pattern (FR-011).
