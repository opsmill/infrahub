# Quickstart / Validation Guide: User-Facing Schema Separation

Runnable scenarios that prove the feature works end-to-end. See `contracts/` and
`data-model.md` for the shapes referenced here.

## Prerequisites

- `uv sync --all-groups` (backend deps).
- `git submodule update --init python_sdk` — the SDK submodule must be checked out
  (it is empty in a fresh worktree); the write/read models are generated into it.

## 1. Regenerate the models (idempotency)

```bash
uv run invoke backend.generate
uv run invoke schema.generate-jsonschema   # refresh schema/openapi.json
git status --short                          # expect: only intended generated diffs
uv run invoke backend.generate              # run again
git diff --exit-code                        # expect: no diff (idempotent)
```

Expected: three model families are generated; the SDK now contains generated
write/read schema models; a second run produces no diff.

## 2. Enum propagation (FR-004 / SC-002)

```bash
# Inspect the generated write JSON-schema for attribute `kind`
uv run invoke schema.generate-jsonschema
python -c "import json,sys; d=json.load(open('schema/openapi.json')); print('kind enum present')"
```

Expected: attribute `kind` and relationship `kind`/`cardinality` carry their full
allowed-value lists in the generated write model / JSON-schema; no constrained field
is a bare `str` where an enum is defined internally.

## 3. Reject non-settable fields on load (FR-003 / SC-003)

Run the functional load tests (extended for this feature):

```bash
uv run invoke backend.test-unit                          # generator unit tests
uv run pytest backend/tests/functional/api/test_load_schema.py -q
```

Expected: a payload containing `inherited` (read-level) plus an unknown field is
rejected with a field-level error naming each; a valid write-shaped schema loads.

## 4. Read-back includes read-only fields (FR-005/FR-006/FR-010)

```bash
uv run pytest backend/tests/component/api/test_40_schema.py -q
```

Expected: `GET /api/schema` returns `inherited`/`used_by`; never returns internal
fields; a pre-existing stored schema reads back without error.

## 5. SDK offline validation + parity (FR-006/FR-007/FR-008 / SC-005)

```bash
# In an environment with ONLY the SDK installed (no server):
cd python_sdk && uv run pytest tests -k "schema and validate" -q
```

Expected: a good schema validates locally; a bad one fails naming the field; the
local verdict matches the server's for the same payloads.

## Done-when

- All five scenarios pass.
- `uv run invoke backend.generate && uv run invoke schema.generate-jsonschema` leaves
  no uncommitted drift.
- SDK's former hand-written schema models are gone; callers use the generated ones.
