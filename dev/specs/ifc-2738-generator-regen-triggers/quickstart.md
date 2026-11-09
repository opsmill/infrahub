# Quickstart — Manual Verification

End-to-end recipe to confirm precise generator triggering works as specified. Mirrors the Independent-Test stanzas from spec.md User Stories 1-7.

## Prerequisites

- A running Infrahub instance built from this branch (`uv run invoke dev.build && uv run invoke dev.start`).
- A linked `CoreRepository` containing at least:
  - Two generator definitions in **different** package directories (call them `gen_a` at `generators/a/a.py` and `gen_b` at `generators/b/b.py`), each with a `targets` group that has at least one member.
  - `gen_a`'s package directory contains a sibling module `generators/a/helpers.py`.
  - A `README.md` at repo root.
  - Two `.gql` files, one used by `gen_a`'s query and one by `gen_b`'s query.
  - A third generator `gen_c` that imports from a top-level package outside its own directory (e.g. `shared/util.py`) and declares `watch: { files: ["shared/"] }`.
- One generator reachable from a `CoreReadOnlyRepository` pinned to a known commit.
- All generators re-imported at least once on this branch so their `dependencies` are populated (check via GraphQL or the UI that `dependencies` is non-null).

## Scenario 1 — README edit triggers nothing (SC-001, US1)

1. New Infrahub branch off `main`, `sync_with_git = True`.
2. Edit `README.md`, commit and push to the branch's tracked Git branch.
3. Open a proposed change to `main`; watch the pipeline.

**Expected**: zero generators dispatched. The task log shows no "will run" entry for any generator. A `.py` edit outside every generator's package directory and unread by any query (US1 acceptance 2) behaves identically.

## Scenario 2 — Edit one generator's source, only it re-runs (SC-002, US2)

1. New branch. Modify `generators/a/a.py`. Commit, push, open PC.

**Expected**: `gen_a`'s instances re-run; `gen_b` untouched. Task log:

```text
Definition gen_a: file generators/a/a.py changed and is in this generator source's dependency closure - all instances will run.
```

2. Repeat instead editing the sibling `generators/a/helpers.py` (US2 acceptance 2).

**Expected**: `gen_a` re-runs (the package-directory floor includes the sibling); `gen_b` untouched.

## Scenario 3 — Edit one `.gql` query, only its generators re-run (SC-003, US3)

1. New branch. Modify the `.gql` query used by `gen_a`. Commit, push, open PC.

**Expected**: only generators using that query re-run. Task log:

```text
Definition gen_a (<id>): GraphQL query <query_name> (<query_id>) was modified - all instances of this definition will run.
```

## Scenario 4 — Read-only repository participates (SC-004, US4)

1. New branch with `sync_with_git = False`.
2. Advance the read-only repository's tracked commit to one that modifies the reachable generator's closure (e.g. its source file).
3. Open a PC; watch the pipeline.

**Expected**: the generator re-runs even though the consuming branch does not sync with Git (the per-repo diff is decoupled from `sync_with_git`). A commit bump modifying only files outside any generator's closure (US4 acceptance 2) triggers no generator.

## Scenario 5 — Diagnostic visibility (SC-006, US5)

For every scenario above, confirm the pipeline task log names the specific triggering file, query, or definition change for the affected generator, and that a non-triggered generator is reflected as not run.

## Scenario 6 — Backward compatibility / self-heal (SC-005, US6)

1. Find (or simulate) a generator with `dependencies = null` (imported before this feature). Confirm a PC with any file change still runs it with no error (legacy fallback). Task log:

   ```text
   Definition <name>: generator source was imported before this feature deployed (dependencies=null) - falling back to regenerate-on-any-file-change. ...
   ```

2. Re-import the repository (push any commit). Confirm `dependencies` and `dependencies_complete` are now populated and subsequent PCs use precise triggering.

## Scenario 7 — User-declared `watch:` (SC-009, US7)

1. New branch. Edit `shared/util.py` (inside `gen_c`'s declared `watch.files`). Commit, push, open PC.

**Expected**: `gen_c` re-runs (US7 acceptance 1).

2. Edit a file outside both `shared/` and `gen_c`'s package floor (US7 acceptance 2).

**Expected**: `gen_c` does not re-run on file-change grounds.

3. In `.infrahub.yml`, set `watch: [shared/]` (list form) and re-import (US7 acceptance 3).

**Expected**: schema rejects the input at parse time.

4. Set `watch: { files: ["does/not/exist"] }` and re-import (US7 acceptance 4).

**Expected**: a warning is logged for the non-matching entry; the import of `gen_c` and the other generators proceeds.

## Regression check — artifacts unchanged (SC-007)

Run the artifact selection scenarios from the INFP-409 quickstart (README edit, `.gql` edit, transform source edit) and confirm artifact behavior and log wording are identical to before this branch. The automated guard is `backend/tests/component/proposed_change/test_artifact_regen_selection.py` plus the predicate/logging unit tests staying green.

## Automated equivalents

- `backend/tests/unit/proposed_change/` — generalized predicate tests (generator-model variants) + artifact regression.
- `backend/tests/unit/git/closure_builder/` — `PythonClosure` accepts generator config.
- `backend/tests/component/proposed_change/test_generator_regen_selection.py` — mirrors the artifact selection component test.
- `python_sdk/tests/` — `watch` field parsing, strict-object rejection, recursive directory expansion.
- `test_proposed_change_repository.py` — e2e, `xfail` on GitHub Actions (same deferral as INFP-409).
