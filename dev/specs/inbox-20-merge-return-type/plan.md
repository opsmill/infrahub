# Implementation Plan: Correct merge()/rebase() return-type annotations

**Branch**: `pha/INBOX-20` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `dev/specs/inbox-20-merge-return-type/spec.md`

## Summary

`InfrahubRepository.merge()` and `InfrahubRepository.rebase()` in
`backend/infrahub/git/repository.py` are annotated `-> bool` but actually return the new
commit-hash `str` on success and `False` on a no-op. Correct both annotations to
`str | Literal[False]` (annotation-only, no runtime change), add the `Literal` import if missing,
reconcile any bool-assuming caller the type gate flags (none expected in production), and add a
changelog fragment. Verify via the static type gate and the git component tests.

## Technical Context

**Language/Version**: Python 3.14 (backend)

**Primary Dependencies**: none new — GitPython/Pydantic already present; only `typing.Literal` (stdlib)

**Storage**: N/A (no persistence change)

**Testing**: pytest — `backend/tests/component/git/test_git_repository.py`; static gate: mypy + ruff via `uv run invoke backend.lint` / `/pre-ci`

**Target Platform**: Linux server (backend service)

**Project Type**: Web-service backend (single-repo change in `opsmill/infrahub`)

**Performance Goals**: N/A — no runtime behavior change

**Constraints**: Annotation-only; no DB schema/migration, GraphQL/REST contract, auth, dependency, CI-workflow, or generated-file changes. No ticket/issue IDs in code, docstrings, comments, or test names (`.agents/rules/code-doc-style.md`).

**Scale/Scope**: Two method annotations in one file, one `typing` import, one changelog fragment; caller reconciliation only if the type gate strictly requires it.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **III. Type Safety & Explicit Contracts** — ✅ **Directly advanced.** The change makes the
  declared return type match the true contract, restoring meaningful type-checking for callers.
  This is the constitutional principle the feature exists to serve.
- **I. Schema-Driven Integrity** — ✅ No schema and no generated files are touched.
- **II. Branch-Safe by Default** — ✅ No query, branching, or temporal logic changes; behavior is
  byte-for-byte unchanged.
- **IV. Test Discipline** — ✅ Existing git component tests are the behavioral guard for an
  annotation-only change; they must remain green. No new user-facing behavior to test.
- **V. Query Performance & Efficiency** — ✅ N/A (no queries changed).
- **VI. Security & Input Boundaries** — ✅ N/A (no boundary, auth, or input handling changed).
- **VII. Simplicity & Maintainability** — ✅ Minimal, bounded change; removes a type lie rather
  than adding abstraction.

**Verdict: PASS.** No violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
dev/specs/inbox-20-merge-return-type/
├── spec.md              # Specify output
├── plan.md              # This file
├── research.md          # Phase 0 output (annotation-form + caller analysis)
├── quickstart.md        # Phase 1 output (verification guide)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

`data-model.md` and `contracts/` are **N/A** for this feature: it introduces no data entities and
changes no external interface (the two methods are internal; their runtime signature and behavior
are unchanged — only the *declared* return type is corrected). No files are created for them.

### Source Code (repository root)

```text
backend/infrahub/git/repository.py     # merge() and rebase() return annotations (+ Literal import)
changelog/                             # new changelog fragment (internal type-correctness fix)
```

**Structure Decision**: Single-repo backend change. The entire behavioral surface lives in one
module (`backend/infrahub/git/repository.py`); the only other artifact is a changelog fragment.
No caller edits are anticipated (the sole production `merge()` caller discards its result and
`rebase()` has no production callers), but the type gate is the authority — any site it flags is
reconciled minimally with `isinstance(result, str)` narrowing.

## Complexity Tracking

> Not applicable — Constitution Check passed with no violations.
