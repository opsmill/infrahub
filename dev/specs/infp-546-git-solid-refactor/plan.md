# Implementation Plan: SOLID Restructuring of `infrahub.git`

**Branch**: `git-solid-refactor-infp-546` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `dev/specs/infp-546-git-solid-refactor/spec.md`

## Summary

The `infrahub.git` module has degraded into two very large classes joined by an inheritance chain (`InfrahubRepositoryBase` 1,161 lines, `InfrahubRepositoryIntegrator` 1,538 lines, plus `InfrahubRepository` / `InfrahubReadOnlyRepository` in `repository.py`). Five distinct responsibilities (config parsing, file discovery, object lifecycle, artifact rendering, dynamic Python loading) sit on one class; Prefect workflow decorators fuse to business methods preventing unit tests without engine setup; global mutable state (`registry.default_branch`, `get_client()`) is reached from inside read accessors; type-checker overrides in `pyproject.toml:358-374` carry a "temporary" comment with nothing forcing follow-up.

This plan delivers a six-story refactor that is **strictly behavior-preserving** (FR-014) and **strictly additive-then-subtractive** (Guiding Constraint 7). Story 1 lands a real-remote safety net (Gogs container) covering six scenario families. Stories 2–6 introduce protocols, extract a `RepositoryFileImporter` collaborator, split Prefect-decorated methods into private `_impl` + public wrapper pairs, and make global dependencies (default branch, SDK client) substitutable at construction time. Every PR is independently mergeable AND revertable (FR-011, FR-012), addresses at most one concern (FR-017), and removes any type-checker suppression it obsoletes in the same change (FR-019). No new public name is removed or renamed (FR-013); no new runtime dependency or DB schema change (FR-015).

The primary deliverables of this *plan* command are: this file, `research.md` (current-state survey + decisions), `data-model.md` (new code entities), `contracts/*.md` (public surface, protocols, importer, error registry, workflow split), and `quickstart.md` (forward-looking developer flow). `/speckit-tasks` will produce the per-story task list next.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: Pydantic 2.10, GitPython (existing), Prefect (existing — workflow decorators), `infrahub_sdk` (existing client), pytest 9.0
**Storage**: N/A — no database schema or persisted-data change (FR-015). Module operates on a local checkout under `repositories/<id>/` and a remote Git server.
**Testing**: pytest 9.0 with `pytest-asyncio`; existing `backend/tests/unit/git/` (3 files) and `backend/tests/integration/git/` (6 files incl. `conftest.py` Gogs fixture at lines 129-202). Story 1 adds one file per scenario family to the integration directory; Stories 2–5 add unit tests directly against extracted collaborators and `_impl` methods.
**Target Platform**: Linux/macOS dev hosts; production runs in containers behind the existing Infrahub stack. No platform-specific code added.
**Project Type**: Backend internal module within the Infrahub monorepo (single project under `backend/`).
**Performance Goals**: No detectable regression. Each new collaborator hop is one attribute lookup + one function call on a path not in any tight inner loop (spec Assumptions §"No detectable performance regression"). If a regression is observed during the work, it is investigated and either fixed or documented before the next PR lands.
**Constraints**:
- **Behavior preservation (FR-014)**: same return values, exception types, exception message strings, logger names, and stack-trace module paths for every public method.
- **Public import-surface preservation (FR-013)**: every name currently importable from `infrahub.git.{repository,base,integrator,tasks,models,utils}` remains importable.
- **Per-PR concern bound (FR-017)**: at most one collaborator boundary, one moved method, one correctness contract, one new protocol, or one scenario family of tests per PR.
- **Type-checker suppression invariant (FR-018, FR-019)**: union of suppressed `(module, error-code)` cells never grows; obsoleted suppressions are removed in the same PR; no new inline `# type: ignore` introduced.
- **Workflow-engine fidelity (FR-021)**: in-process callers (including recursive self-calls) go through the decorated wrapper, not the private `_impl` — preserves retry, checkpointing, telemetry, logging.
- **Delegate purity (FR-016, FR-023)**: moved methods leave a delegate whose body is exactly one expression (`return await self.x.y(...)`); no two divergent implementations of the same logical operation ever co-exist.
- **No new runtime deps / no schema or migration changes (FR-015).**

**Scale/Scope**: ~3,000 lines of Python in `backend/infrahub/git/`, the most heavily-imported backend module. Six user stories produce roughly: Story 1 = 6 PRs (one per scenario family); Story 2 = 3 PRs; Story 3 ≥ 2 PRs; Story 4 ≈ 1 + 7 + 1 PRs (empty importer + per-handler + cleanup); Story 5 = 17 PRs (one per decorated method); Story 6 = 2 PRs. Total ≈ 38 PRs, each reviewable end-to-end in a single sitting (SC-008).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This refactor touches backend code only (no frontend, no schema, no UI). Frontend principles and Shared Components Inventory sections are not applicable.

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | PASS | No schema change. No edit to generated files (`backend/infrahub/core/schema/generated/`, `protocols.py`). |
| II. Branch-Safe by Default | PASS | Module operates on the repository abstraction, not the Neo4j branch/temporal layer. Behavior preservation (FR-014) means existing branch handling is unchanged. |
| III. Type Safety & Explicit Contracts | PASS — STRENGTHENED | Story 2 fixes the merge return-type contract (FR-003); Story 3 introduces typed `Protocol` consumers (FR-006); Story 5 removes 13 inline `# type: ignore[call-overload]` markers as wrappers split (FR-019). The mypy/ty per-module override list never grows (FR-018). |
| IV. Test Discipline | PASS — STRENGTHENED | Story 1 lands the real-remote safety net as a prerequisite to every structural change. Stories 2–5 each ship pinning tests in the same PR that lands the change (FR-022). Mocks that become structurally unnecessary are removed in the PR that obsoletes them; the residue is enumerated in an audit document (SC-010). |
| V. Query Performance & Efficiency | PASS | Not applicable directly — this module does not own Cypher queries. Behavior preservation ensures any existing query patterns are kept. |
| VI. Security & Input Boundaries | PASS | No change to authentication/authorization or input parsing at the API boundary. The error-pattern registry (Story 2, FR-005) reads `error.stderr` from `GitCommandError` — same source as today; the registry does not relax sanitization. |
| VII. Simplicity & Maintainability | PASS — IMPROVED | Each story directly reduces complexity: SRP split (Story 4), open/closed for new object types (Story 4), substitutable globals (Story 6), removed inheritance-overload type confusion (Story 3). YAGNI: no abstraction is introduced that does not have a concrete in-tree caller in the same PR (FR-017). |

**Code Quality Gates check:**

- Formatting & linting: every PR runs `uv run invoke format` and `uv run invoke lint`. The ruff and mypy pre-commit hooks are not bypassed.
- Type checking: mypy/ty config is owned by `pyproject.toml`. FR-018 + FR-019 govern any change to it.
- Tests: each PR runs the relevant unit + integration suites. Story 1's expanded integration suite is wired into the CI configuration that gates merges to `develop` (FR-002, SC-005).
- Changelog: spec §Assumptions specifies one towncrier fragment produced at the close of all stories, not per-PR.

**Gate verdict: PASS.** No violations to track in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-546-git-solid-refactor/
├── plan.md                          # This file
├── research.md                      # Phase 0 — current-state survey + decisions
├── data-model.md                    # Phase 1 — new code entities (protocols, importer, registry, split)
├── quickstart.md                    # Phase 1 — forward-looking developer flow
├── contracts/                       # Phase 1 — contracts
│   ├── public-import-surface.md       (FR-013)
│   ├── protocols.md                   (FR-006, Story 3)
│   ├── file-importer.md               (FR-007, Story 4)
│   ├── error-registry.md              (FR-005, Story 2)
│   └── workflow-split.md              (FR-008, FR-021, Story 5)
├── spec.md                          # Input feature specification
└── tasks.md                         # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/infrahub/git/                # KEEP: all today's public modules stay importable (FR-013)
├── __init__.py                        # unchanged exports
├── base.py                            # InfrahubRepositoryBase — shrinks as collaborators are extracted
├── constants.py                       # unchanged
├── directory.py                       # unchanged
├── integrator.py                      # InfrahubRepositoryIntegrator — body splits per Story 4 + Story 5
├── models.py                          # unchanged
├── repository.py                      # InfrahubRepository, InfrahubReadOnlyRepository; protocol re-exports (Story 3)
├── tasks.py                           # unchanged unless a Story 5 wrapper moves here with FR-013 preserved
├── utils.py                           # unchanged
├── worktree.py                        # unchanged
├── protocols.py                       # NEW — Story 3 (ReadOnlyRepositoryProtocol, RepositoryProtocol)
├── errors.py                          # NEW — Story 2 (ErrorRule, ERROR_RULES, raise_enriched)
└── importer/                          # NEW — Story 4
    ├── __init__.py                      # RepositoryFileImporter, FileImportHandler protocol, DiscoveredFile
    ├── schema.py                        # SchemaFileHandler (replaces import_schema_files body)
    ├── graphql_query.py                 # GraphqlQueryHandler
    ├── python_check.py                  # PythonCheckHandler
    ├── generator.py                     # GeneratorHandler
    ├── python_transform.py              # PythonTransformHandler
    ├── jinja2_transform.py              # Jinja2TransformHandler
    └── artifact_definition.py           # ArtifactDefinitionHandler

backend/tests/unit/git/                # ADD per Story 5 (one per decorated _impl)
├── test_delete_git_branch.py          # existing
├── test_git_repository.py             # existing
├── test_transform_python_information.py  # existing
├── test_errors.py                     # NEW — Story 2 (error registry)
├── test_protocols.py                  # NEW — Story 3 (structural typing checks)
├── test_importer.py                   # NEW — Story 4 (collaborator round-trip)
├── test_<handler>.py × 7              # NEW — Story 4 (per-handler unit tests)
├── test_<impl>.py × 17                # NEW — Story 5 (per workflow-decorated method)
└── test_constructor_injection.py      # NEW — Story 6 (default-branch + SDK client)

backend/tests/integration/git/         # ADD per Story 1 (one per scenario family)
├── conftest.py                        # existing (Gogs fixture)
├── test_git_repository.py             # existing
├── test_git_live_remote.py            # existing
├── test_delete_git_branch_gogs.py     # existing
├── test_readonly_repository.py        # existing
├── test_repository.py                 # existing
├── test_repository_branch.py          # existing
├── utils.py                           # existing
├── test_auth_and_access.py            # NEW — Story 1 family 1
├── test_push_failures.py              # NEW — Story 1 family 2
├── test_merge_scenarios.py            # NEW — Story 1 family 3
├── test_readonly_repository_real.py   # NEW — Story 1 family 4
├── test_repository_setup.py           # NEW — Story 1 family 5
├── test_sync_mismatches.py            # NEW — Story 1 family 6
└── test_readonly_get_commit_value.py  # NEW — Story 2 (FR-004 pinning test)

pyproject.toml                        # mypy/ty overrides narrowed per FR-018, FR-019; no growth
```

**Structure Decision**: Single-project layout under `backend/infrahub/git/`. New collaborators land as **siblings** (`protocols.py`, `errors.py`) or a **subpackage** (`importer/`). No top-level rename of any existing module — FR-013 keeps all current import paths working. The `importer/` subpackage is the only nesting introduced; it earns its weight because Story 4 adds one new file per built-in handler (seven today), and the OCP improvement requires per-handler files for new types to land independently.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified.**

No violations — Constitution Check passed. This section is intentionally empty.
