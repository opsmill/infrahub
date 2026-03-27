# Implementation Plan: Local Computation of Jinja2 Computed Attributes

**Branch**: `ifc-2273-local-computation-jinja2` | **Date**: 2026-03-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/ifc-2273-local-computation-jinja2/spec.md`

## Summary

Optimize Jinja2 computed attribute updates by evaluating "local" changes (attribute or relationship changes on the same node) inline during the update mutation, reusing the existing `_process_macros()` template rendering pattern. Remote changes (peer node attribute changes) continue through Prefect background tasks. This eliminates thousands of unnecessary background tasks during bulk updates and provides immediate computed attribute results in mutation responses.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Neo4j 5.28, Pydantic 2.10, Jinja2 (via `InfrahubJinja2Template`), Prefect
**Storage**: Neo4j graph database
**Testing**: pytest (unit, component, functional, integration_docker)
**Target Platform**: Linux server (Docker)
**Project Type**: Web application (backend-only change)
**Performance Goals**: Zero background tasks for local computed attribute changes; bulk update of 2,000 nodes must not spawn background tasks for local changes
**Constraints**: Must produce identical results to existing background task path; must not affect creation path or template instantiation
**Scale/Scope**: Affects all node kinds with Jinja2 computed attributes across all branches

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | PASS | No schema changes; uses existing computed_attribute schema definitions |
| II. Branch-Safe by Default | PASS | Inline computation uses branch-aware `schema_branch` and `resolve_relationships()` |
| III. Type Safety & Explicit Contracts | PASS | All new code will use typed dataclasses/Pydantic models; no new APIs |
| IV. Test Discipline | PASS | Unit tests for dependency detection, functional tests for inline recomputation, integration_docker tests for computed attributes |
| V. Query Performance & Efficiency | PASS | Eliminates background task DB queries; reuses existing `resolve_relationships()` peer loading |
| VI. Security & Input Boundaries | PASS | No new user input; Jinja2 templates already validated at schema time |
| VII. Simplicity & Maintainability | PASS | Follows existing `_update()` pattern for HFID/display_label recomputation |

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2273-local-computation-jinja2/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (empty — no API changes)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/infrahub/core/
├── node/
│   └── __init__.py              # _update(), _collect_extra_filters(), new _recompute_local_jinja2()
├── schema/
│   └── schema_branch_computed.py  # get_local_jinja2_targets() helper
├── computed_attribute/
│   └── models.py                  # Skip triggers where targets_self=True
└── events/
    └── node_action.py             # No changes needed (changelog already consolidates)

backend/tests/
├── unit/core/schema/
│   └── test_schema_branch_computed.py  # Test local target detection
├── unit/core/node/
│   └── test_computed_jinja2_update.py  # Test inline recomputation logic
├── functional/computed_attribute/
│   └── test_local_computation.py       # End-to-end local recomputation
└── integration_docker/computed_attribute/
    └── test_local_no_background_task.py  # Verify no Prefect tasks for local changes
```

**Structure Decision**: Backend-only changes in the existing `backend/infrahub/core/` tree. No new packages or directories needed. Tests follow existing structure mirroring.

## Complexity Tracking

No constitution violations to justify.
