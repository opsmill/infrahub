# Implementation Report: User-Facing Schema Separation (INFP-234) — INCOMPLETE

**Feature**: User-Facing Schema Separation
**Spec dir**: `specs/002-user-facing-schema` (tracked at `dev/specs/002-user-facing-schema`)
**Base commit**: `3525b42ec`
**Head commit**: `f39a8446c` (parent) · SDK submodule `ce6e067`
**Branch**: `dga/user-schema-infp-234-gqj6d` (+ SDK submodule own history)
**Status**: **INCOMPLETE** — 30/31 tasks done; T020 intentionally partial, and one HIGH review finding (REST OpenAPI contract) is deferred as a documented follow-up. All local-pass evidence is present (no MISSING rows).

## 1. Chunk-by-chunk ledger

| # | Chunk (phase) | Tasks | ✅ | ⚠️ | ❌ | Commit(s) |
|---|---------------|-------|----|----|----|-----------|
| 1 | Setup | T001–T003 | 3 | 0 | 0 | `1a6d1e648` |
| 2 | Foundational | T004–T009 | 6 | 0 | 0 | parent `581f8772e` / SDK `1aa2046` |
| 3 | US1 (P1 MVP) | T010–T016 | 7 | 0 | 0 | `4a5ccd27f` |
| 4 | US2 | T017–T021 | 4 | 1 | 0 | parent `6ca3ba3ee` / SDK `8d8da84` |
| 5 | US3 | T022–T026 | 5 | 0 | 0 | `e390fbd0b` |
| 6 | Polish | T027–T031 | 5 | 0 | 0 | parent `97c1e64c7` / SDK `5f6ac8a` |
| R | Review fixes | (FIX 1–5) | 4 | 1 | 0 | parent `f39a8446c` / SDK `ce6e067` |

**Flagged upward during chunks:**
- **Ch2**: `tasks/backend.py` passed a *shell-escaped* repo path to Jinja's `FileSystemLoader`/`Path` — broke generation in worktree paths containing regex/shell metacharacters (this worktree). Switched Python-side FS/template access to the real `REPO_BASE` (no-op in clean CI paths). Used a dedicated `generate_schema_sdk.j2` so the internal variant stays byte-identical. Enums rendered as `Literal[...]` for self-contained SDK models.
- **Ch2/Ch6**: `backend.generate` regenerates `python_sdk/infrahub_sdk/protocols.py`, which showed pre-existing drift unrelated to this feature (pinned submodule predated current backend schema); committed in the SDK so CI's generated-file check passes.
- **Ch3**: T013 wired as a `model_validator(mode="before")` boundary gate (not a full model swap) — a full swap would 422 on the unknown field before naming `inherited`.
- **Ch4**: T020 left **partial** deliberately (see §3). Backend load boundary now calls the SDK's `validate_schema()` directly (single implementation).
- **Ch5**: backend internal Pydantic models already have the read model's field set; the "internal back-reference" is a meta-schema relationship, never serialized — GET was already read-model-consistent, so T025 enforced visibility via test rather than a risky rebase.

## 2. Tasks not completed

- **T020 (US2) — ⚠️ partial.** DONE: the generated write models are the single source for the load boundary (SDK `validate_schema` + backend; backend's duplicated validator removed). NOT DONE: the SDK's hand-written `main.py` models (`SchemaRoot`/`NodeSchema`/`*API` read models with ~15 behavior methods, enums, `BranchSchema`) and the ~22 in-SDK consumers are not repointed. Reason: the generated read models lack `hash` and differ in field set/typing (`Literal` vs enum classes; extra fields; `min_count`/`max_count` required int) from the hand-written read models; a naive rebase changes serialization shape and breaks export/protocols-generator/node consumers and the SDK suite. Deferred to keep the SDK suite green. Consequence: **FR-009** ("no second parallel definition") is not fully met — a behavior-subclass-over-generated-data-model refactor is needed in its own chunk.

## 3. Local-pass evidence

All rows observed passing locally (Neo4j/testcontainers Docker stack available for functional tests). No MISSING rows.

| Test id | Type | Run command | Passed at (UTC) | Env | Verbatim pass line |
|---------|------|-------------|-----------------|-----|--------------------|
| `backend/tests/unit/core/schema/test_generated_visibility.py` (13 cases: SC-001 no-leak + SC-002 enum-published per family + positive settable-field guard) | unit | `uv run pytest backend/tests/unit/core/schema/test_generated_visibility.py -q` | 2026-07-03T15:28:39Z | backend unit, no DB | `13 passed` |
| `test_load_schema.py::…rejects_non_write_and_unknown_fields` | functional | `uv run pytest …::test_schema_load_rejects_non_write_and_unknown_fields -q` | 2026-07-03T14:18:51Z | Neo4j testcontainers | `2 passed … in 55.30s` (with out-of-enum kind) |
| `test_load_schema.py::…rejects_out_of_enum_attribute_kind` | functional | (run with above) | 2026-07-03T14:18:51Z | Neo4j testcontainers | `2 passed … in 55.30s` |
| `test_load_schema.py::…rejects_non_write_fields_in_extensions` (FIX 1) | functional | `uv run pytest …::test_schema_load_rejects_non_write_fields_in_extensions …::test_schema_load_rejects_out_of_enum_relationship_cardinality -v` | 2026-07-03T15:29:17Z | Neo4j testcontainers | `2 passed … in 50.08s` |
| `test_load_schema.py::…rejects_out_of_enum_relationship_cardinality` (FIX 2) | functional | (run with above) | 2026-07-03T15:29:17Z | Neo4j testcontainers | `2 passed … in 50.08s` |
| `test_load_schema.py::…stored_schema_with_read_level_field_reads_back` | functional | `uv run pytest …::test_stored_schema_with_read_level_field_reads_back …::test_schema_load_id_cannot_bypass_authorization -q` | 2026-07-03T~14:20Z | Neo4j testcontainers | `2 passed … in 60.33s` |
| `test_load_schema.py::…id_cannot_bypass_authorization` (R1) | functional | (run with above) | 2026-07-03T~14:20Z | Neo4j testcontainers | `2 passed … in 60.33s` |
| `test_load_schema.py` (full file, regression incl. parity test) | functional | `uv run pytest backend/tests/functional/api/test_load_schema.py` | 2026-07-03T15:32:00Z | Neo4j testcontainers | `17 passed … in 134.21s` |
| `test_40_schema.py::test_schema_read_endpoint_visibility` | component | `uv run pytest …::test_schema_read_endpoint_visibility -q` | 2026-07-03T~14:40Z | Neo4j testcontainers | `1 passed … in 23.59s` |
| `test_40_schema.py` (full file, regression) | component | `uv run pytest backend/tests/component/api/test_40_schema.py` | 2026-07-03T~14:45Z | Neo4j testcontainers | `27 passed … in 85.65s` |
| `python_sdk/tests/unit/test_schema_offline_validation.py` (14 cases incl. extensions + relationship + read-level breadth) | unit (SDK) | `uv run pytest tests/unit/test_schema_offline_validation.py -q` | 2026-07-03T15:36:35Z | SDK venv, pydantic only (no server) | `14 passed` |
| `python_sdk/tests/unit/test_schema_generated_models.py` (drift/presence/invariants) | unit (SDK) | `uv run pytest tests/unit/test_schema_generated_models.py -q` | 2026-07-03T~15:36Z | SDK venv | passed (with offline suite) |
| SDK suite regression (T020 gate) | unit (SDK) | `uv run pytest tests/unit -o addopts=""` | 2026-07-03T~13:00Z | SDK venv | `1432 passed` (10 pre-existing/environmental failures, unchanged from baseline; +23 new passing) |

## 4. Review findings

| Severity | File | Summary | Disposition |
|----------|------|---------|-------------|
| HIGH | `schema/openapi.json` / `backend/infrahub/api/schema.py` | REST OpenAPI load request still advertises bare-string `kind` (no enum) + non-settable fields; runtime rejects them via the before-validator (invisible to FastAPI schema-gen). Doc-vs-behavior gap; FR-004/SC-002 only met at SDK-model level. | **Deferred** — documented in `opsmill-implement-followups.md` with recommended approach. Not force-fixed (both safe paths risk the downstream parsing the impl deliberately avoided). |
| HIGH | `python_sdk/infrahub_sdk/schema/validate.py` | `extensions.nodes[*]` attributes/relationships bypassed the write-contract gate. | **Fixed inline** (FIX 1): `validate_schema` now gates extension attrs/rels against the generated write models; functional + SDK tests added. |
| MEDIUM | `backend/.../test_generated_visibility.py` | No positive guard — a future field defaulting to INTERNAL would silently drop from write+read and be rejected on load with no failing test. | **Fixed inline** (FIX 3): positive settable-field guard per family. |
| MEDIUM | tests | Relationship-level + non-`inherited` read-level rejection, and out-of-enum relationship fields, were untested. | **Fixed inline** (FIX 2). |
| MEDIUM | `test_load_schema.py` | Parity test is tautological (endpoint calls same validator); loose `in response.text` assertions. | New tests assert structured dotted-path errors; parity remains a wiring guard (noted). |
| LOW | `tasks/backend.py` | `ruff` invocations interpolated unescaped paths → break on shell-metacharacter checkout paths. | **Fixed inline** (FIX 4): paths quoted. |
| LOW | new test files | Spec/ticket IDs in test names/docstrings violate `.agents/rules`. | **Fixed inline** (FIX 4): removed. |

## 5. Autonomous decisions (may warrant a look)

1. **`before_specify` Jira hook run in `--dry-run`** (prep phase) to avoid creating/switching a second branch inside the existing worktree.
2. **`ESCAPED_REPO_PATH`→`REPO_BASE`** in `tasks/backend.py`: a real fix (escaped path broke Jinja/Path here), no-op on clean CI paths — but it is a change to shared generation tooling beyond the feature's strict scope.
3. **Unrelated `protocols.py` drift** committed in the SDK to keep the generated-file CI check green.
4. **T020 left partial** to keep the SDK test suite green rather than ship a broken library (see §2).
5. **T025 via visibility-enforcing test, not a model rebase** (backend internal models already match the read field set).
6. **FIX 5 (REST OpenAPI, HIGH) deferred** rather than force-fixed in a review pass — documented follow-up.
7. **SDK commits are on the submodule's detached HEAD** (consistent across chunks). To land them, a branch must be created in the SDK repo (`opsmill/infrahub-sdk-python`) at `ce6e067` and a PR opened there; the parent repo's submodule pointer references it.
8. Targeted `ruff`/`mypy` on changed files were used in the review-fix pass instead of repo-wide `invoke format`/`lint` (which Ch6 already ran green across the whole tree).

## 6. Suggested next steps

1. **Address the deferred HIGH finding** — publish the write contract in the REST OpenAPI (`opsmill-implement-followups.md`): declare the load endpoint's request model as the generated write models (converting to internal downstream) or inject a custom OpenAPI request-body schema, then regenerate `schema/openapi.json`. This is what makes FR-004/SC-002 true for an agent reading the REST contract (the P1 story's artifact).
2. **Finish T020** — consolidate the SDK's hand-written models onto the generated data models via a behavior-subclass/mixin strategy (reconciling `hash` and the `Literal`-vs-enum/field-set deltas), repoint the ~22 consumers, keep the SDK suite green → satisfies FR-009.
3. **Land the SDK changes** — create a branch in the SDK repo at `ce6e067`, open its PR, then bump the submodule pointer in the backend PR.
4. **Set the SC-004 benchmark target** with product (still open).
5. Open the backend PR from `dga/user-schema-infp-234-gqj6d` once 1–3 are resolved; run the full repo-wide `invoke format`/`lint`/`docs.validate` in CI.
