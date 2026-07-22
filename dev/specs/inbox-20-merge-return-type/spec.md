# Feature Specification: Correct merge()/rebase() return-type annotations

**Feature Branch**: `pha/INBOX-20`

**Created**: 2026-07-22

**Status**: Draft

**Input**: Correct the return-type annotations of `InfrahubRepository.merge()` and `InfrahubRepository.rebase()` in `backend/infrahub/git/repository.py` so they no longer lie about their contract.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Callers and the type checker see the true return contract (Priority: P1)

A developer — or the static type checker acting on their behalf — calls `InfrahubRepository.merge()` or `InfrahubRepository.rebase()` and relies on the declared return type to reason about the result. Today the annotation says `bool`, but the methods actually return the new commit-hash **string** on a successful merge and `False` on a no-op (nothing to merge). The developer is misled: a legitimate `isinstance(result, str)` check looks dead, and code that treats the result as a plain boolean is never flagged.

After this change the annotation states the real contract, so the type checker both accepts the two real return paths and flags any caller that assumes a plain boolean.

**Why this priority**: This is the entire feature — a single, self-contained type-correctness fix. There is no smaller viable slice.

**Independent Test**: Run the project's static type gate against the git module and confirm the corrected annotation introduces no new type errors and reads `str | Literal[False]`; run the git component tests and confirm they still pass (runtime behavior unchanged).

**Acceptance Scenarios**:

1. **Given** the corrected annotation, **When** the type checker analyzes `merge()`/`rebase()`, **Then** both the success path (`return str(commit_after)`) and the no-op path (`return False`) satisfy the declared return type with no type errors.
2. **Given** the corrected annotation, **When** the type checker analyzes callers, **Then** any code assigning the result to a `bool` (or otherwise assuming a plain boolean) is flagged; if no such caller exists, the type gate stays green.
3. **Given** the change is annotation-only, **When** the git component test suite runs, **Then** all tests pass with identical runtime behavior (a commit-hash string on success, `False` on no-op).

### Edge Cases

- **No-op merge** (source already contained in destination): still returns `False`; the `Literal[False]` arm of the union covers it exactly.
- **Existing truthiness callers** (`if await repo.merge(...)`): runtime behavior is unchanged — a non-empty commit-hash string is truthy and `False` is falsy — so there is no behavioral regression; only the static type is corrected.
- **`rebase()` delegation**: `rebase()` returns exactly what `merge()` returns, so its declared type must stay in lock-step with `merge()`'s.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The return annotation of `InfrahubRepository.merge()` MUST declare its real contract — a commit-hash `str` on a successful merge and `False` on a no-op — expressed as `str | Literal[False]`.
- **FR-002**: The return annotation of `InfrahubRepository.rebase()` MUST match what it returns (`str | Literal[False]`), since its body only delegates to `merge()`.
- **FR-003**: The change MUST be annotation-only. Runtime behavior and control flow MUST be unchanged; the existing `return False` and `return str(commit_after)` statements MUST remain functionally identical.
- **FR-004**: `Literal` MUST be available in the module (added to the existing `typing` import if not already present).
- **FR-005**: Any caller the static type gate now flags as assuming a plain `bool` MUST be reconciled minimally and faithfully — preferring `isinstance(result, str)` narrowing consistent with the module's existing pull()-result consumers — with no behavioral change.
- **FR-006**: A changelog fragment under `changelog/` MUST record the internal type-correctness fix. The fragment body MUST NOT reference the tracking ticket key.

### Key Entities *(include if feature involves data)*

- **Merge/rebase result**: the new commit hash (string) when the operation advanced the destination branch, or `False` when the operation was a no-op.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The static type gate passes with the corrected annotation — zero new type errors introduced. (Note: `infrahub.git.repository` runs under a mypy override that suppresses `return-value`, so a green gate for this module does not by itself prove the lie is fixed; the corrected annotation's enforcement value accrues to callers in other modules and to human readers, and it makes a future removal of that suppression meaningful.)
- **SC-002**: The `merge()` and `rebase()` return annotations read `str | Literal[False]` (verifiable by inspection).
- **SC-003**: 100% of the git component tests (`backend/tests/component/git/test_git_repository.py`) pass, confirming unchanged runtime behavior.
- **SC-004**: The change set is confined to `backend/infrahub/git/repository.py` plus a `changelog/` fragment (and, only if strictly required by the type gate, minimal caller reconciliation) — with no changes to database schema, migrations, API contracts, authentication, dependencies, CI workflows, or generated files.

## Assumptions

- The only production caller of `merge()` discards its return value, and `rebase()` has no production callers, so no production-caller reconciliation is expected — to be confirmed by the type gate rather than assumed.
- `str | Literal[False]` is the preferred annotation form: it matches the actual `return False` / `return str(...)` statements and the source SOLID analysis's recommendation. The looser `str | bool` is deliberately not used.
- `backend/infrahub/git/repository.py` is type-checked, but under a mypy override that disables `return-value` / `arg-type` / `assignment` / `call-overload`; the corrected annotation is therefore enforced primarily at external call sites and read by humans. Removing that suppression is a separate mypy-burndown item and is out of scope here.
- No new tests are strictly required for an annotation-only change; the existing git component tests are the behavioral guard. A focused assertion may be added only if it clarifies the contract, and never references the tracking ticket.
