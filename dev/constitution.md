<!--
Sync Impact Report
===================
Version change: 0.0.0 (unfilled template) → 1.0.0
Modified principles: N/A (initial constitution)
Added sections:
  - I. Schema-Driven Integrity
  - II. Branch-Safe by Default
  - III. Type Safety & Explicit Contracts
  - IV. Test Discipline
  - V. Query Performance & Efficiency
  - VI. Security & Input Boundaries
  - VII. Simplicity & Maintainability
  - Security & Performance Standards
  - Development Workflow & Quality Gates
  - Governance
Removed sections: None
Templates requiring updates:
  - .specify/templates/plan-template.md — Constitution Check placeholder
    now has concrete gates to reference ✅ (no file edit needed;
    plan-template instructs to derive gates from this file at plan time)
  - .specify/templates/spec-template.md — ✅ compatible (functional
    requirements and success criteria align with principles)
  - .specify/templates/tasks-template.md — ✅ compatible (phase structure
    supports test-first and security-hardening tasks)
Follow-up TODOs: None
-->

# Infrahub Constitution

## Core Principles

### I. Schema-Driven Integrity

All data in Infrahub is governed by schemas. Every node, attribute,
relationship, and constraint MUST be defined in the schema layer before
it can exist in the database.

- Schema definitions are the single source of truth for data structure.
- All writes MUST validate against the active schema for the target
  branch and point in time.
- Schema migrations MUST preserve data integrity: constraints, unique
  indexes, and relationship cardinality MUST be enforced before, during,
  and after migration.
- Generated files (`backend/infrahub/core/schema/generated/`,
  `backend/infrahub/core/protocols.py`, `frontend/app/src/shared/api/`)
  MUST NOT be edited manually; they MUST be regenerated from schemas.

**Rationale:** Infrahub's value proposition is reliable infrastructure
data. Bypassing the schema layer risks silent data corruption that
propagates across branches and downstream consumers.

### II. Branch-Safe by Default

Every feature MUST operate correctly across Infrahub's branching and
temporal model. Code MUST NOT assume it runs only on the default branch.

- All database queries MUST include branch and temporal filters as
  defined in the database schema documentation.
- Edge activity MUST be resolved using the priority ordering:
  `branch_level DESC, from DESC, status ASC`.
- Cross-branch side effects (e.g., modifying branch-agnostic nodes)
  MUST be explicitly documented and tested.
- Merge behavior for new features MUST be specified and tested before
  the feature is considered complete.
- Soft-delete semantics MUST be used; hard-delete is permitted only for
  branch deletion itself.

**Rationale:** Infrahub's Git-like branching for infrastructure data is
a core differentiator. Branch-unsafe code silently corrupts data across
all branches and breaks the version-control guarantee.

### III. Type Safety & Explicit Contracts

All code MUST use the type system to enforce correctness at boundaries.

- **Python backend:** All function parameters and return types MUST
  carry type hints. Use `str | None` (not `Optional[str]`). Prefer
  frozen dataclasses for internal data; Pydantic models for API
  boundaries. Avoid untyped dictionaries for structured data.
- **TypeScript frontend:** `any` is forbidden; use `unknown` with type
  guards. Non-null assertions (`!`) and type assertions (`as`) MUST be
  replaced with proper null checks or type guards.
- **Query results:** All database queries MUST expose results through
  frozen dataclass `get_data()` methods, never raw Neo4j records.
- **APIs:** GraphQL and REST contracts MUST be defined before
  implementation. Generated types MUST be used by consumers.

**Rationale:** Infrastructure data management requires high confidence
in correctness. Loose typing hides errors that surface as silent data
corruption in production.

### IV. Test Discipline

Every feature MUST include tests at the appropriate level. Tests MUST
be written before or alongside implementation, not deferred.

- **Unit tests** (`tests/unit/`): Pure logic, no external services, no
  database. MUST run in seconds.
- **Component tests** (`tests/component/`): Small scope, may use
  database via TestContainers.
- **Functional tests** (`tests/functional/`): Multi-component, single
  process, async tasks inline. Preferred for features spanning multiple
  layers.
- **Integration Docker tests** (`tests/integration_docker/`): Full
  distributed stack. Required for features involving computed attributes,
  triggered actions, or schema migrations.
- **Frontend unit tests**: Vitest for pure logic, utilities, and React
  hooks. MUST run in seconds.
- **Frontend E2E tests** (`frontend/app/tests/e2e/`): Playwright tests
  MUST be included for all user-facing features. Feature implementation
  is not complete until E2E tests pass.
- Prefer adapter/protocol patterns over mocking. Mocks are acceptable
  only for external HTTP APIs with no test mode or time-dependent
  behavior.
- Test files MUST mirror source structure.
- Existing schema fixtures MUST be reused; new inline schemas are
  permitted only when no existing fixture suffices.

**Rationale:** Infrahub manages critical infrastructure data. Untested
code paths risk data loss or corruption that may not be detected until
a production merge or deployment.

### V. Query Performance & Efficiency

Database queries MUST be designed for efficiency from the start, not
optimized later.

- All queries MUST be parameterized (`$param` syntax); string
  interpolation of user input into Cypher is forbidden.
- Queries MUST return only the specific properties needed, never entire
  nodes or relationships.
- N+1 query patterns MUST be avoided; batch queries MUST be used when
  operating on multiple nodes.
- Memory footprint MUST be considered: large result sets MUST use
  pagination or streaming.
- Performance-sensitive paths SHOULD include benchmark tests.
- `EXPLAIN` SHOULD be used during development to validate query plans
  for new or modified queries.

**Rationale:** Neo4j graph traversals can exhibit non-linear cost growth.
Inefficient queries under load degrade the entire system and are
expensive to fix retroactively.

### VI. Security & Input Boundaries

Security MUST be enforced at system boundaries. Internal code may trust
validated data flowing through established interfaces.

- All user input entering via REST, GraphQL, or configuration MUST be
  validated and sanitized before use.
- Cypher queries MUST use parameter binding; string interpolation is
  forbidden (prevents Cypher injection).
- Authentication MUST be required for all mutating operations.
  Authorization MUST be checked at the API layer.
- Secrets, API keys, and credentials MUST NOT be committed to the
  repository. Files matching `.env`, `credentials.*`, and similar
  patterns MUST be in `.gitignore`.
- Error messages returned to users MUST NOT expose internal
  implementation details, stack traces, or database structure.
- Dependencies MUST be reviewed before addition and kept updated to
  address known vulnerabilities.

**Rationale:** Infrahub manages network infrastructure data. A security
breach could expose or corrupt an organization's entire infrastructure
topology.

### VII. Simplicity & Maintainability

Prefer the simplest solution that satisfies requirements. Complexity
MUST be justified.

- YAGNI: Do not implement features, abstractions, or configurability
  for hypothetical future requirements.
- Three similar lines of code are preferable to a premature abstraction.
- Helpers, utilities, and shared abstractions MUST serve at least two
  existing callers before extraction.
- New dependencies MUST be justified; prefer stdlib or existing
  dependencies over new ones.
- Follow established project patterns (Query classes, adapter pattern,
  Feature-Sliced architecture) rather than introducing alternative
  patterns for the same problem.
- Async-first for all backend I/O. Keyword arguments for all function
  calls (except single-arg stdlib functions).
- Generated files MUST be regenerated, never hand-edited.

**Rationale:** Infrahub is a large codebase spanning backend, frontend,
SDK, and documentation. Unnecessary complexity compounds maintenance
cost and onboarding time.

## Security & Performance Standards

### Security Requirements

- **Input validation:** Pydantic models at API boundaries enforce
  structure, types, and constraints before data reaches business logic.
- **Injection prevention:** All database queries use parameterized
  Cypher (`$param`). No dynamic query construction from user input.
- **Access control:** Role-based access control at the API layer.
  Branch-specific permissions where applicable.
- **Audit trail:** Node and edge metadata (`created_by`, `updated_by`,
  `created_at`, `updated_at`) MUST be maintained for all mutations on
  default/global branches.
- **Dependency management:** `uv` for Python, `npm` for frontend.
  Dependency additions require review. Known vulnerability patches
  MUST be applied promptly.

### Performance Standards

- **Query efficiency:** Return only required properties. Batch
  operations over iteration. Use indexes for frequent lookups.
- **Memory management:** Stream or paginate large result sets. Avoid
  loading entire datasets into memory.
- **Benchmark tracking:** `pytest-benchmark` with CodSpeed CI for
  performance regression detection. Query benchmarks in
  `tests/query_benchmark/`.
- **Frontend performance:** Code splitting, lazy loading, and
  virtualization for large lists. Bundle size monitored.

## Development Workflow & Quality Gates

### Code Quality Gates

All code MUST pass these gates before merge:

1. **Formatting:** `uv run invoke format` (Python), `npm run biome:fix`
   (frontend). No unformatted code in PRs.
2. **Linting:** `uv run invoke lint` (ruff + mypy for Python),
   Biome for TypeScript. Zero lint errors.
3. **Type checking:** mypy for Python, TypeScript strict mode for
   frontend. No `type: ignore` without justification.
4. **Tests:** All existing tests MUST pass. New features MUST include
   tests. Test level chosen per Test Discipline principle.
5. **Changelog:** Every user-facing change MUST include a Towncrier
   changelog fragment in `changelog/`.

### Git Workflow

- Main branches: `stable` (production), `develop` (integration),
  `release-*` (releases).
- Feature branches from `develop`, merged via PR.
- Conventional commit format: `<type>: <description> [<issue>]`.
- Never force push to `stable` or `develop`.
- Submodule (`python_sdk`) updates MUST be explicit commits.

### Documentation Requirements

- New features MUST be documented in `docs/` for users.
- Backend architecture changes MUST update `dev/knowledge/backend/`.
- Frontend architecture changes MUST update `dev/knowledge/frontend/`.
- API changes MUST regenerate schemas (`uv run invoke backend.generate`,
  `npm run codegen`).

## Governance

This constitution is the authoritative reference for development
standards in the Infrahub project. It supersedes informal practices
and ad-hoc decisions.

- **Compliance:** All pull requests and code reviews MUST verify
  adherence to these principles. Reviewers SHOULD reference specific
  principle numbers (e.g., "Principle III violation") when requesting
  changes.
- **Amendments:** Changes to this constitution require:
  1. A written proposal describing the change and rationale.
  2. Review and approval by a project maintainer.
  3. A migration plan if the change affects existing code.
  4. Version increment following semantic versioning (see below).
- **Versioning:**
  - MAJOR: Principle removal, redefinition, or backward-incompatible
    governance change.
  - MINOR: New principle or materially expanded guidance.
  - PATCH: Clarifications, wording fixes, non-semantic refinements.
- **Complexity justification:** Any deviation from Principle VII
  (Simplicity) MUST be documented in the relevant plan or PR with a
  rationale for why the simpler alternative was insufficient.
- **Runtime guidance:** Coding standards in `dev/guidelines/` and
  architecture knowledge in `dev/knowledge/` provide detailed
  implementation guidance aligned with these principles.

**Version**: 1.0.0 | **Ratified**: 2026-02-16 | **Last Amended**: 2026-02-16
