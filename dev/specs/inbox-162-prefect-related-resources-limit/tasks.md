# Tasks: Align Infrahub's event related-resource cap with Prefect's effective limit

**Feature**: `dev/specs/inbox-162-prefect-related-resources-limit` | **Branch**: `pha/INBOX-162`

**Inputs**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [critique.md](./critique.md)

Ordering note: the test-mechanism migration (T003) runs **before** any new coverage is added, so
the existing 59 cases are proven green on `temporary_settings` before the suite grows. Doing it the
other way round mixes "did my new test work?" with "did I migrate correctly?" — see critique E1.

---

## Phase 0 — Environment

### T001 · Prepare the worktree environment · `setup`

A fresh worktree has an empty `python_sdk`, which makes every `infrahub.*` import fail with
`ModuleNotFoundError: No module named 'infrahub_sdk'` (research.md R8).

```bash
git submodule update --init python_sdk
uv sync --all-groups --reinstall-package infrahub-server
```

**Done when**: `uv run python -c "import infrahub.events.limits"` succeeds.

**Depends on**: nothing.

### T002 · Record the pre-change baseline · `setup` `[P]`

```bash
uv run pytest backend/tests/unit/event/ \
  backend/tests/unit/core/merge/test_submit_coalesced_recompute.py
```

**Done when**: the run is green and the count is noted. Expected **59 passed** (research.md R8,
critique E7). If it differs, stop and reconcile before editing anything — the number is the
regression baseline for T007.

**Depends on**: T001.

---

## Phase 1 — Migrate the existing tests to the real override mechanism

### T003 · Migrate `test_limits.py` from `monkeypatch.setenv` to `temporary_settings` · `test`

**File**: `backend/tests/unit/event/test_limits.py`

`monkeypatch.setenv` cannot drive a Prefect-settings read — settings are snapshotted at import
(research.md R4). This migration is a prerequisite for the implementation, not a follow-up.

- Delete the module-level `ENV_VAR` constant.
- Replace every `monkeypatch.setenv(ENV_VAR, case.configured_max)` with
  `temporary_settings({PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES: case.configured_max})`,
  wrapping the assertion in the context manager.
- Change `configured_max` from `str` to `int` on `ChunkSizeCase` and `BudgetCase` — the string form
  existed only because the value came from the environment. Update the case tables accordingly
  (`"1"` → `1`, `"500"` → `500`, …).
- Drop the now-redundant `monkeypatch` parameter from the migrated test signatures.
- In `test_event_on_the_budget_survives_the_prefect_run_context_append`, remove the
  `monkeypatch.setenv` line and keep its existing `temporary_settings` block — it was already
  pairing both mechanisms and only needs the dead half removed (research.md R4).
- **Preserve every case's intent and its explanatory comments verbatim** (e.g. `# 1 // 2 == 0
  without the floor`, `# 100 // 10 < 20`). They encode why each boundary matters.
- Add a comment on the `BUDGET_CASES` entry for maximum 100 noting that after this change it also
  covers the new default.

**Important**: this task must leave the suite **green against the unchanged implementation**.
`temporary_settings` sets the real setting, and the current code reads `os.environ`, so the migrated
cases would all fall through to the current 500 default and fail. Therefore migrate the mechanism
**and** run T004 in the same step — see the note on T004's dependency. Verify by running T003+T004
together, not T003 alone.

**Depends on**: T002.

---

## Phase 2 — Implementation

### T004 · Read Prefect's effective maximum in `limits.py` · `impl`

**File**: `backend/infrahub/events/limits.py`

- Remove `import os` and the `_DEFAULT_MAX_RELATED_RESOURCES = 500` constant.
- Add `from prefect.settings import PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES` — the accessor
  Prefect's own `_validate_related_resources` uses, so Infrahub's ceiling cannot diverge from the
  enforced one (research.md R1, critique E6).
- Add `PREFECT_DEFAULT_MAX_RELATED_RESOURCES = 100`, Prefect's documented default (research.md R2).
- Rewrite `get_prefect_max_related_resources()` to return
  `PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value()` when positive, else the default.
- **Delete the `try/except ValueError` parse guard** — unreachable, because a non-numeric value
  makes Prefect raise during settings construction, at import, before Infrahub runs (research.md
  R5, critique E3).
- **Keep the non-positive guard**, and word its docstring honestly: it keeps the derived budget and
  chunk size computed from a sane positive ceiling; it does **not** rescue event delivery, since a
  maximum of 0 makes Prefect reject every event with related resources regardless (plan.md D2,
  critique E4).
- Update the docstring so it no longer claims the value is read "from the environment".
- Do not touch `MAX_RUN_CONTEXT_RESOURCES`, `get_related_resource_budget()` or
  `get_submission_chunk_size()` — same semantics, same signatures (FR-007).
- Full type hints throughout (Constitution III).

**Done when**: `grep -n '500' backend/infrahub/events/limits.py` prints nothing, and T003's
migrated suite passes.

**Depends on**: T003 (and T003's verification depends on this — run the pair together, then the
suite green).

---

## Phase 3 — New coverage

### T005 · Pin the new default and the guard in `test_limits.py` · `test` `[P]`

**File**: `backend/tests/unit/event/test_limits.py`

Following the file's dataclass-case + `parametrize` style:

- With nothing configured, `get_prefect_max_related_resources()` returns **100**, not 500
  (FR-002, SC-004). This is the regression test for the card's core defect.
- A non-positive configured maximum (`0` and a negative) falls back to 100 (FR-005).
- Overriding via the **alias** `PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES` is observed
  (FR-004, SC-003). Deliberately exercises the alias the implementation reads while the other
  tests override the name the image uses — proving equivalence rather than assuming it
  (critique E6).

**Depends on**: T004.

### T006 · Assert the node-event truncation tracks the setting · `test` `[P]`

**File**: `backend/tests/unit/event/test_node_action.py`

Beside the existing cap tests (`test_related_resources_stay_within_prefect_maximum_for_large_relationships`,
`test_truncation_drops_peer_entries_not_node_scoped_entries`), matching their style:

- With the maximum at **100**, `NodeMutatedEvent.get_related()` truncates to the budget derived
  from 100 (US1, SC-001).
- With the maximum at **500**, it truncates to the budget derived from 500 (US2, SC-002).

**Assert against `get_related_resource_budget()` evaluated under the same override — never a
literal 80 or 450.** A literal would keep passing even if the derivation were replaced by a
constant, which is exactly the regression these tests exist to catch (plan.md D3, critique E2).

**Depends on**: T004.

---

## Phase 4 — Verification & polish

### T007 · Full suite green, no regressions · `verify`

```bash
uv run pytest backend/tests/unit/event/ \
  backend/tests/unit/core/merge/test_submit_coalesced_recompute.py
```

**Done when**: all of T002's 59 baseline cases still pass (`test_limits.py`, `test_node_action.py`,
`test_group_action.py`, `test_submit_coalesced_recompute.py`) plus the new cases from T005/T006
(SC-005). No case weakened or deleted to make the suite pass.

**Depends on**: T005, T006.

### T008 · Changelog fragment · `docs` `[P]`

**File**: `changelog/+inbox-162-prefect-related-resources.fixed.md`

A `fixed` fragment in the repo's towncrier style (prose, user-facing, no ticket-number preamble —
match `changelog/+ifc3041.fixed.md`). It must convey (plan.md D4):

- **Who was affected**: deployments that do not set the related-resources limit — i.e. anything not
  running the shipped image.
- **The symptom**: node mutation events touching many related resources were silently dropped by
  Prefect — no automation, no trigger, no webhook, no activity-feed entry — while the mutation
  itself succeeded.
- **Shipped image unaffected**: it configures 500 and keeps its current capacity exactly.
- **The malformed-value change**: a non-numeric value now fails at startup instead of being
  silently treated as 500 (critique E3).
- Honest framing: events are now *delivered, truncated to the real limit* — not "nothing is ever
  lost" (critique P1). Mention that the per-event budget on an unconfigured deployment is
  correspondingly smaller than the previous, unhonoured figure (critique P2).

**Depends on**: T004.

### T009 · Format and lint · `verify`

```bash
uv run invoke format
uv run invoke lint
```

**Done when**: both clean. Re-run T007 afterwards if formatting touched any test file.

**Depends on**: T007, T008.

### T010 · Governance diff check · `verify`

```bash
git diff --name-only origin/develop...HEAD
```

**Done when**: the changed-file list contains **only** `backend/infrahub/events/limits.py`, the two
test files, the changelog fragment, and this spec directory. Specifically confirm **no** changes to
`development/Dockerfile` (FR-006), migrations, schema, GraphQL/REST contracts, auth, `.github/`,
dependency blocks, or generated files. Any hit is a governance stop, not something to fix in place.

**Depends on**: T009.

---

## Dependency graph

```text
T001 → T002 → T003 ⇄ T004 → ┬─ T005 [P] ─┐
                            ├─ T006 [P] ─┴→ T007 ─┐
                            └─ T008 [P] ──────────┴→ T009 → T010
```

`T003 ⇄ T004`: the test migration and the implementation must land together — each is red without
the other (see T003's note). Everything downstream of T004 is independent and `[P]`-parallelisable.

## Traceability

| Requirement | Covered by |
|---|---|
| FR-001 (read effective setting) | T004 |
| FR-002 (default 100) | T004, T005 |
| FR-003 (no 500 in module) | T004, T010 |
| FR-004 (all config sources / aliases) | T004, T005 |
| FR-005 (non-positive → default) | T004, T005 |
| FR-006 (image untouched) | T010 |
| FR-007 (signatures unchanged) | T004, T007 |
| FR-008 (resolved at call time) | T004, T003/T005/T006 (all rely on live override) |
| FR-009 (changelog) | T008 |
| SC-001 / US1 | T006 |
| SC-002 / US2 | T006 |
| SC-003 / US3 | T005 |
| SC-004 | T005 |
| SC-005 | T002, T007 |
