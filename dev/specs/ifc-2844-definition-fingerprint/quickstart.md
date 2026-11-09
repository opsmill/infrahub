# Quickstart: Validating the Definition Fingerprint Foundation

Validation guide proving the feature end-to-end. Field-level composition lives in
`contracts/fingerprint-composition.md`; the schema shape in `data-model.md`. This file is
run/validation scenarios only.

## Prerequisites

```bash
uv sync --all-groups
```

Fixtures: reuse the `car-dealership` repo fixture
(`backend/tests/fixtures/repos/car-dealership/`), which already contains GraphQL queries,
Jinja2 + Python transforms, artifact definitions, and generator definitions, plus the
`FileRepo` / `MultipleStagesFileRepo` helpers (`backend/tests/helpers/file_repo.py`) that
support multi-commit re-import. Model new integration tests on
`backend/tests/integration/git/test_generator_import_closure.py`.

## Step 0 - Regenerate and verify generated files (SC-009)

After adding the four `fingerprint` attributes:

```bash
uv run invoke backend.generate
uv run invoke schema.generate-graphqlschema
uv run invoke schema.generate-jsonschema
cd frontend/app && pnpm codegen && cd -
uv run invoke docs.validate        # must pass (no stale generated files)
```

Expected: `fingerprint` appears in `backend/infrahub/core/protocols.py`, the generated
schema, `schema/schema.graphql`, and the frontend generated GraphQL types.

## Step 1 - US1: query fingerprint primitive (P1)

1. Import a repo containing a `CoreGraphQLQuery`. Assert the query node's `fingerprint`
   is non-null (SC-001).
2. Re-import byte-identical -> fingerprint unchanged (SC-002).
3. Edit the query text, re-import -> fingerprint changes (SC-003).
4. Edit an unrelated file, re-import -> query fingerprint unchanged.
5. Two imports differing only by ordering that Infrahub normalises identically -> equal
   fingerprints (hash is over stored inlined text, not raw bytes).

## Step 2 - US2: transformation fingerprint (P1)

Python and Jinja2 transforms both non-null. With `watch` declared (`{}` or files):

- No-op re-import -> unchanged (SC-002).
- Connected query fingerprint changes -> transform fingerprint changes.
- A closure file's blob SHA changes -> changes.
- Python: `class_name` or `convert_query_response` change -> changes. Jinja2:
  `template_path` change -> changes.
- `timeout`-only change -> unchanged (FR-010).
- `watch: {}` and edit the transform's own `.py`/template -> changes (own source file is
  in the closure, FR-009a).

## Step 3 - US5: watch-driven stability (P1)

For one transform/generator, set `watch` to each state:

- absent (`None`) -> fingerprint changes on every commit, incl. unrelated file changes (SC-006).
- explicit empty (`watch: {}`) -> stable across unrelated commits (SC-002).
- populated (`watch: {files: [...]}`) -> declared file change -> changes; undeclared
  non-closure file change -> unchanged.
- Comment-only / unrelated `.infrahub.yml` edit for a definition with declared `watch` ->
  unchanged (SC-005). (While `watch` is absent, the folded commit id still changes it -
  that is the safe default, not a regression.)

## Step 4 - US3: artifact definition fingerprint (P2)

Non-null. Changes on: transformation fingerprint, `parameters`, `content_type`,
`artifact_name`, or target-group **identity** (re-point). Unchanged on group
**membership** churn (add/remove one member) - SC-007.

## Step 5 - US4: generator definition fingerprint (P2)

Non-null. Changes on: query fingerprint, closure, `parameters`, and group identity.
Same watch semantics as transforms. `watch: {}` + `class_name` change (different class,
same unchanged file) or `convert_query_response` toggle -> changes (FR-012a). Group
membership churn -> unchanged.

## Step 6 - Cross-cutting invariants

- **Edit-then-revert** (SC-004): change an input, re-import, revert to identical bytes,
  re-import -> identical fingerprint before and after.
- **Consistent snapshot** (FR-015a): change a query and its dependent artifact definition
  in the *same* commit/import -> the artifact-definition fingerprint reflects the new
  query fingerprint in that same import (no one-import lag).
- **No consumer change** (SC-008, FR-020): existing regeneration/recompute regression
  tests stay green with identical trigger counts.
- **Branch behaviour** (SC-010): the `fingerprint` appears in a branch diff and survives
  rebase/merge as a normal branch-aware attribute.

## Test placement

- Unit (`backend/tests/unit/git/fingerprint/`): composers (each layer), blob resolver,
  watch-state discrimination, canonicalisation / edit-then-revert determinism.
- Integration (`backend/tests/integration/git/`): import-and-store per kind, re-import
  stability, closure/query/param/group-identity/membership scenarios, branch diff.

Per repo convention, no Jira/spec/FR IDs appear in test names, docstrings, or source
comments - those belong in the commit message, PR description, and changelog fragment.
