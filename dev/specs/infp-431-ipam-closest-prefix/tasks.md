# Tasks: IPAM Parent Prefix Lookup

**Input**: Design documents from `/specs/infp-431-ipam-closest-prefix/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per constitution Principle IV (test discipline).

**Organization**: Tasks grouped by user story. Backend query + resolver changes are foundational since all user stories depend on them.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Foundational (Backend Query + Resolver)

**Purpose**: Core backend infrastructure that ALL user stories depend on. Must complete before frontend work begins.

- [x] T001 [P] Add `IPParentPrefixResult` frozen dataclass with `from_db()` classmethod in `backend/infrahub/core/query/ipam.py` — follows `IPPrefixFreeData` pattern, fields: `prefix_id: str`, `prefix_kind: str`
- [x] T002 Add `IPParentPrefixLookupQuery` class in `backend/infrahub/core/query/ipam.py` — adapt `_build_possible_parent_prefixes()` from `IPPrefixReconcileQuery`, accept `ip_value: IPv4Address | IPv6Address | IPv4Network | IPv6Network`, query all namespaces, return results ordered by `prefixlen DESC`, use `branch.get_query_filter_path()` for branch safety (depends on T001)
- [x] T003 [P] Add `_try_parse_ip_or_prefix()` helper function in `backend/infrahub/graphql/queries/search.py` — try `ipaddress.ip_address(q)` then `ipaddress.ip_network(q, strict=False)`, return parsed object or `None`
- [x] T004 Add nullable `parent_prefixes` field to `NodeEdges` GraphQL type in `backend/infrahub/graphql/queries/search.py` — `Field(List(of_type=NonNull(NodeEdge)), required=False)`
- [x] T005 Extend `search_resolver()` in `backend/infrahub/graphql/queries/search.py` — after IPv6 normalization, call `_try_parse_ip_or_prefix(q)`, if valid IP/CIDR run `IPParentPrefixLookupQuery` and populate `parent_prefixes` in response, always run existing text search regardless (depends on T002, T003, T004)
- [x] T006 [P] Unit tests for `_try_parse_ip_or_prefix()` in `backend/tests/unit/graphql/queries/test_search.py` — test IPv4 address, IPv6 address, CIDR prefix, partial IP returns None, hostname returns None, empty string returns None, IPv6 non-canonical formats
- [x] T007 Component tests for parent prefix lookup in `backend/tests/component/graphql/queries/test_search.py` — test IPv4 address returns containing prefixes ordered by specificity, test IPv4 prefix returns parents (excludes exact match), test non-IP query returns `parent_prefixes: null`, test valid IP with no matching prefixes returns empty list, test existing IP address object appears in `edges` alongside parent prefixes in `parent_prefixes` (FR-013), test parent prefix lookup on a non-default branch returns only that branch's prefixes (FR-011)

**Checkpoint**: Backend API returns `parent_prefixes` field. Verifiable via direct GraphQL query.

---

## Phase 2: User Story 1 — Find Parent Prefix for IP Address (Priority: P1) MVP

**Goal**: User searches for an IP address (e.g., "10.1.2.45") in Cmd+K and sees all containing parent prefixes in a dedicated "Parent Prefixes" section.

**Independent Test**: Search for any valid IP address and verify containing prefixes appear in a separate section, ordered most-specific first, each with namespace label.

### Implementation for User Story 1

- [x] T008 [US1] Extend GraphQL query in `frontend/app/src/entities/navigation/api/search.ts` — add `parent_prefixes { node { id kind } }` field to the `SEARCH` query
- [x] T009 [US1] Extend domain types in `frontend/app/src/entities/navigation/domain/search-anywhere.ts` — add `parentPrefixes: Array<ObjectResult> | null` to the return type, map from `parent_prefixes` field in API response
- [x] T010 [US1] Update query hook in `frontend/app/src/entities/navigation/ui/queries/search-anywhere.query.ts` — ensure `parentPrefixes` is exposed from `useGetSearchAnywhere()` return value
- [x] T011 [US1] Create `SearchParentPrefixes` component in `frontend/app/src/entities/navigation/ui/search-anywhere/search-parent-prefixes.tsx` — follow `SearchNodes` pattern, read `parentPrefixes` from search response, render each result using the existing `NodesOptions` component inside a `SearchAnywhereGroup` with heading "Parent Prefixes", show empty state message when `parentPrefixes` is an empty array, return null when `parentPrefixes` is null
- [x] T012 [US1] Add `SearchParentPrefixes` to `frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere.tsx` — insert between `SearchActions` and `SearchNodes` in the `Command.List`

**Checkpoint**: Searching for an IPv4 address in the search dialog shows parent prefixes in a dedicated section above regular search results. US1 acceptance scenarios 1-4 are verifiable.

---

## Phase 3: User Story 2 — Find Parent Prefix for Known Prefix (Priority: P2)

**Goal**: User searches for a CIDR prefix (e.g., "10.1.2.0/24") and sees exact match in regular results plus containing parent prefixes in the "Parent Prefixes" section.

**Independent Test**: Search for a prefix in CIDR notation and verify exact match appears in Objects, parent prefixes appear in Parent Prefixes section (no duplication).

### Implementation for User Story 2

No additional code changes required — the backend `IPParentPrefixLookupQuery` already handles `IPv4Network`/`IPv6Network` inputs and the frontend `SearchParentPrefixes` component renders whatever `parent_prefixes` contains. The `_try_parse_ip_or_prefix()` function parses CIDR notation via `ipaddress.ip_network(q, strict=False)`.

- [x] T013 [US2] Add component test for CIDR prefix search in `backend/tests/component/graphql/queries/test_search.py` — verify searching "10.1.2.0/24" returns the prefix as a regular result in `edges` AND returns only true parent prefixes (10.1.0.0/16, 10.0.0.0/8) in `parent_prefixes` (exact match excluded)
- [x] T014 [US2] Add component test for non-existent prefix search in `backend/tests/component/graphql/queries/test_search.py` — verify searching "10.1.3.0/24" (not in DB) returns parent prefixes in `parent_prefixes` and empty `edges`

**Checkpoint**: US2 acceptance scenarios 1-2 verified.

---

## Phase 4: User Story 3 — Partial IP Falls Back to Text Search (Priority: P2)

**Goal**: Partial IP strings (e.g., "10.1.2") and non-IP text (e.g., "router-core-01") trigger regular text search only, with no parent prefix section.

**Independent Test**: Enter partial IPs and hostnames, verify regular search results appear and no "Parent Prefixes" section is shown.

### Implementation for User Story 3

No code changes required — `_try_parse_ip_or_prefix()` returns `None` for partial IPs (they fail `ipaddress.ip_address()` and `ipaddress.ip_network()` parsing), so `parent_prefixes` stays `null` and the frontend `SearchParentPrefixes` returns `null`.

- [x] T015 [US3] Add component test for partial IP fallback in `backend/tests/component/graphql/queries/test_search.py` — verify searching "10.1.2" returns `parent_prefixes: null` and regular text search results in `edges`
- [x] T016 [US3] Add component test for text search unchanged in `backend/tests/component/graphql/queries/test_search.py` — verify searching "router-core-01" returns `parent_prefixes: null` and existing text search behavior is preserved

**Checkpoint**: US3 acceptance scenarios 1-2 verified. Existing search behavior confirmed unchanged.

---

## Phase 5: User Story 4 — Navigate from Search Result (Priority: P3)

**Goal**: Clicking a parent prefix result navigates to the prefix detail page.

**Independent Test**: Click a prefix result in the Parent Prefixes section, verify navigation to `/ipam/BuiltinIPPrefix/{id}`.

### Implementation for User Story 4

No code changes required — `SearchParentPrefixes` reuses `NodesOptions` which uses `getObjectDetailsUrl()`, and `getObjectDetailsUrl` already routes `BuiltinIPPrefix` to `/ipam/{kind}/{id}`.

- [x] T017 [US4] Add E2E test for search-to-navigate workflow in `frontend/app/tests/e2e/search-parent-prefixes.spec.ts` — open Cmd+K, type a valid IP address, verify "Parent Prefixes" section appears, click a prefix result, verify navigation to prefix detail page

**Checkpoint**: Full end-to-end workflow verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, IPv6 support verification, documentation, changelog

- [x] T018 [P] Add component tests for IPv6 parent prefix lookup in `backend/tests/component/graphql/queries/test_search.py` — test IPv6 address search, test IPv6 with non-canonical formatting (FR-006), test IPv6 CIDR prefix search
- [x] T019 [P] Add component test for multi-namespace results in `backend/tests/component/graphql/queries/test_search.py` — verify same IP in multiple namespaces returns all matching prefixes with namespace context (FR-004)
- [x] T020 [P] Add Towncrier changelog fragment in `changelog/` — describe new parent prefix lookup in search anywhere dialog
- [ ] T021 [P] Add user-facing documentation in `docs/` — document the parent prefix lookup feature in the search anywhere section, covering IP address search, CIDR prefix search, IPv6 support, and namespace display
- [x] T022 Run `uv run invoke format` and `uv run invoke lint` (backend) and `cd frontend/app && npm run biome:fix` (frontend) to verify all code passes quality gates
- [x] T023 Run `uv run invoke schema.generate-graphqlschema` to regenerate `schema/schema.graphql` after adding `parent_prefixes` field to `NodeEdges` GraphQL type

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Foundational)**: No dependencies — start immediately
- **Phase 2 (US1)**: Depends on Phase 1 completion
- **Phase 3 (US2)**: Depends on Phase 1 completion (can run in parallel with US1)
- **Phase 4 (US3)**: Depends on Phase 1 completion (can run in parallel with US1/US2)
- **Phase 5 (US4)**: Depends on Phase 2 (US1) completion (needs frontend components)
- **Phase 6 (Polish)**: Depends on Phase 1 completion (tests), all phases for changelog

### User Story Dependencies

- **US1 (P1)**: Depends on foundational backend (Phase 1). This is the MVP.
- **US2 (P2)**: Backend already handles CIDR in Phase 1. Tests can run after Phase 1.
- **US3 (P2)**: Backend already handles fallback in Phase 1. Tests can run after Phase 1.
- **US4 (P3)**: Frontend navigation depends on US1 frontend components (Phase 2).

### Within Phase 1 (Foundational)

```
T001 (dataclass) ──┐
                    ├── T002 (query class) ──┐
T003 (parser)  ────────T004 (GraphQL type) ──┼── T005 (resolver)
                                              │
T006 (unit tests) ───────────────────────────┘
T007 (component tests) ── after T005
```

### Parallel Opportunities

- T001 and T003 can run in parallel (different files)
- T006 can run in parallel with T001/T002 (different file)
- US2 tests (T013-T014), US3 tests (T015-T016) can run in parallel after Phase 1
- T018, T019, T020, T021 can all run in parallel

---

## Parallel Example: Phase 1 Foundational

```bash
# Parallel batch 1 (different files):
Task T001: "Add IPParentPrefixResult dataclass in backend/infrahub/core/query/ipam.py"
Task T003: "Add _try_parse_ip_or_prefix() helper in backend/infrahub/graphql/queries/search.py"
Task T006: "Unit tests for _try_parse_ip_or_prefix() in backend/tests/unit/graphql/queries/test_search.py"

# Sequential after batch 1:
Task T002: "Add IPParentPrefixLookupQuery class (depends on T001)"
Task T004: "Add parent_prefixes field to NodeEdges (same file as T003)"
Task T005: "Extend search_resolver() (depends on T002, T003, T004)"
Task T007: "Component tests (depends on T005)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Foundational backend (T001-T007)
2. Complete Phase 2: US1 frontend (T008-T012)
3. **STOP and VALIDATE**: Search for an IPv4 address, verify parent prefixes appear
4. Deploy/demo if ready — delivers core customer value

### Incremental Delivery

1. Phase 1 (Foundational) → Backend API ready
2. Phase 2 (US1) → MVP: IP address search with parent prefixes
3. Phase 3 (US2) → CIDR prefix search verified
4. Phase 4 (US3) → Text search fallback verified
5. Phase 5 (US4) → E2E navigation verified
6. Phase 6 (Polish) → IPv6, multi-namespace, changelog
