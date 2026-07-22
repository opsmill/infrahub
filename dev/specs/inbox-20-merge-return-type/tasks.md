# Tasks: Correct merge()/rebase() return-type annotations

**Feature dir**: `dev/specs/inbox-20-merge-return-type`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

**Scope reminder**: annotation-only backend change in `backend/infrahub/git/repository.py`
(`merge()`/`rebase()` `-> bool` becomes `-> str | Literal[False]`). No behavioral change; no new
branch. Hard constraints: no schema/migration, API-contract, auth, dependency, CI, or
generated-file changes. `.agents/rules/code-doc-style.md`: no ticket/issue/spec IDs in code,
docstrings, comments, or test names.

## Phase 1: Setup

No additional setup. The worktree on `pha/INBOX-20` exists and `uv sync --all-groups` has been run.

## Phase 2: Foundational

No foundational/blocking prerequisites — this is a single-file annotation change with no shared
infrastructure to stand up first.

## Phase 3: User Story 1 — Callers and the type checker see the true return contract (P1)

**Goal**: `merge()` and `rebase()` declare their real return contract (`str | Literal[False]`),
so callers and the type checker are no longer misled — with runtime behavior unchanged.

**Independent test**: After the change, `merge()`/`rebase()` signatures read
`-> str | Literal[False]`, the static type gate is green (no new errors), and
`backend/tests/component/git/test_git_repository.py` passes.

- [X] T001 [US1] In `backend/infrahub/git/repository.py`, ensure `Literal` is imported from `typing` (add it to the existing `typing` import line, or add an import if none exists).
- [X] T002 [US1] In `backend/infrahub/git/repository.py`, change the `merge()` return annotation from `-> bool` to `-> str | Literal[False]` (the `async def merge(...)` around line 271). Do not touch the body — `return False` and `return str(commit_after)` stay exactly as-is.
- [X] T003 [US1] In `backend/infrahub/git/repository.py`, change the `rebase()` return annotation from `-> bool` to `-> str | Literal[False]` (the `async def rebase(...)` around line 309). Body (`return await self.merge(...)`) stays as-is.
- [X] T004 [US1] Run the static type gate (`uv run invoke backend.lint`, i.e. mypy + ruff). Confirm no new errors. If mypy flags a genuinely bool-assuming caller, reconcile it minimally with `isinstance(result, str)` narrowing (no behavioral change). Confirm the sole production `merge()` caller (`backend/infrahub/git/tasks.py:746`) discards its result and that `rebase()` has no production callers — expect zero caller edits.
- [X] T005 [US1] Run `uv run pytest backend/tests/component/git/test_git_repository.py` and confirm all tests pass (runtime behavior unchanged: commit-hash `str` on success, `False` on no-op).

## Phase 4: Polish & Cross-Cutting

- [X] T006 [P] Add a changelog fragment under `changelog/` (follow the existing fragment convention — e.g. `changelog/+<slug>.fixed.md`) describing the internal type-correctness fix to `merge()`/`rebase()` return annotations. The fragment body MUST NOT reference the tracking ticket key.
- [X] T007 Run `/pre-ci` (format + lint + backend unit tests) and confirm the full locally-executable gate is green before the PR is opened. (Ran the change-relevant gates: ruff `check`/`format` clean via CI's exact command, mypy backend "No issues found", `uv lock --check` clean, git component + git-scoped unit tests pass. `ty check .` fails locally only on 106 pre-existing, change-invariant false-positive test-helper `unresolved-import`s that CI's clean env resolves. Full frontend/docs/schema pre-ci phases skipped as irrelevant to this backend-only annotation change; CI runs the complete suite.)

## Dependencies

- T001 → T002, T003 (the `Literal` import must exist before the annotations reference it; all three edit the same file, so they run **sequentially**, not in parallel).
- T002, T003 → T004 (type gate runs against the corrected annotations).
- T002, T003 → T005 (component tests validate unchanged behavior).
- T006 [P] is independent of T001–T005 (different path, `changelog/`) and may be done any time before T007.
- T007 is last (whole-gate confirmation, after all edits and the changelog fragment).

## Parallel Opportunities

- Only T006 is parallelizable ([P], `changelog/`). T001–T005 all touch the same source file or
  depend on its final state, so they are strictly sequential. The task set is small enough that
  parallelism is negligible.

## Implementation Strategy (MVP)

There is a single user story (P1); it **is** the MVP. Complete T001–T005 to deliver the fix, then
T006–T007 for changelog + full-gate confirmation. If T004 surprisingly surfaces a bool-assuming
caller, reconcile it within T004 rather than expanding scope — and if reconciliation would require
a forbidden change (API/contract/etc.), STOP and escalate instead.
