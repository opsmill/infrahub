# Implementation Plan: Optimize Automated Task Query Performance

**Branch**: `optimize-prefect-queries-infp-501` | **Date**: 2026-04-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/infp-501-optimize-prefect-queries/spec.md`

## Summary

Replace verbose SDK read calls (`client.all()`, `client.filters()`) inside Prefect tasks with targeted custom GraphQL queries that fetch only the fields each task actually needs. Three tasks are explicitly flagged for optimization (`display_labels`, `hfid`, `computed_attribute`); a full audit will identify additional candidates across the remaining 26 task files. Each task is migrated independently using the existing `infrahub_sdk.graphql.Query` builder pattern already established in `hfid/models.py`.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: Prefect (workflow orchestration), `infrahub-sdk` (`InfrahubClient`, `infrahub_sdk.graphql.Query`), `fast_depends` (DI)
**Storage**: Neo4j 5.28 (accessed exclusively through the SDK client — no direct DB queries in this feature)
**Testing**: pytest 9.0, functional tests (preferred per constitution), unit tests for query models
**Target Platform**: Linux server (backend service process)
**Project Type**: web-service / workflow automation backend
**Performance Goals**: ≥30% reduction in task execution time; ≥50% reduction in data volume per task (per spec SC-001, SC-002)
**Constraints**: Each task migration independently deployable; zero behavioral regressions; all queries branch-aware; `client.get()` calls followed by SDK mutations (`.save()`/`.update()`) are out of scope (SDK requires full object for mutations)
**Scale/Scope**: ~3 `client.all()` priority-1 candidates + 3 `client.filters()` priority-2 candidates + 2 `client.get()` pure-read candidates; full audit across 29 task files (149 `@flow`/`@task` instances)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | ✅ Pass | No schema changes; no generated files modified |
| II. Branch-Safe by Default | ✅ Pass | All custom queries use `client.execute_graphql(branch_name=...)` — branch parameter already required |
| III. Type Safety & Explicit Contracts | ✅ Pass | Query models use typed Pydantic/frozen dataclasses; `parse_response()` returns typed results |
| IV. Test Discipline | ✅ Pass | Unit tests for query models + functional tests for output equivalence per task |
| V. Query Performance & Efficiency | ✅ Pass | **This feature directly implements Principle V** — replacing overfetching with targeted queries |
| VI. Security & Input Boundaries | ✅ Pass | `client.execute_graphql()` handles parameterization; no new user input surfaces |
| VII. Simplicity & Maintainability | ✅ Pass | Reuses existing `HFIDGraphQL` pattern; no new abstractions until 2+ callers justify extraction |

**Post-design re-check**: ✅ All gates pass. No complexity justification table required.

## Project Structure

### Documentation (this feature)

```text
specs/infp-501-optimize-prefect-queries/
├── plan.md          ← this file
├── research.md      ← Phase 0 output
├── data-model.md    ← Phase 1 output
└── tasks.md         ← Phase 2 output (/speckit-tasks command)
```

### Source Code (affected paths)

```text
backend/infrahub/
├── display_labels/
│   ├── models.py          # Add DisplayLabelNodeQuery
│   └── tasks.py           # Replace client.all() with DisplayLabelNodeQuery
├── hfid/
│   ├── models.py          # Audit HFIDGraphQL; add optimized read query model if needed
│   └── tasks.py           # Replace client.all() with custom query
├── computed_attribute/
│   ├── tasks.py           # Replace client.all() with ComputedAttributeNodeQuery
│   └── queries.py         # New file: ComputedAttributeNodeQuery (if models.py absent/large)
└── [other domains]        # Per audit results

tests/
├── unit/
│   └── [domain]/
│       └── test_*_query.py    # Unit tests for render_query() and parse_response()
└── functional/
    └── [domain]/
        └── test_*_tasks.py    # Output equivalence tests per migrated task
```

**Structure Decision**: Single backend project (Option 1). Changes are localized to domain-specific `models.py`/`queries.py` and `tasks.py` files within the existing feature-sliced structure. No new top-level directories.

## Implementation Phases

### Phase A: Audit & Inventory

1. Audit all 29 task files for `client.all()`, `client.filters()`, and `client.get()` calls.
2. For each call, record: file, line, kind queried, fields actually used by the task.
3. Produce a ranked list of optimization candidates by estimated data reduction.
4. Prioritize: `display_labels` → `hfid` → `computed_attribute` → remainder.

**Output**: Updated inventory table in `research.md`.

### Phase B: Per-Task Migration (repeat for each candidate)

Each task migration follows this pattern:

1. **Write unit test** for the new query model (`render_query()` output, `parse_response()` behavior).
2. **Write query model** in `models.py` or `queries.py` following `HFIDGraphQL` pattern.
3. **Write functional test** capturing pre-migration task output as a fixture.
4. **Replace SDK call** in `tasks.py` with `client.execute_graphql()` + query model.
5. **Verify** functional test passes (output equivalence confirmed).
6. **Add changelog fragment** in `changelog/`.

### Phase C: Validation

1. Run full test suite to confirm no regressions.
2. Measure execution time and data volume for each migrated task against pre-migration baseline.
3. Confirm SC-001 (≥30% time reduction) and SC-002 (≥50% data volume reduction) for each migrated task.
4. Confirm SC-005: all identified candidates either migrated or explicitly deferred with rationale.
