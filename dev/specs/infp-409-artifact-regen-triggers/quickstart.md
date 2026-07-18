# Quickstart — Manual Verification

End-to-end recipe a developer can follow to confirm Stage 1 + Stage 2 are working as specified. Mirrors the independent-test stanzas from spec.md User Stories 1–5.

## Prerequisites

- A running Infrahub instance built from this branch (`uv run invoke dev.build && uv run invoke dev.start`).
- A linked `CoreRepository` containing at least:
  - One artifact definition whose Jinja2 transform uses `{% include "partials/header.j2" %}`.
  - One artifact definition whose Python transform lives at `transforms/foo/foo.py` with a sibling helper `transforms/foo/helpers.py`.
  - A `README.md` at repo root.
  - A `.gql` file used by one of the definitions' queries.
- One artifact definition that is also reachable from a `CoreReadOnlyRepository` pinned to a known commit on the source branch.

## Scenario 1 — README edit triggers nothing (SC-001, US1 acceptance 1)

1. Create a new Infrahub branch off `main`. Set `sync_with_git = True` on the branch.
2. In the linked repo, edit `README.md`. Commit and push to the branch's tracked Git branch.
3. Open a proposed change from this branch to `main`.
4. Watch the pipeline run.

**Expected**:

- No artifact regenerates.
- The pipeline task log contains no "all artifacts will be regenerated" entry for any definition.

## Scenario 2 — Edit one `.gql` file, only its definition regenerates (US1 acceptance 3)

1. New Infrahub branch. Modify the `.gql` file used by one definition (`A`). Commit, push, open PC.

**Expected**:

- Only definition `A`'s artifacts regenerate.
- Pipeline task log contains an entry like:

  ```text
  Definition A: GraphQL query <query_name> (<id>) was modified — all artifacts of this definition will regenerate.
  ```

## Scenario 3 — Edit the transform's own file (US1 acceptance 4)

1. New Infrahub branch. Modify the Python transform file `transforms/foo/foo.py`. Commit, push, open PC.

**Expected**:

- Only the definition using that transform regenerates.
- Pipeline task log: `Definition <name>: file transforms/foo/foo.py changed and is in this transform's dependency closure — all artifacts will regenerate.`

## Scenario 4 — Python heuristic floor (US1 acceptance 5)

1. New Infrahub branch. Modify the *sibling helper* `transforms/foo/helpers.py`. Commit, push, open PC.

**Expected**:

- The definition using `foo.py` regenerates (the closure includes the sibling because of the package-directory floor).
- Pipeline log mentions `transforms/foo/helpers.py` as the cause.

## Scenario 5 — Jinja2 transitive include (US1 acceptance 6)

1. New Infrahub branch. Edit `partials/header.j2`. Commit, push, open PC.

**Expected**:

- The Jinja2 transform's definition regenerates.
- Pipeline log: `Definition <name>: file partials/header.j2 changed and is in this transform's dependency closure — all artifacts will regenerate.`

## Scenario 6 — `watch:` field happy path (US3 acceptance 2)

1. In `.infrahub.yml`, add `watch.files: [templates/partials/]` to the Jinja2 transform entry. Push the commit (this re-imports the transform under the new code).
2. Verify the new closure is stored: query the `CoreTransformation` node and observe `dependencies` includes `templates/partials/...` entries and `dependencies_complete = True`.
3. New Infrahub branch. Edit a file inside `templates/partials/` that was *not* the auto-detected include. Open PC.

**Expected**: the transform's definition regenerates.

4. New Infrahub branch. Edit a file *outside* `templates/partials/` and outside the auto-detected closure (e.g. an unrelated helper). Open PC.

**Expected**: nothing regenerates.

## Scenario 7 — Read-only repo participates (US5 acceptance 1)

1. Set `sync_with_git = False` on a new Infrahub branch.
2. Bump the linked `CoreReadOnlyRepository`'s pinned commit on the source branch to a commit that modifies a `.gql` query referenced by definition `B`.
3. Open PC.

**Expected**:

- Definition `B`'s artifacts regenerate.
- The `sync_with_git = False` flag does not suppress the regeneration.

## Scenario 8 — Definition repointed (US3-ish, FR-007)

1. New Infrahub branch. Edit the `targets` relationship on definition `C` to point at a different `CoreStandardGroup`.
2. Open PC.

**Expected**:

- All of definition `C`'s artifacts regenerate.
- Pipeline log: `Definition C: definition node was modified (targets) — all artifacts will regenerate.` (`_definition_changed` triggered.)

## Scenario 9 — Legacy fallback path (US4 acceptance 1)

1. With a database carrying transforms imported before Stage 2 deployed (`dependencies = null` on the `CoreTransformation` node), without re-importing, open a PC that edits any tracked file in the repo.

**Expected**:

- The pipeline runs without errors.
- Pipeline log includes: `Definition <name>: transform was imported before this feature deployed (dependencies=null) — falling back to regenerate-on-any-file-change.`
- Affected artifacts regenerate as they would have done pre-feature.

2. Commit any change to the repo that triggers a re-import. Re-run a PC against any change.

**Expected**: the new precise gate applies (Scenarios 1–8 hold for this transform).

## Scenario 10 — Dynamic Jinja2 include with no `watch:` (US3 acceptance 1)

1. Add `{% include some_var %}` to a Jinja2 transform's template. Push the commit (re-imports under the new code).
2. Verify the import log shows: `Definition <name>: closure builder encountered unresolved reference at templates/<file>:<line>; dependencies_complete=False.`
3. Open a PC that edits *any* file in the repo.

**Expected**:

- The affected artifacts regenerate (safe fallback per `dependencies_complete = False`).
- Pipeline log records the incomplete closure and which file change triggered the fallback.

## Scenario 11 — Closure-builder failure is isolated (US4 acceptance 3)

1. Add a Jinja2 transform with an intentionally malformed template (e.g. `{% include "missing` — unterminated string). Push the commit.

**Expected**:

- The import log records the closure-builder failure for that transform with the affected transform's name.
- The other transforms in the same repo import successfully.
- The malformed transform's `dependencies_complete = False` (or `dependencies = null`-with-explanation in the log).
- Subsequent PCs that touch the repo regenerate that transform's artifacts (safe fallback).

## Scenario 12 — Diagnostic logging completeness (US2)

For every regeneration in Scenarios 2–8, confirm the pipeline task log identifies:

- The triggering file path (Scenarios 3, 4, 5, 6).
- The GraphQL query name and id (Scenario 2, 7).
- The definition attribute or relationship (Scenario 8).

A user reading the log should be able to answer "why did these artifacts regenerate?" without cross-referencing `diff_summary` or the database directly (SC-003).

## Sign-off criteria

All twelve scenarios pass. SC-001 through SC-009 from spec.md correspond 1:1 with the scenarios above:

| SC | Scenario |
|---|---|
| SC-001 | 1 |
| SC-002 | 3, 4, 5 |
| SC-003 | 12 |
| SC-004 | 1 (logical consequence of 1 on a 10k target group) |
| SC-005 | 9 |
| SC-006 | 7 |
| SC-007 | 6 |
| SC-008 | 11 |
| SC-009 | 9, 10, 11 |
