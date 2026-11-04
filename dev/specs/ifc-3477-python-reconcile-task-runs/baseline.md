# Computed-attribute test baseline

Recorded on 2026-11-04 at commit `dadd46e4f9`, before any code change for this feature (task T002).

## Commands

```bash
uv run pytest backend/tests/component/computed_attribute/ -v
uv run pytest backend/tests/functional/computed_attributes/ -v
```

## Results

| Suite | Passed | Failed | Skipped | Duration |
|-------|--------|--------|---------|----------|
| `backend/tests/component/computed_attribute/` | 32 | 0 | 0 | 238 s |
| `backend/tests/functional/computed_attributes/` | 13 | 0 | 0 | 194 s |

No test failed before the change, so any later failure in these suites comes from this feature.

## Branch base

The branch is based on `origin/stable` (merge base `5ca7c05db8`). On 2026-11-04 the pull requests #11093 and #11095 were open, so the branch was not rebased (task T001). `origin/stable` had one later commit, `8c3a8926a5`, which changes only `backend/tests/component/graphql/auth/test_permissions_on_branch.py` and does not affect these suites.
