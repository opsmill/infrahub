# Quickstart: verifying the `Sequence` typing change

All commands run from the repo root of the `pha/INBOX-8` worktree.

## 1. The type error is genuinely gone (SC-001)

```bash
uv run mypy backend/infrahub/core/manager.py backend/infrahub/core/relationship/model.py
```

Expect: no errors. In particular no `arg-type` error on the `rel_manager.update(...)` call at
`backend/infrahub/core/manager.py:~1345`, and no suppression comment on that line.

## 2. The check is meaningful, not vacuously passing (SC-001)

`warn_unused_ignores` is off in this repo, so mypy will not tell you on its own that the removed
suppression was load-bearing. Prove the gate is live by reverting just the signature and confirming
the error comes back:

```bash
# temporarily restore the invariant list annotation in relationship/model.py, then:
uv run mypy backend/infrahub/core/manager.py
# expect: error: Argument "data" ... has incompatible type "list[PeerWithRelationshipMetadata]" ...
#                 [arg-type]
git checkout backend/infrahub/core/relationship/model.py   # undo the experiment
```

If the error does **not** reappear, the fix is not being tested by anything and SC-001 is
meaningless — stop and investigate (`arg-type` must not be in `infrahub.core.manager`'s
`disable_error_code` list in `pyproject.toml`).

## 3. The suppression count dropped by exactly one (SC-002)

```bash
grep -c 'type: ignore\[arg-type\]' backend/infrahub/core/manager.py   # expect 1 (was 2)
grep -rn 'type: ignore' backend/infrahub/core/relationship/model.py   # expect no new ignores
```

The one remaining ignore in `manager.py` is the unrelated `**dict` splat at line ~1178. The
`backend/infrahub/menu/repository.py:105` ignore is deliberately untouched (FR-006).

## 4. Lint and the local gate (SC-003)

```bash
uv run ruff check backend/infrahub/core/relationship/model.py backend/infrahub/core/manager.py
uv run ruff format --check backend/infrahub/core/relationship/model.py backend/infrahub/core/manager.py
```

Then the full local pre-push gate:

```bash
/pre-ci
```

## 5. Existing behaviour is preserved (SC-004)

The relationship-manager component tests exercise the `list`, single-`Node`, and `None` paths:

```bash
uv run pytest backend/tests/component/core/test_relationship_manager.py -v
```

Expect: all pass, with no changes to their existing assertions.

The live bare-`str` caller (`core/ipam/reconciler.py:168`, see research R7) is the one that the
`str` carve-out protects. Exercise it:

```bash
uv run pytest backend/tests/unit/core/ipam -q
```

## 6. The newly-permitted non-`list` sequence works (SC-005)

```bash
uv run pytest backend/tests/component/core/test_relationship_manager.py -k tuple -v
```

Expect: the added test passes, showing a `tuple` of peers produces the same relationship set as the
equivalent `list`.

## 7. Governance scan (no out-of-bounds surface touched)

```bash
git diff --name-only origin/develop...HEAD
```

Expect only:

- `backend/infrahub/core/relationship/model.py`
- `backend/infrahub/core/manager.py`
- `backend/tests/component/core/test_relationship_manager.py`
- `dev/specs/005-manager-update-sequence-type/*`
- possibly a `changelog/` fragment

Expect **nothing** under `backend/infrahub/core/migrations/`, `backend/infrahub/core/schema/`,
`backend/infrahub/graphql/`, auth/permission modules, `.github/`, or dependency blocks of
`pyproject.toml` / lockfiles.
