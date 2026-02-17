# Tasks: IPAM Parent Prefix Lookup

**Input**: Design documents from `/specs/001-ipam-prefix-lookup/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/graphql-search.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Foundational (Backend Core)

**Purpose**: Core backend infrastructure shared by all user stories. MUST be complete before any story-specific work begins.

- [X] T001 [P] Create `IPParentPrefixLookupQuery` class with frozen dataclass `IPParentPrefixResult` in `backend/infrahub/core/query/ipam.py`. The query accepts an `ipaddress.IPv4Address | IPv6Address | IPv4Network | IPv6Network` value and finds all containing prefixes across all namespaces using the `possible_prefix_list` containment pattern from `IPPrefixReconcileQuery`. Must use `branch.get_query_filter_path()` for branch/temporal filtering. Return results ordered by `prefixlen DESC` (most specific first). Each result includes prefix UUID, prefix value, prefix length, namespace UUID. Reference the Cypher pattern in `research.md` R2 and the existing `IPPrefixReconcileQuery` `get_new_parent_query` section (line ~1190 of ipam.py). Key difference from existing queries: match ALL `BuiltinIPNamespace` nodes (no namespace UUID filter) per research.md R3.
- [X] T002 [P] Add `is_prefix_lookup` Boolean field to the `NodeEdges` GraphQL ObjectType in `backend/infrahub/graphql/queries/search.py`. Use `graphene.Boolean(required=False)` so it defaults to `None` for backward compatibility.
- [X] T003 [P] Add IP/prefix detection helper function `_try_parse_ip_or_prefix(q: str)` in `backend/infrahub/graphql/queries/search.py`. It should attempt to parse the input using `ipaddress.ip_address()` first, then `ipaddress.ip_network(strict=False)`. Return the parsed object on success or `None` on failure. Must handle both IPv4 and IPv6. The existing `_collapse_ipv6()` already runs before this function for IPv6 normalization.
- [X] T004 Wire IP detection into `search_resolver()` in `backend/infrahub/graphql/queries/search.py`. After the UUID check and IPv6 collapse, call `_try_parse_ip_or_prefix()`. If it returns a valid IP/prefix, instantiate and execute `IPParentPrefixLookupQuery`, build results as `{id, kind}` pairs from the query output, and set `is_prefix_lookup=True` in the response. If it returns `None`, fall through to existing text search logic unchanged. The `is_prefix_lookup` field should be included in the response dict when requested via `fields`.

**Checkpoint**: Backend API now returns parent prefixes when given a valid IP address or CIDR prefix. Testable via GraphQL playground.

---

## Phase 2: User Story 1 - Find Parent Prefix for a New IP Address (Priority: P1) MVP

**Goal**: A network engineer types a full IP address (e.g., "10.1.2.45") in search anywhere and sees all containing parent prefixes ordered by specificity, with namespace context.

**Independent Test**: Search for any valid IPv4/IPv6 address in the Cmd+K dialog and verify containing prefixes appear in a "Parent Prefixes" section.

### Implementation for User Story 1

- [X] T005 [US1] Regenerate GraphQL schema and frontend types by running `uv run invoke backend.generate` then `cd frontend/app && npm run codegen` to pick up the new `is_prefix_lookup` field on `NodeEdges`.
- [X] T006 [P] [US1] Update GraphQL query to include `is_prefix_lookup` field in `frontend/app/src/entities/navigation/api/search.ts`. Add `is_prefix_lookup` to the `SEARCH` gql.tada query selection set inside the `InfrahubSearchAnywhere` block, after `count`.
- [X] T007 [P] [US1] Add `isPrefixLookup` boolean to domain types in `frontend/app/src/entities/navigation/domain/search-anywhere.ts`. Update the `SearchAnywhere` return type to include `isPrefixLookup: boolean` and update the `searchAnywhere` function to extract and pass through the `isPrefixLookup` field (mapped from `is_prefix_lookup`) from the API response.
- [X] T008 [US1] Update `useGetSearchAnywhere` hook to expose `isPrefixLookup` in `frontend/app/src/entities/navigation/domain/search-anywhere.query.ts`. Ensure the query result includes the new field so consuming components can read it.
- [X] T009 [US1] Create `SearchPrefixes` component in `frontend/app/src/entities/navigation/ui/search-anywhere/search-prefixes.tsx`. This component renders a `SearchAnywhereGroup` with heading "Parent Prefixes". It reads the search query from `useCommandState`, debounces it (300ms, same as `SearchNodes`), and calls `useGetSearchAnywhere`. For each result, fetch full object details using `useGetObject` (same pattern as `NodesOptions` in `search-nodes.tsx`), display the prefix value, namespace badge, and schema label. Use `SearchAnywhereItem` with `getObjectDetailsUrl()` for navigation. Show IP Namespace column for each result. Use the same `SearchResultNodeSkeleton` loading pattern as `SearchNodes`. Handle empty/error/loading states consistently with `SearchNodes`.
- [X] T010 [US1] Wire conditional rendering in `frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere.tsx`. Import `SearchPrefixes`. The `SearchNodes` component must be updated to check `isPrefixLookup` from its query data and return `null` when true (so `SearchPrefixes` takes over). `SearchPrefixes` should check `isPrefixLookup` and return `null` when false/null. Add `SearchPrefixes` to the `Command.List` alongside `SearchNodes`. When `isPrefixLookup` is true, `SearchActions` and `SearchDocs` should be hidden (IP lookup replaces text search entirely per FR-001).

**Checkpoint**: User Story 1 fully functional. Typing a valid IP address in Cmd+K shows parent prefixes in a dedicated section. Text search still works for non-IP queries.

---

## Phase 3: User Story 2 - Find Parent Prefix for a Known Prefix (Priority: P2)

**Goal**: A network engineer types a prefix in CIDR notation (e.g., "10.1.2.0/24") and sees both the exact match and containing parent prefixes.

**Independent Test**: Search for a known CIDR prefix and verify the exact match plus parent prefixes appear.

### Implementation for User Story 2

- [X] T011 [US2] Visually distinguish exact matches from parent prefixes in `frontend/app/src/entities/navigation/ui/search-anywhere/search-prefixes.tsx`. The `SearchPrefixes` component should pass the original search query string down to each result item. If the searched prefix matches a result exactly (compare fetched prefix value with search input using `ipaddress`-style normalization or string comparison), add a subtle visual indicator such as a `Badge` with text "Exact match" to help users identify it among the parent results.

**Checkpoint**: Prefix search works alongside IP address search. Both go through the same lookup path. Exact matches are visually distinguished.

---

## Phase 4: User Story 3 - Partial IP Falls Back to Text Search (Priority: P2)

**Goal**: Partial IPs (e.g., "10.1.2") and non-IP text continue to use regular text search with no behavior change.

**Independent Test**: Type partial IP strings and non-IP text and verify existing search results appear unchanged.

**No implementation tasks**: Backward compatibility is built into the foundational logic. The `_try_parse_ip_or_prefix()` function (T003) returns `None` for partial IPs, hostnames, and general text, which causes `search_resolver` (T004) to fall through to the existing text search path unchanged.

**Checkpoint**: Backward compatibility verified. No regressions in existing search behavior.

---

## Phase 5: User Story 4 - Navigate from Search Result to Create IP Address (Priority: P3)

**Goal**: Clicking a parent prefix result navigates to the prefix detail page where the user can create a new IP address.

**Independent Test**: Click a prefix result in the search dialog and verify navigation to the correct prefix detail page.

**No implementation tasks**: Navigation is handled by `SearchAnywhereItem` with `getObjectDetailsUrl()` already wired in T009. The existing prefix detail page supports IP address creation. No additional code needed.

**Checkpoint**: End-to-end workflow complete. User can search, find, and navigate to parent prefixes.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final quality, formatting, and documentation tasks.

- [X] T012 Add Towncrier changelog fragment in `changelog/` describing the new parent prefix lookup feature in search anywhere.
- [X] T013 Run formatters and linters: `uv run invoke format` and `uv run invoke lint` for backend; `cd frontend/app && npm run biome:fix` for frontend. Fix any issues.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies - can start immediately. BLOCKS all user stories.
- **User Story 1 (Phase 2)**: Depends on Foundational completion. This is the MVP.
- **User Story 2 (Phase 3)**: Depends on US1 completion (T011 modifies the `SearchPrefixes` component created in T009).
- **User Story 3 (Phase 4)**: No implementation - verified by foundational logic.
- **User Story 4 (Phase 5)**: No implementation - verified by US1 navigation.
- **Polish (Phase 6)**: Depends on all stories being complete.

### Within Each Phase

**Foundational phase**:
- T001 (ipam.py), T002 (search.py field), T003 (search.py helper) can all run in parallel (different files or independent sections)
- T004 wires them together — depends on T001, T002, T003

**User Story 1**:
- T005 (codegen) must run first to generate types from backend schema changes
- T006 (API query), T007 (domain types) can run in parallel
- T008 depends on T006 + T007
- T009 depends on T008
- T010 depends on T009

### Parallel Opportunities

Within Foundational phase:
- T001 (query class in ipam.py) can run in parallel with T002 + T003 (search.py changes), then T004 wires them together

Within US1:
- T006, T007 (frontend API + domain) can run in parallel after T005

Cross-story:
- US2 (T011) can start as soon as T009 is complete (does not need T010)

---

## Parallel Example: User Story 1

```bash
# After Foundational (T001-T004) is complete:

# First, regenerate types:
Task: T005 "Regenerate GraphQL schema and frontend types"

# Launch frontend API + domain in parallel:
Task: T006 "Update GraphQL query in frontend/app/src/entities/navigation/api/search.ts"
Task: T007 "Add isPrefixLookup to domain types in frontend/app/src/entities/navigation/domain/search-anywhere.ts"

# Then sequentially:
Task: T008 "Update hook in frontend/app/src/entities/navigation/domain/search-anywhere.query.ts"
Task: T009 "Create SearchPrefixes component in frontend/app/src/entities/navigation/ui/search-anywhere/search-prefixes.tsx"
Task: T010 "Wire conditional rendering in frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Foundational (T001-T004)
2. Complete Phase 2: User Story 1 (T005-T010)
3. **STOP and VALIDATE**: Search for valid IPv4/IPv6 addresses via Cmd+K, verify parent prefixes appear
4. Deploy/demo if ready — this alone delivers the core customer value

### Incremental Delivery

1. Foundational → Backend API ready
2. Add US1 → Test independently → Deploy (MVP: IP address lookup works)
3. Add US2 → Test independently → Deploy (CIDR prefix lookup with exact match indicator)
4. US3 + US4 → Verify independently → No code changes needed
5. Polish → Changelog, formatting

### Notes

- US3 and US4 require NO new code — they are verified by the foundational and US1 implementation
- The bulk of the work is in Foundational (T001-T004) and US1 frontend (T006-T010)
- US2 is a single frontend enhancement (T011)
- Total implementation: 13 tasks across 6 phases
