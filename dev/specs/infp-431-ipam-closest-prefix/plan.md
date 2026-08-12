# Implementation Plan: IPAM Parent Prefix Lookup

**Branch**: `gma-431-ipam-closest-prefix` | **Date**: 2026-03-14 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/infp-431-ipam-closest-prefix/spec.md`

## Summary

Extend the search anywhere dialog (Cmd+K) to detect valid IP address and CIDR prefix queries and return all containing parent prefixes in a dedicated "Parent Prefixes" section. Uses a new `IPParentPrefixLookupQuery` that adapts the existing binary prefix matching algorithm from `IPPrefixReconcileQuery`, returning results ordered by specificity across all namespaces. The feature is purely additive — non-IP queries follow the exact same code path as before.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 (frontend)
**Primary Dependencies**: FastAPI, Graphene (GraphQL), React 19, cmdk, gql.tada, @tanstack/react-query
**Storage**: Neo4j 5.28 — existing `AttributeIPNetwork` nodes with `binary_address` index
**Testing**: pytest (backend unit + component), Vitest (frontend unit), Playwright (E2E)
**Target Platform**: Web application (Linux server backend, browser frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Parent prefix lookup in <3s (SC-001). Zero regression for non-IP text queries (SC-003).
**Constraints**: No cap on parent prefix result count (FR-002). Must respect branch context (FR-011).
**Scale/Scope**: Touches 2 backend files, 5-6 frontend files. ~200 lines new backend code, ~150 lines new frontend code.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | PASS | No schema changes. Operates on existing `BuiltinIPPrefix`, `AttributeIPNetwork`, `BuiltinIPNamespace` nodes. |
| II. Branch-Safe by Default | PASS | Uses `branch.get_query_filter_path()` for all Cypher queries (same as `IPPrefixReconcileQuery`). FR-011 explicitly requires branch context. |
| III. Type Safety & Explicit Contracts | PASS | New `IPParentPrefixResult` frozen dataclass with `from_db()`. GraphQL contract extended with typed `parent_prefixes` field. Frontend uses gql.tada typed queries. |
| IV. Test Discipline | PASS | Unit tests for IP parsing helper, component tests for search resolver with prefix lookup, E2E tests for full workflow. |
| V. Query Performance & Efficiency | PASS | Parameterized Cypher with `$possible_prefix_list`. Leverages existing `binary_address` index. Returns only `uuid` and `kind` (not full nodes). |
| VI. Security & Input Boundaries | PASS | Input validated via `ipaddress` stdlib (no user string interpolation into Cypher). All query parameters bound. |
| VII. Simplicity & Maintainability | PASS | Adapts existing `_build_possible_parent_prefixes()` algorithm. Reuses existing UI components (`NodesOptions`). No new abstractions. |

**Post-Phase 1 re-check**: All gates still pass. No new entities, no new dependencies, no new patterns introduced.

## Project Structure

### Documentation (this feature)

```text
specs/infp-431-ipam-closest-prefix/
├── plan.md              # This file
├── research.md          # Phase 0: research decisions
├── data-model.md        # Phase 1: data structures
├── quickstart.md        # Phase 1: architecture overview
├── contracts/           # Phase 1: API contracts
│   └── graphql-schema.md
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── infrahub/
│   ├── core/query/ipam.py                         # Add IPParentPrefixLookupQuery + IPParentPrefixResult
│   └── graphql/queries/search.py                  # Extend NodeEdges, search_resolver, add _try_parse_ip_or_prefix
└── tests/
    ├── unit/graphql/queries/test_search.py         # Unit tests for _try_parse_ip_or_prefix
    └── component/graphql/queries/test_search.py    # Component tests for parent prefix lookup

frontend/app/
├── src/entities/navigation/
│   ├── api/search.ts                               # Add parent_prefixes to GraphQL query
│   ├── domain/search-anywhere.ts                   # Add parentPrefixes to domain type
│   └── ui/
│       ├── search-anywhere/
│       │   ├── search-anywhere.tsx                  # Add SearchParentPrefixes component
│       │   └── search-parent-prefixes.tsx           # NEW: parent prefix results section
│       └── queries/
│           └── search-anywhere.query.ts             # Update query options
└── tests/e2e/
    └── search-parent-prefixes.spec.ts               # E2E tests
```

**Structure Decision**: Web application pattern — existing `backend/` and `frontend/app/` structure. All changes go into existing directories following established patterns.

## Complexity Tracking

No constitution violations. No complexity justifications needed.
