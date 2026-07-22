# Quickstart: Validating the BLE re-enablement

**Plan**: [plan.md](plan.md) | **Site inventory**: [data-model.md](data-model.md)

Run everything from the repository root. Prerequisite: `uv sync --all-groups` already done (standard dev setup).

## 1. Card acceptance checks

```bash
# SC-001 — zero BLE violations repo-wide (baseline before the change: 78)
uv run ruff check --select=BLE .
# expected: "All checks passed!"

# FR-001 — BLE gone from the global ignore list
grep -n '"BLE"' pyproject.toml
# expected: no match (exit 1)

# SC-002 — card acceptance lint gate
uv run invoke backend.lint
# expected: exit 0 (ruff, ty, mypy all green)
```

## 2. CI-equivalent gates (stricter than the card)

```bash
# the exact CI lint commands (.github/workflows/ci.yml:325-328)
uv run ruff check . --exclude python_sdk
uv run ruff format --check --diff --exclude python_sdk .
# expected: both exit 0
```

## 3. Enforcement mutation check (SC-006)

```bash
# temporarily plant an unjustified blind except in a linted file
cat >> tasks/utils.py <<'EOF'


def _ble_canary() -> None:
    try:
        pass
    except Exception:
        pass
EOF
uv run ruff check --select=BLE tasks/utils.py
# expected: 1 × BLE001 reported (proves the rule is live)
git checkout -- tasks/utils.py   # remove the canary
```

## 4. Suppression audit (SC-003 / SC-004)

```bash
# every suppression is line-targeted, justified, and enumerable in one search
grep -rn "noqa: BLE001" --include="*.py" . --exclude-dir=python_sdk --exclude-dir=.venv
# expected: each hit sits on an `except Exception`/`except BaseException` line
# with a justification comment on or immediately above it

# no bare excepts anywhere in linted code (E722 backstop)
uv run ruff check --select=E722 .
# expected: "All checks passed!"
```

## 5. Behavior-preservation audit for hard-constraint areas (SC-007)

```bash
# migrations + auth diffs must contain ONLY comment/noqa additions
git diff <base>..HEAD -- backend/infrahub/core/migrations/ \
    backend/infrahub/api/auth.py backend/infrahub/api/oauth2.py \
    backend/infrahub/api/oidc.py backend/infrahub/auth/
# expected: every changed hunk adds comments/`# noqa: BLE001` only;
# no executable line added, removed, or reordered
```

## 6. Tests for touched modules (SC-005)

```bash
# the two behavior-relevant tooling narrowings (tasks/release.py → InvalidVersion)
uv run python -c "from packaging.version import Version; Version('1.2.3-foo')"
# expected: raises packaging.version.InvalidVersion (proves the narrowed type
# is exactly what non-standard versions raise)
uv run invoke --list > /dev/null && echo "invoke imports OK"
# expected: "invoke imports OK" (proves tasks/release.py still imports)

# cheap tier — full backend unit suite
uv run invoke backend.test-unit
# expected: passes (same result as base branch)

# the two component-test files that were themselves violation sites
uv run pytest backend/tests/component/core/schema/schema_branch/test_process_idempotency.py \
              backend/tests/component/core/schema/schema_branch/test_uniqueness_propagation.py
# expected: pass (requires local testcontainers; if unavailable, defer to CI and record it)
```

## Expected end state

| Check | Expected |
|-------|----------|
| `ruff check --select=BLE .` | 0 violations (was 78) |
| `"BLE"` in `pyproject.toml` | absent |
| `ruff check . --exclude python_sdk` | exit 0 |
| `invoke backend.lint` | exit 0 |
| `noqa: BLE001` count | equals data-model.md SUPPRESS count, each justified |
| Migration/auth diffs | annotation-only |
| Unit tests | green |

**Rollback**: single-commit revert, or re-add `"BLE"` to the `[tool.ruff.lint]` ignore list — the code fixes remain valid either way (narrowed handlers and justified suppressions are correct with or without the rule active).

**CI-only verification (accepted)**: the two `tests/integration/git/conftest.py` narrowings (`httpx.HTTPError`) are exercised only by CI's integration tier; if CI shows the poll loops now failing on something httpx-shaped that isn't `HTTPError`, fall back to the documented SUPPRESS treatment for those two sites (data-model.md Batch D).
