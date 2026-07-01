# Quickstart: running the multi-environment validation suites

Two suites, two cost tiers.

## Deterministic prong (CI-resident, fast)

Real local Git remote + in-process server. No Docker stack.

```bash
# Whole file
uv run pytest backend/tests/integration/git/test_multi_env_writeback.py -v

# Single scenario (debug a failure in place — see AGENTS.md --pdb guidance)
uv run pytest backend/tests/integration/git/test_multi_env_writeback.py::<node_id> -s --pdb
```

- Defect reproductions are `xfail(strict)`: a green run shows them as `xfailed`. If one becomes
  `XPASS`, the underlying defect was fixed — convert that test to a plain assertion.
- Regression guards (US3, US4§3/§4, US5§1) are normal passing tests.

## Full-stack prong (opt-in, heavier)

Two full testcontainers stacks (a development instance + a read-only consumer instance) sharing one
remote. No multi-worker pool. Requires a local image.

```bash
# Build the image once
uv run invoke dev.build

# Run the two-instance Approach-A demonstration (US2)
INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest backend/tests/integration_docker/test_multi_env_approach_a.py -v
```

- This suite is **excluded from the default CI run** (opt-in marker / manual workflow).
- It covers US2 only: consumer isolation and promotion-via-reimport across two instances. The #9568
  reproduction lives entirely in the deterministic prong.

## What "done" looks like

- US2, US3, US4§3, US4§4, US5§1 — green.
- US1, US4§1, US4§2, US5§2 — `xfailed` (tracked open defects).
- Zero flake on the deterministic prong across repeated runs.
- For US4§1 and US5§2: once they fail as predicted, a GitHub issue is **drafted** (issue-reporting
  skill, one file per defect) for review — never auto-submitted.
