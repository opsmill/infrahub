# Implementation Plan: Precise Regeneration Triggers for Generators in the Pipeline Based on Git

**Branch**: `generator-regen-triggers-ifc-2738` | **Date**: 2026-06-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/ifc-2738-generator-regen-triggers/spec.md`
**Jira**: [IFC-2738](https://opsmill.atlassian.net/browse/IFC-2738) | **Implements (JPD)**: [INFP-607](https://opsmill.atlassian.net/browse/INFP-607)

## Summary

Generators (`CoreGeneratorDefinition`) re-run on every file change in any linked repository today, the same blunt gate INFP-409 already replaced for artifacts. This plan extends the *existing, shipped* INFP-409 machinery to generators with no new design: it widens the reusable `PythonClosure` builder and `TransformConfig` union to accept `InfrahubGeneratorDefinitionConfig`, stores `dependencies` / `dependencies_complete` on `CoreGeneratorDefinition`, plumbs `query_id` + those two attributes into the pipeline model, generalizes the three regeneration predicates (`_query_changed`, `_definition_changed`, `_transform_changed`) behind a structural `Protocol` both definition models satisfy, and swaps the two blunt generator gates (the definition-level `FILE_CHANGES` clause in `run_generators` and the per-member `managed_branch` flag in `request_generator_definition_check`) for precise predicate evaluation. The SDK gains a `watch:` field on `InfrahubGeneratorDefinitionConfig`, reusing the existing `InfrahubWatchConfig` — because the shared aggregator already unions `watch.files` and appends the manifest, adding the field makes generator `watch:` work end-to-end with no further backend wiring.

The design invariant is inherited verbatim from INFP-409: **over-execution is acceptable, under-execution is not.** Every fallback path (`dependencies = null`, `dependencies_complete = False`, unresolvable query peer) errs toward running the generator. The `MODIFIED_KINDS` data-change path and the per-member `impacted_instances` path are already correct and stay unchanged; the per-member gate swap (FR-007) is the single place where category-2 (`impacted_instances`) and category-3 (closure) logic meet and is the primary risk area.

## Technical Context

**Language/Version**: Python 3.14 (project supports `>=3.12,<3.15`) backend + SDK; TypeScript 5.9 / React 19.2 frontend (regenerated GraphQL types only, no UI work)
**Primary Dependencies**: FastAPI 0.131.0, Pydantic 2.12, Neo4j 2026.05 (driver 6.2), Prefect (pipeline orchestrator), Infrahub Python SDK (`python_sdk/` submodule)
**Storage**: Neo4j — two new optional/nullable attributes on `CoreGeneratorDefinition`
**Testing**: pytest 9.0 (unit / component); SDK unit tests. Predicate unit tests (generator-model variants), `PythonClosure` generator-config support test, generator-selection component test mirroring `test_artifact_regen_selection.py`, generator-import closure test, SDK `watch`-field tests. `test_proposed_change_repository.py` (e2e) is `xfail` on GitHub Actions for the same flakiness INFP-409 deferred.
**Target Platform**: Linux server (Docker), Neo4j-backed Infrahub deployment
**Project Type**: Web service with companion SDK (web-service)
**Performance Goals**: No regression in import time (closure rebuilt per commit, acceptable per spec Known Limitations). Pipeline selection check is O(definitions × diff_size) — a Python set intersection per definition, identical to the artifact path.
**Constraints**: Correctness invariant (never under-execute) is hard. SDK `watch:` field on `InfrahubGeneratorDefinitionConfig` ships coordinated with the backend, the same way the transform `watch:` shipped for INFP-409. All novel infrastructure already exists; this is replication and wiring.
**Scale/Scope**: Target groups of 10,000+ nodes; repositories with dozens of generators; proposed changes touching thousands of files. Two new attributes on one node; one new field on one SDK config model; one structural Protocol; two gate swaps.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | PASS | Adds `dependencies` / `dependencies_complete` to `CoreGeneratorDefinition` via the schema layer (FR-001), mirroring the INFP-409 attributes on `CoreTransformation`. Generated files (`core/schema/generated/`, `protocols.py`, frontend GraphQL types, `schema.graphql`, `openapi.json`) are regenerated, never hand-edited. |
| II. Branch-Safe by Default | PASS | Per-repo file diffs are computed per branch pair by the existing INFP-409 machinery; read-only repos participate via the already-shipped per-repo diff decoupling (FR-008). New attribute reads/writes flow through the normal branch-aware schema path. No new cross-branch side effects. |
| III. Type Safety & Explicit Contracts | PASS | New pipeline-model fields are typed Pydantic; the predicate generalization introduces a typed structural `Protocol` (FR-005) instead of `getattr`/duck-typing. SDK `watch:` reuses the strict `InfrahubWatchConfig` (object form, `extra="forbid"`). |
| IV. Test Discipline | PASS | Unit tests for generalized predicates (generator variants) and `PythonClosure` support; component test for generator selection mirroring `test_artifact_regen_selection.py`; integrator closure test; SDK `watch` parsing/strict-rejection/recursion tests. Artifact regression coverage (FR-013) proves the shared refactor leaves artifacts unchanged. E2e `xfail` deferral matches INFP-409. |
| V. Query Performance & Efficiency | PASS | Pipeline check is a Python set intersection; no new Cypher. The gather reads two scalar attributes plus `query.peer.id` (already fetched as `query.peer.name.value`) — no new traversal. Closure rebuild runs only on commits that re-import the repo. |
| VI. Security & Input Boundaries | PASS | `watch.files` entries are user input from `.infrahub.yml`, parsed through the strict SDK submodel and canonicalized by the existing shared canonicalizer before storage; never interpolated into Cypher. Closure builder reads worktree bytes via `git ls-files` — no shell-out on user strings. |
| VII. Simplicity & Maintainability | PASS | Reuses every INFP-409 component (closure builder, aggregator, canonicalizer, predicates, watch-union, diagnostics). The structural `Protocol` is extracted only because it now serves two real callers (artifact + generator models) — satisfies the two-caller rule. No new dependency. AST import analysis explicitly rejected (YAGNI + correctness). |

### Frontend principles (apply when feature includes UI)

Not applicable. No UI work is in scope. Frontend GraphQL types are regenerated (offline) because the schema gains two attributes, but no components, pages, or hooks change.

### Shared Components Inventory (frontend features only)

Not applicable.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2738-generator-regen-triggers/   (symlink: specs -> dev/specs)
├── plan.md                       # This file
├── research.md                   # Phase 0 output
├── data-model.md                 # Phase 1 output
├── quickstart.md                 # Phase 1 output
├── contracts/                    # Phase 1 output
│   ├── definition-protocol.md        # structural Protocol both definition models satisfy + predicate reuse
│   └── generator-watch-config.md     # SDK `watch:` field on InfrahubGeneratorDefinitionConfig
├── checklists/
│   └── requirements.md           # already present
├── spec.md                       # already present
└── tasks.md                      # Phase 2 output (NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── infrahub/
│   ├── proposed_change/
│   │   └── tasks.py                  # generalize _query_changed/_definition_changed/_transform_changed (FR-005);
│   │                                 #   swap FILE_CHANGES gate in run_generators (FR-006);
│   │                                 #   swap managed_branch in request_generator_definition_check (FR-007)
│   ├── generators/
│   │   ├── models.py                 # ProposedChangeGeneratorDefinition gains query_id, dependencies, dependencies_complete (FR-004)
│   │   └── tasks.py                  # run_generator_definition (~156): 2nd construction site, must set query_id (FR-004)
│   ├── git/
│   │   ├── integrator.py             # build closure in _build_generator_definitions (has worktree); thread ClosureResult
│   │   │                             #   to _apply/_create/_update; compare closure in _generator_requires_update (FR-003)
│   │   └── closure_builder/
│   │       ├── python_closure.py     # PythonClosure.supports() widened to InfrahubGeneratorDefinitionConfig (FR-002)
│   │       └── protocols.py          # TransformConfig union widened to include InfrahubGeneratorDefinitionConfig (FR-002)
│   └── core/
│       └── schema/definitions/core/
│           └── generator.py          # CoreGeneratorDefinition: dependencies, dependencies_complete attrs (FR-001)
└── tests/
    ├── unit/
    │   ├── proposed_change/          # predicate unit tests: generator-model variants + protocol satisfaction (FR-011)
    │   └── git/closure_builder/      # PythonClosure generator-config support test (FR-011)
    └── component/
        └── proposed_change/          # test_generator_regen_selection.py mirroring test_artifact_regen_selection.py (FR-011),
                                      #   reusing conftest helpers (make_node_diff, query constants) and the existing
                                      #   test_request_generator_definition_check.py fixtures; artifact regression assertions (FR-013).
                                      #   Generator fixture repos already exist (e.g. car-dealership, 4 generators).

python_sdk/
└── infrahub_sdk/
    └── schema/
        └── repository.py             # watch: InfrahubWatchConfig | None on InfrahubGeneratorDefinitionConfig (FR-014..FR-017)
        # + python_sdk tests for parsing, strict-object rejection, recursive expansion

docs/docs/
├── topics/ or reference/             # extend dependency-closure / why-trail docs to mention generators;
│                                     #   add generator `watch:` schema-reference entry (FR-012)
└── (regenerated: schema.graphql, openapi.json, frontend GraphQL types)

changelog/
└── +ifc-2738.*.md                    # Towncrier fragment (FR-012)
```

**Structure Decision**: Multi-package web-service repo. The work is parallel wiring into existing INFP-409 components plus one schema attribute pair and one SDK field. Backend pipeline changes live in `backend/infrahub/proposed_change/tasks.py` (predicates + both gates) and `backend/infrahub/generators/models.py` (pipeline model). Import-time closure wiring lives in `backend/infrahub/git/integrator.py` and the two one-line widenings in `backend/infrahub/git/closure_builder/`. The schema attribute pair lives in `backend/infrahub/core/schema/definitions/core/generator.py` and triggers regeneration of `protocols.py`, the generated schema, the GraphQL/OpenAPI exports, and frontend types. The SDK field lives in `python_sdk/infrahub_sdk/schema/repository.py` and is committed as an explicit submodule update.

## Complexity Tracking

No deviations from the constitution. The single new abstraction (the structural `Protocol`, FR-005) is justified under Principle VII because it serves two existing callers (the artifact and generator definition models) the moment it is introduced — it is the minimum needed to let the shipped artifact predicates also accept generator definitions without duck-typing.

## Phase 0 / Phase 1 outputs

See:

- [research.md](./research.md) — open-question resolution, predicate-generalization design, per-member gate analysis, fallback design.
- [data-model.md](./data-model.md) — schema additions, pipeline-model extensions, the structural Protocol shape, SDK config shape.
- [contracts/definition-protocol.md](./contracts/definition-protocol.md) — the structural Protocol and the predicate / gate replacement matrix.
- [contracts/generator-watch-config.md](./contracts/generator-watch-config.md) — `.infrahub.yml` generator `watch:` field schema.
- [quickstart.md](./quickstart.md) — end-to-end manual verification recipe.
