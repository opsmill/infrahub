# Implementation Plan: Definition Fingerprint Foundation

**Branch**: `definition-fingerprint-ifc-2844` | **Date**: 2026-07-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/ifc-2844-definition-fingerprint/spec.md`

## Summary

Add a nullable, branch-aware `fingerprint` `Text` attribute to `CoreGraphQLQuery`,
`CoreTransformation` (inherited by `CoreTransformPython` / `CoreTransformJinja2`),
`CoreArtifactDefinition`, and `CoreGeneratorDefinition`. During repository import,
compute each fingerprint as a deterministic content hash of the definition's
output-affecting inputs and write it through the standard SDK-over-GraphQL mutation
path (the importer is a Prefect worker with no direct DB access). Fingerprints are
layered (query -> transformation -> artifact definition; query -> generator
definition) and composed from a freshly-computed in-import snapshot so a dependent
definition never lags behind its inputs by an import. This ticket delivers **only the
foundation**: the schema fields, the computation, and the overwrite-on-every-import
storage. It wires up **no consumer** and changes **no runtime behaviour** on its own.

The governing invariant, inherited from INFP-409: **over-regeneration is acceptable;
under-regeneration is not.** Every fallback (null/unknown fingerprint, `watch` absent)
defaults toward regeneration - concretely, when `watch` is not declared the current
commit id is folded into the fingerprint so it changes on every commit.

## Technical Context

**Language/Version**: Python 3.14 (backend), plus a config-model touch in the Python SDK submodule (`python_sdk/`, Python 3.10-3.13)

**Primary Dependencies**: FastAPI, Prefect (import runs as a Prefect flow/tasks), `infrahub_sdk` (mutation path), GitPython (blob-SHA + commit resolution), Pydantic 2.12, `hashlib` (stdlib, SHA-256)

**Storage**: Neo4j graph via the standard node-update pipeline. Fingerprint is a normal branch-aware attribute; no new store, no direct-DB write from the importer.

**Testing**: pytest. Unit tests for the pure fingerprint composers and the blob-SHA resolver (`backend/tests/unit/git/...`); integration tests that import a fixture repo and assert on the stored `fingerprint` (`backend/tests/integration/git/...`), mirroring `test_generator_import_closure.py`.

**Target Platform**: Linux server (Infrahub backend + task worker)

**Project Type**: Web application backend (monorepo: `backend/` + `frontend/app/` + `python_sdk/` submodule). This feature is backend + a small SDK config change; the only frontend impact is regenerated GraphQL types.

**Performance Goals**: No regression to import time beyond hashing cost. Fingerprint reads git *metadata* (blob SHAs via the tree at the imported commit) - file contents are never read for hashing. Reuse the already-built dependency closure rather than rebuilding it.

**Constraints**: Deterministic and stable across processes and Infrahub versions (SHA-256 hex over canonicalised inputs). No consumer behaviour may change (FR-020). Importer holds no DB access - all writes go through the SDK. CI generated-file/doc validation must pass.

**Scale/Scope**: Four schema attributes; one new fingerprint-composition module; integration into the existing import flow (`git/integrator.py`) with a per-import fingerprint registry and dependency-ordered computation; regeneration of the schema/protocol/GraphQL/OpenAPI/frontend generated files; unit + integration tests; one changelog fragment.

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.0.0.*

- **I. Schema-Driven Integrity** - PASS. The `fingerprint` attribute is declared in the hand-authored core schema definitions and all generated files are regenerated (FR-023, SC-009). No generated file is hand-edited.
- **II. Branch-Safe by Default** - PASS. `fingerprint` uses `BranchSupportType.AWARE` (FR-003); it participates in branch diffs and survives rebase/merge as a normal branch-aware attribute, verified by SC-010. Merge behaviour is inherited from the attribute framework, not custom.
- **III. Type Safety & Explicit Contracts** - PASS. Fingerprint composers are typed, use frozen dataclasses for internal inputs, and the GraphQL/REST contracts are regenerated from the schema. The write goes through the generated SDK payload path.
- **IV. Test Discipline** - PASS. Pure composition logic gets fast unit tests; the import-and-store path and branch behaviour get integration tests reusing existing fixtures.
- **V. Query Performance & Efficiency** - PASS. No new Cypher. Fingerprint reads git metadata and reuses the existing closure. Writes reuse the standard node-update pipeline.
- **VI. Security & Input Boundaries** - PASS. No user input is interpolated anywhere; hashing is over content already validated at the config boundary. The attribute is writable (FR-004) by design; the desync risk is explicitly accepted in the spec and is no worse than other importer-managed fields.
- **VII. Simplicity & Maintainability** - PASS. Reuses the closure, the SDK mutation path, and stdlib hashing; adds no dependency. New logic is factored into small injectable components per `backend-component-design` (single entry point, constructor-injected collaborators).

**Result: PASS. No violations; Complexity Tracking is empty.**

*Re-check after Phase 1 design: still PASS - the design (Section: research.md decisions + data-model.md) introduces no schema migration beyond additive nullable attributes, no direct-DB write, and no consumer change.*

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2844-definition-fingerprint/
├── plan.md              # This file
├── research.md          # Phase 0: resolved design decisions
├── data-model.md        # Phase 1: schema fields + fingerprint composition model
├── quickstart.md        # Phase 1: validation scenarios
├── contracts/
│   └── fingerprint-composition.md   # Exact hashed inputs per definition kind
├── checklists/
│   └── requirements.md  # Pre-existing
└── tasks.md             # Phase 2 (/speckit-tasks - NOT created here)
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/schema/definitions/core/
│   ├── graphql_query.py       # + fingerprint Attr on CoreGraphQLQuery
│   ├── transform.py           # + fingerprint Attr on CoreTransformation (generic)
│   ├── artifact.py            # + fingerprint Attr on CoreArtifactDefinition
│   └── generator.py           # + fingerprint Attr on CoreGeneratorDefinition
├── core/schema/generated/     # REGENERATED (do not hand-edit)
├── core/protocols.py          # REGENERATED
├── git/
│   ├── integrator.py          # compute + pass fingerprint into SDK create/update payloads;
│   │                          #   dependency-ordered import with an in-import fingerprint registry
│   └── fingerprint/           # NEW module
│       ├── __init__.py
│       ├── composer.py        # layered composers: query / transformation / artifact-def / generator-def
│       ├── blob_resolver.py   # git tree -> {repo_relative_path: blob_sha} at the imported commit
│       └── registry.py        # per-import in-memory {definition-key: fingerprint} snapshot
└── ...

python_sdk/infrahub_sdk/schema/repository.py   # watch three-state confirmation (None vs present); no shape change expected

backend/tests/
├── unit/git/fingerprint/      # NEW: composer + blob_resolver + watch-state unit tests
└── integration/git/           # NEW: import-and-store + branch-diff integration tests
                               #   (mirror test_generator_import_closure.py)

schema/schema.graphql          # REGENERATED
schema/openapi.json            # REGENERATED
frontend/app/src/shared/api/graphql/generated/   # REGENERATED (pnpm codegen)

changelog/+ifc-2844.added.md   # NEW changelog fragment
```

**Structure Decision**: Backend web-application monorepo. Fingerprint logic lands in a new
`backend/infrahub/git/fingerprint/` package (small, injectable components) consumed by the
existing `git/integrator.py` import flow. Schema attributes are added in the four
hand-authored core definition files and propagated by the offline regeneration tasks. The
only frontend and SDK touches are regenerated types and confirming the SDK watch config
already distinguishes the required states.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
