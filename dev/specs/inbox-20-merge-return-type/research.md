# Research: merge()/rebase() return-type correction

## Decision 1 — Annotation form

**Decision**: Annotate both `merge()` and `rebase()` as `str | Literal[False]`.

**Rationale**: The success path executes `return str(commit_after)` (a commit-hash string) and the
no-op early-exit executes `return False`. `str | Literal[False]` is the exact union of the two real
return values, so it is annotation-only — it requires zero change to the return statements or
control flow. It also lets the type checker discriminate the two arms (`isinstance(x, str)` narrows
to success; the remaining arm is `Literal[False]`).

**Alternatives considered**:
- `str | bool` — looser: it would admit `True`, which the method never returns, weakening the
  contract for callers. Rejected.
- `str | None` — would force changing `return False` to `return None`, i.e. a behavioral/semantic
  change to the no-op path and to any truthiness-based caller. Out of scope (annotation-only).
  Rejected.

The source SOLID analysis (Confluence "Infrahub Git refactoring 26Q2", §9 recommendations)
explicitly suggests `str | Literal[False]`, corroborating this choice.

## Decision 2 — Caller reconciliation strategy

**Decision**: Change the annotations first, then let the static type gate (mypy) enumerate any
caller that assumed a plain `bool`. Fix only what it flags, using `isinstance(result, str)`
narrowing.

**Rationale**: A source sweep shows:
- The only **production** caller of `InfrahubRepository.merge()` is in
  `backend/infrahub/git/tasks.py` (the repository-merge flow), and it **discards** the return value
  (`await repo.merge(...)` as a statement) — so the corrected type cannot break it.
- `InfrahubRepository.rebase()` has **no production callers** (matches on `.rebase(` elsewhere are a
  different `Branch.rebase(db=...)` method and internal git-CLI calls).
- The module already consumes similarly-typed results (from `pull()`) via `isinstance(commit_after,
  str)` at `repository.py:214` and `:240`, so that is the idiomatic narrowing pattern to mirror if a
  test or caller needs adjusting.

**Alternatives considered**: Pre-emptively rewriting callers — rejected as speculative; the type
gate is the ground truth and pre-emptive edits risk scope creep.

## Decision 3 — Verification & no generated-file impact

**Decision**: Verify with the project static gate (mypy + ruff via `/pre-ci`) and the git component
tests (`backend/tests/component/git/test_git_repository.py`). No generated files are regenerated.

**Rationale**: The change is confined to a hand-written module and (optionally) a changelog
fragment. It touches none of the generated-file paths listed in `AGENTS.md`, no schema, and no API
contract, so no `invoke *.generate` step is required. The git component tests exercise
merge/rebase behavior and confirm runtime is unchanged.

## Resolved unknowns

None outstanding — no `NEEDS CLARIFICATION` markers. The feature description was precise and
independently verified against current source (`repository.py` lines 271/300/307/309/319).
