# Implementation Plan: IPAM Parent Prefix Lookup

**Branch**: `001-ipam-prefix-lookup` | **Date**: 2026-02-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-ipam-prefix-lookup/spec.md`

## Summary

Enhance the search anywhere (Cmd+K) feature to detect valid IP address/prefix input and return containing parent prefixes via binary address matching. The backend `search_resolver` will detect IP input using Python's `ipaddress` module, then execute a new `IPParentPrefixLookupQuery` that leverages existing RANGE indexes on `AttributeIPNetwork(binary_address)` and the `possible_prefix_list` containment pattern from `IPPrefixReconcileQuery`. Non-IP queries fall through to existing text search unchanged.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 (frontend)
**Primary Dependencies**: FastAPI, Graphene (GraphQL), Neo4j 5.28, React 19, cmdk, gql.tada
**Storage**: Neo4j graph database (existing `AttributeIPNetwork` nodes with `binary_address` RANGE index)
**Testing**: pytest (backend unit + functional), Vitest (frontend unit), Playwright (E2E)
**Target Platform**: Web application (Linux server backend, browser frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: IP lookup results in <3 seconds end-to-end; zero regression on existing text search
**Constraints**: Must respect branch/temporal context; must work across all IP namespaces; must not introduce new dependencies
**Scale/Scope**: Typical prefix hierarchies have <10 nesting levels; typical namespace count <10

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | PASS | No schema changes; uses existing `AttributeIPNetwork` nodes |
| II. Branch-Safe by Default | PASS | Query uses `branch.get_query_filter_path()` consistent with all IPAM queries |
| III. Type Safety & Explicit Contracts | PASS | New query class uses frozen dataclass for results; GraphQL schema extended with typed field |
| IV. Test Discipline | PASS | Plan includes unit tests for IP detection, query class tests, frontend component tests, E2E tests |
| V. Query Performance & Efficiency | PASS | Leverages existing RANGE index on `binary_address`; parameterized Cypher; returns only needed properties |
| VI. Security & Input Boundaries | PASS | Input validated via `ipaddress` module (stdlib); Cypher uses parameter binding |
| VII. Simplicity & Maintainability | PASS | Extends existing resolver (no new API surface); new query class follows established patterns; one new frontend component |

**Post-Phase 1 Re-check**: All principles still pass. No new abstractions introduced; query follows existing `IPPrefixReconcileQuery` pattern.

## Project Structure

### Documentation (this feature)

```text
specs/001-ipam-prefix-lookup/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research findings
├── data-model.md        # Data model documentation
├── quickstart.md        # Development quickstart guide
├── contracts/           # API contract definitions
│   └── graphql-search.md
├── checklists/          # Quality checklists
│   └── requirements.md
└── tasks.md             # Phase 2 task breakdown (created by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── infrahub/
│   ├── graphql/queries/search.py         # MODIFY: Add IP detection + prefix lookup routing
│   └── core/query/ipam.py                # MODIFY: Add IPParentPrefixLookupQuery class
└── tests/
    ├── unit/core/query/test_ipam_prefix_lookup.py    # NEW: Unit tests for query class
    ├── unit/graphql/queries/test_search.py            # MODIFY: Add IP detection tests
    └── functional/search/test_prefix_lookup.py        # NEW: Functional tests

frontend/app/
├── src/entities/navigation/
│   ├── api/search.ts                                  # MODIFY: Add is_prefix_lookup field
│   ├── domain/search-anywhere.ts                      # MODIFY: Add isPrefixLookup to types
│   └── ui/search-anywhere/
│       ├── search-anywhere.tsx                        # MODIFY: Conditional section rendering
│       ├── search-nodes.tsx                           # MODIFY: Skip when isPrefixLookup
│       └── search-prefixes.tsx                        # NEW: Parent prefix results component
└── tests/
    ├── unit/entities/navigation/                      # NEW: Frontend unit tests
    └── e2e/search/prefix-lookup.spec.ts               # NEW: E2E test
```

**Structure Decision**: Web application structure following existing Infrahub patterns. Backend changes in existing files plus one new query class. Frontend changes in existing search components plus one new result component.

## Complexity Tracking

No constitution violations. All changes follow existing patterns.
