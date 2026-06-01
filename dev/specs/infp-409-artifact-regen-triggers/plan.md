# Implementation Plan: Refactor When Artifacts Are Regenerated on Git Changes

**Branch**: `artifact-regen-triggers-infp-409` | **Date**: 2026-06-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `dev/specs/infp-409-artifact-regen-triggers/spec.md`
**Source investigation**: [`dev/specs/infp-409-artifact-regeneration-investigation.md`](../infp-409-artifact-regeneration-investigation.md)
**Jira**: [INFP-409](https://opsmill.atlassian.net/browse/INFP-409)

## Summary

Today every artifact in every artifact definition is regenerated when any file changes in any linked Git repository, even unrelated edits like a README typo. This plan delivers a two-stage refactor of the regeneration gate so that only definitions whose closure actually changed are regenerated, while preserving the design invariant that *over-regeneration is acceptable, under-regeneration is not*.

The technical approach is taken directly from the source investigation. **Stage 1** (no schema additions, no SDK coordination) replaces the blunt `has_file_modifications` selection gate in `refresh_artifacts` and `validate_artifacts_generation` with two per-definition predicates against `diff_summary`: `_query_changed` (checks `definition.query_id`) and `_definition_changed` (checks the `CoreArtifactDefinition` node id). **Stage 2** adds `dependencies: list[str]` and `dependencies_complete: bool` to `CoreTransformation` (the generic), populated at git-import time by per-language closure builders (Jinja2 AST walk; Python package-directory floor) unioned with a new user-declared `watch: { files: [...] }` field on `python_transforms` / `jinja2_transforms` in `.infrahub.yml`. At pipeline time the per-definition check is a set intersection between the stored closure and the per-repository file diff. The repo file diff is also decoupled from `sync_with_git` so `CoreReadOnlyRepository` participates fully.

Diagnostic logging via the Prefect logger covers every "all artifacts regenerated" decision (which file/query/attribute triggered it) and every closure-builder failure or unresolved reference at import time. Backward compatibility is provided per-transform: a transform with `dependencies is null` (imported before this code deploys) falls back to today's legacy gate until its next natural re-import populates the closure.

## Technical Context

**Language/Version**: Python 3.13 (primary per `.python-version`; project supports `>=3.12,<3.15`) backend + SDK; TypeScript 5.9 / React 19.2 frontend (no UI work in scope)
**Primary Dependencies**: FastAPI 0.131.0, Pydantic 2.12.x, Neo4j 6.0.3 (driver + `neo4j-rust-ext`), Jinja2 3.1 (`>=3,<4`), Prefect 3.6.13 (pipeline orchestrator), Infrahub Python SDK (`python_sdk/`)
**Storage**: Neo4j 6.0.3 (graph database) — two new attributes on `CoreTransformation`
**Testing**: pytest 9.0 (unit / component / functional / integration_docker). New tests required across unit (closure builders, path normalizer, pipeline predicates), functional (pipeline behavior with the new predicates), and integration_docker (end-to-end proposed-change flow with `CoreRepository` and `CoreReadOnlyRepository`).
**Target Platform**: Linux server (Docker), Neo4j-backed Infrahub deployment
**Project Type**: Web service with companion SDK (web-service)
**Performance Goals**: No regression in import time on representative repos (closure rebuild on every commit is acceptable per spec Assumptions). Pipeline selection check must be O(definitions × diff_size) at worst — set intersection per definition.
**Constraints**: Correctness invariant (never under-regenerate) is hard. Stage 1 ships with no schema change and no SDK release; Stage 2 requires a coordinated SDK release for the `watch:` schema. Stage 1 and Stage 2 can ship in the same release or sequentially; the spec defines the interim behavior if Stage 1 ships first.
**Scale/Scope**: Target groups of 10,000+ nodes; repositories with dozens to hundreds of transforms; proposed changes that touch up to thousands of files per commit. Two new attributes on a generic with two specializations; one new field on two SDK repository-config models.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | PASS | Stage 2 adds two attributes (`dependencies`, `dependencies_complete`) to `CoreTransformation` via the schema layer; generated files (`backend/infrahub/core/schema/generated/`, `protocols.py`, frontend types) are regenerated, never hand-edited. |
| II. Branch-Safe by Default | PASS | Per-repo file diffs are computed per branch pair (FR-017–FR-020). All new attribute reads/writes flow through the normal branch-aware schema path. No cross-branch side effects. |
| III. Type Safety & Explicit Contracts | PASS | New backend models (`ProposedChangeArtifactDefinition`, closure-builder results) are typed via Pydantic / frozen dataclasses; SDK `watch:` is a strict Pydantic submodel (no list/object union — FR-011). No `getattr`-based enum dispatch. |
| IV. Test Discipline | PASS | Unit tests for closure builders, path normalizer, and pipeline predicates; functional tests for selection + fan-out behavior; integration_docker tests for the full proposed-change pipeline against both `CoreRepository` and `CoreReadOnlyRepository`. No new mocks introduced beyond the existing Prefect logger surface. |
| V. Query Performance & Efficiency | PASS | Pipeline check is a set intersection in Python; no new Cypher. The extension of `GATHER_ARTIFACT_DEFINITIONS` selects two scalar attributes under `transformation { node { ... } }` — no new traversal cost. Closure rebuild at import time runs on commits that touch the repo only. |
| VI. Security & Input Boundaries | PASS | `watch.files` entries are user input from `.infrahub.yml` and pass through the SDK's Pydantic schema (object form, no polymorphism). Paths are normalized through a shared canonicalizer before storage and never interpolated into Cypher. Closure builder reads file bytes from the git worktree — no shell out. |
| VII. Simplicity & Maintainability | PASS | The two predicates (`_query_changed`, `_definition_changed`, `_transform_changed`) replace a single conjoined gate. The `watch:` schema is a strict object so future keys (`strict:`, `exclude:`) can land without migration; YAGNI rule respected — we are not implementing them now. Path normalizer is one shared helper used on both sides of the intersection. |

### Frontend principles (apply when feature includes UI)

Not applicable. This feature has no UI work in scope. The Phase 3 UI surfacing for fingerprint results from the source investigation is explicitly out of scope. Pipeline-task-log surface (Infrahub repository task log) already exists.

### Shared Components Inventory (frontend features only)

Not applicable.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-409-artifact-regen-triggers/
├── plan.md                 # This file
├── research.md             # Phase 0 output
├── data-model.md           # Phase 1 output
├── quickstart.md           # Phase 1 output
├── contracts/              # Phase 1 output
│   ├── watch-config.md         # SDK schema for `watch:`
│   └── pipeline-predicates.md  # _query_changed / _definition_changed / _transform_changed
├── checklists/
│   └── requirements.md     # already present
├── spec.md                 # already present
└── tasks.md                # Phase 2 output (NOT created by /speckit-plan)
```

The Phase 2 deliverables in this file refer to the *spec-kit* phases (Stage 1 selection / Stage 2 closure are the *feature* delivery stages and are documented under "Source Code" below).

### Source Code (repository root)

```text
backend/
├── infrahub/
│   ├── proposed_change/
│   │   ├── tasks.py                # Stage 1: replace FILE_CHANGES gate; Stage 2: remove has_file_modifications short-circuit; gather query extended
│   │   ├── models.py               # ProposedChangeArtifactDefinition gains dependencies / dependencies_complete
│   │   └── branch_diff.py          # per-repo, per-branch-pair file diff (decoupled from sync_with_git)
│   ├── message_bus/
│   │   └── types.py                # ProposedChangeArtifactDefinition shape
│   ├── git/
│   │   ├── integrator.py           # closure builder call sites for Jinja2 and Python transforms
│   │   └── closure_builder/        # NEW: Jinja2Closure, PythonClosure, PathCanonicalizer, ManifestPathResolver
│   │       ├── __init__.py
│   │       ├── canonicalizer.py
│   │       ├── jinja2_closure.py
│   │       ├── python_closure.py
│   │       └── result.py           # ClosureResult dataclass (deps, complete, unresolved)
│   └── core/
│       └── schema/definitions/core/
│           └── transform.py        # CoreTransformation: dependencies, dependencies_complete attrs
└── tests/
    ├── unit/
    │   ├── git/closure_builder/    # NEW: closure builder + canonicalizer unit tests
    │   └── proposed_change/        # NEW: predicate unit tests (_query_changed, _definition_changed, _transform_changed)
    ├── functional/
    │   └── proposed_change/        # extended: end-to-end selection + fan-out behavior on a real DB
    └── integration_docker/
        └── proposed_change/        # extended: CoreRepository and CoreReadOnlyRepository scenarios end-to-end

python_sdk/
└── infrahub_sdk/
    └── schema/
        └── repository.py           # InfrahubWatchConfig (strict object); added to Jinja2 + Python transform configs

docs/docs/
├── topics/
│   └── proposed-change.mdx         # extended: "Where to find the why trail" section
└── reference/
    └── infrahub-yml/...            # `watch:` schema reference + dependencies_complete user guidance

changelog/
└── +infp-409-*.changed.md          # Towncrier fragment(s) — at least one per stage
```

**Structure Decision**: Multi-package web-service repo. Backend changes live under `backend/infrahub/proposed_change/` (pipeline) and `backend/infrahub/git/` (import-time closure builder). SDK changes live under `python_sdk/infrahub_sdk/schema/repository.py`. The closure builder is a new sub-package under `backend/infrahub/git/closure_builder/` because it is a cohesive component with two interchangeable implementations (Jinja2, Python) plus a shared canonicalizer — it satisfies the backend-component-design rule (Protocol-based, constructor-injected, single entry method per implementation). Schema changes live under `backend/infrahub/core/schema/definitions/core/transform.py` and trigger regeneration of `protocols.py` and the generated schema files.

## Complexity Tracking

No deviations from the constitution. No entries.

## Phase 0 / Phase 1 outputs

See:

- [research.md](./research.md) — open-question resolution, library-fit checks, fallback design.
- [data-model.md](./data-model.md) — schema additions, normalized path form, closure-result shape, SDK config shape.
- [contracts/watch-config.md](./contracts/watch-config.md) — `.infrahub.yml` `watch:` field schema.
- [contracts/pipeline-predicates.md](./contracts/pipeline-predicates.md) — pipeline-time predicate signatures and call-site replacement matrix.
- [quickstart.md](./quickstart.md) — end-to-end manual verification recipe.
