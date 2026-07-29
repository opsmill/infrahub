# Tasks: `Sequence` typing for `RelationshipManager.update()`

**Feature**: `005-manager-update-sequence-type` | **Branch**: `pha/INBOX-8`

**Inputs**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md) · [critique.md](./critique.md)

Dependency-ordered. `[P]` marks tasks that may run in parallel with the previous one.

## Phase A — Baseline (prove the gate is live before changing anything)

### T001 — Capture the failing baseline

Confirm the suppression is load-bearing *before* removing it, so the change is verifiably tested
(quickstart §2; research R8).

1. Temporarily delete only the `# type: ignore[arg-type]` on the `rel_manager.update(...)` call in
   `backend/infrahub/core/manager.py` (leave the signature alone).
2. Run `uv run mypy backend/infrahub/core/manager.py`.
3. Record the exact `arg-type` error text in the implementation report.
4. Restore the file (`git checkout backend/infrahub/core/manager.py`).

**Gate**: if no `arg-type` error appears, STOP — the premise is wrong and the card needs
re-analysis (check `arg-type` is absent from `infrahub.core.manager`'s `disable_error_code`).

**Files**: `backend/infrahub/core/manager.py` (temporary, reverted)

---

## Phase B — Production change

### T002 — Relocate the `Sequence` import to `collections.abc`

Per research R6. `Sequence` appears in only two places in the file, so this is contained.

1. Remove `Sequence,` from the `from typing import (...)` block in
   `backend/infrahub/core/relationship/model.py`.
2. Add `from collections.abc import Sequence` in the correct import group (stdlib, before the
   `typing` import — let `ruff format`/isort settle ordering).
3. Do **not** touch `Iterable`, `Iterator`, or `Mapping` in the same block (critique E3).

**Files**: `backend/infrahub/core/relationship/model.py`

### T003 — Re-type `data` and widen the runtime narrowing (depends on T002)

The core change (plan D1 + D2). Both edits land together — the annotation and the `isinstance` test
must never be out of step (research R3).

1. In `RelationshipManager.update()`, change the collection member of `data` from
   `list[str | Node | dict[str, Any] | PeerWithRelationshipMetadata]` to
   `Sequence[str | Node | dict[str, Any] | PeerWithRelationshipMetadata]`. Leave every other union
   member unchanged.
2. Replace the narrowing:
   ```python
   if not isinstance(data, list):
   ```
   with:
   ```python
   if isinstance(data, str) or not isinstance(data, Sequence):
   ```
3. Add a short comment on the `str` exclusion explaining **why** (a `str` satisfies `Sequence` but
   represents one peer id, so it must not be iterated). This is a genuine invariant, which is the
   kind of comment `.agents/rules/code-doc-style.md` permits — no ticket ID, no restating the code.
4. Confirm the method body still only *reads* `list_data` (research R2) — no mutation introduced.

**Gate (critique E1)**: run `uv run mypy backend/infrahub/core/relationship/model.py` and confirm
`list_data = data` in the `else` branch type-checks — i.e. mypy narrowed `data` to the `Sequence`
member. If it does not, fix the narrowing shape; **never** add a `type: ignore` to make it pass.

**Files**: `backend/infrahub/core/relationship/model.py`

### T004 — Remove the suppression and its stale comment (depends on T003)

Plan D3 / spec FR-002.

1. In `backend/infrahub/core/manager.py`, delete the `# type: ignore[arg-type]` from the
   `await rel_manager.update(db=db, data=rel_peers_with_metadata)` call.
2. Delete the preceding comment line `# invariant list parameter; update() only reads data, so the
   narrower element type is safe` — it describes a constraint that no longer exists.
3. Leave the unrelated `# type: ignore[arg-type]` on the `**dict` splat (~line 1178) alone.
4. Leave `backend/infrahub/menu/repository.py:105` alone (spec FR-006, research R9).

**Files**: `backend/infrahub/core/manager.py`

---

## Phase C — Tests

### T005 — Test the non-`list` sequence path (depends on T003)

Spec User Story 3 / SC-005. Add to `backend/tests/component/core/test_relationship_manager.py`,
reusing the fixtures `test_many_update` already uses (`db`, `tag_blue_main`, `tag_red_main`,
`person_jack_main`, `branch`) — per `.agents/rules/testing-python.md` ("check
`backend/tests/helpers/schema/` before defining test schemas inline"; reuse over redeclare).

Assert a `tuple` of peers produces the **same** relationship set as the equivalent `list`: both tags
related after `update(data=(tag_blue_main, tag_red_main))` + `save()`. Assert exact expectations
(exact path counts, as the neighbouring tests do) — not mere non-emptiness.

No ticket ID or spec ID in the test name, docstring, or comments.

**Files**: `backend/tests/component/core/test_relationship_manager.py`

### T006 [P] — Test the bare-`str` carve-out explicitly (depends on T003)

Critique E2. The `str` path is currently only *incidentally* covered by diff/merge tests; guard it
deliberately next to T005.

Assert that `update(data=<peer_id_str>)` relates exactly that one peer — and specifically **not** one
peer per character. Reuse the same fixtures as T005.

**Files**: `backend/tests/component/core/test_relationship_manager.py`

---

## Phase D — Verification

### T007 — Type check and lint (depends on T004)

```bash
uv run mypy backend/infrahub/core/manager.py backend/infrahub/core/relationship/model.py
uv run ruff check backend/infrahub/core/relationship/model.py backend/infrahub/core/manager.py \
                  backend/tests/component/core/test_relationship_manager.py
uv run ruff format --check <same files>
```

Confirm SC-002: `grep -c 'type: ignore\[arg-type\]' backend/infrahub/core/manager.py` → `1` (was 2),
and no new suppression anywhere in the diff.

### T008 — Run the affected test suites (depends on T005, T006)

```bash
uv run pytest backend/tests/component/core/test_relationship_manager.py -v
```

All pre-existing tests must pass with **unmodified assertions** (SC-004), plus the two new ones.

If the component tier cannot run in this environment (it needs database containers), record that
explicitly in the implementation report as missing local evidence rather than claiming a pass — CI
will run it on the PR. Do not silently skip.

### T009 — Changelog fragment (depends on T004)

Check `changelog/` conventions and the repo's `creating-changelog-entries` skill. Add a fragment
only if this repo requires one for an internal typing fix; a pure-internal change with no
user-visible effect may legitimately need none. Record the decision either way.

### T010 — Governance scan (depends on T004)

`git diff --name-only origin/develop...HEAD` must touch only the files listed in quickstart §7.
Any hit on migrations, schema, GraphQL contracts, auth, `.github/`, dependency blocks, or generated
files → STOP and escalate instead of opening a PR.

### T011 — Local pre-push gate (depends on T007, T008)

Run `/pre-ci`. It must pass before the PR is opened.

---

## Task summary

| Phase | Tasks | Concern |
|-------|-------|---------|
| A | T001 | Prove the type gate is live before touching it |
| B | T002, T003, T004 | The production change (import, signature + narrowing, suppression removal) |
| C | T005, T006 | Tuple path + `str` carve-out coverage |
| D | T007–T011 | mypy/lint, tests, changelog, governance, pre-CI |

**11 tasks.** Only T006 is parallelizable (`[P]`); everything else is a short dependency chain,
appropriate for an Effort-S change.
