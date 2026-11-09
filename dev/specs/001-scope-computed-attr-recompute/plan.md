# Implementation Plan: Scope Computed-Attribute Recompute to Actual Schema Changes

**Branch**: `001-scope-computed-attr-recompute` | **Date**: 2026-06-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `dev/specs/001-scope-computed-attr-recompute/spec.md`

> Regenerated 2026-06-03 to fold in the Session 2026-06-03 clarifications (observability medium = task logs; full-depth dependency traversal with conservative fallback; per-attribute indeterminate dependency → always recompute, FR-013; any schema edit counts as "changed", incl. cosmetic).

## Summary

Today, any schema change emits a `SchemaUpdatedEvent` (`backend/infrahub/events/schema_action.py`) carrying only `branch_name` + `schema_hash`. That event fires `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` (`backend/infrahub/computed_attribute/triggers.py`), which runs `computed_attribute_setup_jinja2` and `computed_attribute_setup_python` (`backend/infrahub/computed_attribute/tasks.py`). Those setup flows iterate **every** computed attribute defined on the branch and, per attribute, call `client.all(kind=...)` and submit one recompute job per object — regardless of whether the schema change touched anything the attribute reads.

This feature scopes that fan-out: a computed attribute is recomputed only when the schema change affects a schema element (object type, attribute, or relationship) that the attribute's value depends on. The technical approach is:

1. **Carry the changed-element set** from the schema-update paths into the recompute decision (extend `SchemaUpdatedEvent` payload with the added/changed/removed kinds and fields produced by `SchemaBranch.diff()`). The changed-element set includes **every** element the diff reports as changed — there is no "value-affecting" classifier, so cosmetic edits (label, description, ordering) count as changes.
2. **Derive each computed attribute's dependency set at full depth.** Jinja2 attributes reuse the existing dependency graph in `Jinja2ComputedRegistry` (`local_fields` + `relationship_dependencies`). Transform-based attributes get a **new** deriver that parses the transform's stored GraphQL query (via the SDK `GraphQLQueryAnalyzer`) to extract the kinds/fields it reads, following relationships to whatever depth the query expresses. Where the depth or the precise read set cannot be determined for a given attribute, that attribute is marked "depends on everything" and is always recomputed (conservative; never skips a needed recompute).
3. **Intersect** changed-element set against each dependency set in the setup flows; submit recompute only for attributes whose dependency set is impacted (or that depend on everything). Skipped attributes are recorded.
4. **Fail safe at two granularities.** (a) When the changed-element set is unavailable for the whole path (branch deletion, merge/rebase paths that do not surface a diff), fall back to the current full recompute (FR-008). (b) When the path *does* surface a diff but a *single* attribute's dependency set is indeterminate, recompute only that attribute always — without escalating to a branch-wide full recompute (FR-013).
5. **Observability via task logs.** The recompute setup flows log, at info level, a summary of the attributes selected for recompute (count + identities); the intentionally-skipped set is logged at debug level. No new event/metric surface is introduced.

Recompute remains asynchronous (background workflows) and branch-aware (existing `registry.get_altered_schema_branches()` scoping is preserved unchanged).

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Prefect (workflows/triggers), Neo4j 5.28, Pydantic 2.10, `infrahub-sdk` (`GraphQLQueryAnalyzer`), `graphql-core`
**Storage**: Neo4j (graph) — no new persisted data model; dependency sets are derived in-memory from the active `SchemaBranch`
**Testing**: pytest 9.0 — unit (`backend/tests/unit/computed_attribute/`), component (`backend/tests/component/computed_attribute/`), integration_docker (`backend/tests/integration_docker/test_computed_attributes.py`)
**Target Platform**: Linux server (backend task workers / Prefect)
**Project Type**: Web service backend (single backend project; no frontend change)
**Observability**: Recompute task logs — info-level summary of selected attributes (count + identities); debug-level list of skipped attributes (FR-012, SC-006). No new metric/event channel.
**Performance Goals**: Recompute work scales with the number of *impacted* computed attributes, not the total number defined on the branch (SC-003). Schema changes touching unrelated types produce zero recompute jobs for unaffected attributes (SC-001).
**Constraints**: Asynchronous / eventually consistent (FR-011). Correctness over optimization — never skip a needed recompute, at either path or per-attribute granularity (FR-008, FR-013). Branch isolation preserved (FR-010).
**Scale/Scope**: Branches may hold thousands of objects across many computed attributes; the defect is most visible on large datasets. Change is confined to the schema-update event payload, the `computed_attribute` package, and a new transform-query dependency deriver.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Gates derived from `.specify/memory/constitution.md` (v1.0.0):

| Principle | Gate | Status |
|-----------|------|--------|
| I. Schema-Driven Integrity | Dependency sets derived from the active schema; no manual edits to generated files; computed values still flow through the schema/attribute layer. | PASS — read-only use of `SchemaBranch`; no generated-file edits. |
| II. Branch-Safe by Default | Recompute scoping must remain branch-aware (FR-010); **merge behavior and cross-branch isolation MUST be specified and tested before the feature is complete.** | PASS *with required coverage* — branch scoping reuses `get_altered_schema_branches()`; merge/rebase behavior is specified (scoped when diff surfaced, else full recompute) and MUST be covered by a test, and a test MUST assert no cross-branch broadening. See quickstart Scenarios H (branch isolation) and J (merge/rebase). |
| III. Type Safety & Explicit Contracts | Type hints on all new code; frozen dataclasses / Pydantic for the changed-element set and dependency set; `str \| None` style. | PASS — contracts defined as frozen dataclasses (see `contracts/`). |
| IV. Test Discipline | Computed-attribute work requires integration_docker coverage per constitution; component + unit tests for scoping logic; reuse existing fixtures. | PASS — test plan covers unit (deriver/scoper), component (setup-flow scoping), integration_docker (zero-job, dependency-change, fallback, merge). |
| V. Query Performance & Efficiency | The whole point is fewer jobs/queries; no new N+1; dependency derivation is in-memory over already-loaded schema. | PASS — reduces queries; transform-query parsing is in-memory AST work. |
| VI. Security & Input Boundaries | No new external input surface; GraphQL query text parsed is operator-authored transform definitions already in the system. | PASS — no new injection surface; no auth change. |
| VII. Simplicity & Maintainability | Reuse the existing Jinja2 dependency graph; introduce the Python-transform deriver only because a second computed-attribute kind genuinely requires it. Follow DI / single-entry-point component design (`dev/rules/backend-component-design.md`). | PASS — extends existing structures; one justified new component. |

No violations. **Required-coverage note (Principle II):** the merge/rebase path test and the cross-branch isolation test are mandatory for completion — tasks.md must carry them (this was flagged by `/speckit-analyze` as C1/C2). Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
dev/specs/001-scope-computed-attr-recompute/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── recompute-scoping.md
├── spec.md              # Feature specification (input)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

```text
backend/infrahub/
├── events/
│   └── schema_action.py                      # SchemaUpdatedEvent — extend payload with changed-element set
├── computed_attribute/
│   ├── tasks.py                              # computed_attribute_setup_{jinja2,python}: apply scoping before fan-out
│   ├── triggers.py                           # TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA: thread changed-element set into workflow params
│   ├── gather.py                             # trigger gathering (branch scoping reused unchanged)
│   ├── models.py                             # trigger/target definitions
│   └── scoping.py                            # NEW: dependency-set intersection + selected/skipped report (single-entry-point component)
├── core/schema/
│   ├── schema_branch.py                      # SchemaBranch.diff() -> SchemaDiff (changed-element source)
│   └── schema_branch_computed/
│       ├── jinja2.py                         # Jinja2ComputedRegistry — reuse dependency graph for Jinja2 dependency set
│       └── python_transform.py               # PythonTransformRegistry — extend with GraphQL-query dependency derivation
└── graphql/
    ├── mutations/schema.py                   # emits SchemaUpdatedEvent (interactive edit path)
    └── analyzer.py                           # GraphQLQueryReport.requested_read — reused to parse transform queries

backend/infrahub/api/schema.py                # schema load endpoint — diff already computed here; emit it on the event
backend/infrahub/core/merge/branch_merger.py  # merge path — surface diff when available, else fall back (must be tested)

backend/tests/
├── unit/computed_attribute/                  # scoping logic + transform-query deriver (no DB)
├── component/computed_attribute/             # setup-flow scoping with DB (reuse schema_with_jinja2 fixture)
└── integration_docker/test_computed_attributes.py  # zero jobs / dependency change / fallback / merge / branch isolation

changelog/                                    # towncrier ".fixed.md" fragment (user-facing defect fix)
dev/knowledge/backend/computed-attributes.md  # document scoped-recompute model + Python transform coverage
```

**Structure Decision**: Single backend project (web-service backend, no frontend impact). All changes live in `backend/infrahub/computed_attribute/`, the `SchemaUpdatedEvent` payload, the schema-update emission sites, and the two computed-attribute registries under `backend/infrahub/core/schema/schema_branch_computed/`. The one new module (`scoping.py`) follows the constructor-injection / single-entry-point pattern from `dev/rules/backend-component-design.md`, with a `Protocol` for the per-kind dependency derivers (Jinja2 vs Python transform are the two implementations that justify it).

## Complexity Tracking

> No constitution violations. No entries required.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
