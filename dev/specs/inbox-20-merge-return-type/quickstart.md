# Quickstart / Verification: merge()/rebase() return-type correction

This is an annotation-only change, so "validation" means: the static type gate accepts the new
contract, no caller breaks, and runtime behavior is provably unchanged.

## Prerequisites

- Worktree on branch `pha/INBOX-20`, dependencies synced: `uv sync --all-groups`.

## Verify the annotations (inspection)

```bash
rg -n "def merge|def rebase" backend/infrahub/git/repository.py
```

Expected: both signatures end in `-> str | Literal[False]:`, and `Literal` is imported from
`typing` at the top of the module.

## Verify the static type gate (primary acceptance)

Run the project's mypy/lint gate (the same one `/pre-ci` runs):

```bash
uv run invoke backend.lint
```

Expected: passes with **no new errors**. In particular:
- Inside `merge()`, both `return False` and `return str(commit_after)` satisfy `str | Literal[False]`.
- `rebase()` (delegating to `merge()`) satisfies its own `str | Literal[False]`.
- No previously-green caller becomes red. If mypy flags a genuinely bool-assuming site, it is
  reconciled with `isinstance(result, str)` narrowing (see research.md, Decision 2).

## Verify runtime behavior is unchanged (regression guard)

```bash
uv run pytest backend/tests/component/git/test_git_repository.py
```

Expected: all tests pass. A successful merge still returns the new commit-hash string; a no-op
merge still returns `False`; `rebase()` still returns whatever `merge()` returns.

## Done when

- Annotations read `str | Literal[False]` for both methods.
- `uv run invoke backend.lint` is green (type gate + ruff).
- `backend/tests/component/git/test_git_repository.py` is green.
- The diff is confined to `backend/infrahub/git/repository.py` + a `changelog/` fragment (plus
  minimal caller narrowing only if the type gate required it).
