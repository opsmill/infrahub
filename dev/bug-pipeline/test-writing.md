# Test-writing steps

These are the shared steps for writing a failing test that reproduces a confirmed bug.
Read this file when directed by your main prompt.

Before starting, you should already have:
- The root cause analysis (root cause, affected files, fix strategy)

## Step 0: Create working branch

Create a working branch from `origin/stable`:

```bash
git fetch origin stable
git checkout -b ai-bug-pipeline-<issue_number>-<short-slug> origin/stable
```

- Name: `ai-bug-pipeline-<issue_number>-<short-slug>` (lowercase, hyphens only, max 50 chars total).
- If the branch already exists, check it out instead of creating a new one.

## Step 1: Read testing documentation

Read root `AGENTS.md` and `dev/documentation-architecture.md` to understand the project
structure and determine which code packages are related to the bug. Then read the testing
guidelines relevant to the bug:
- Backend bugs -- read BOTH of these:
  - `dev/knowledge/backend/testing.md` (test infrastructure, fixtures, test types)
  - `dev/guidelines/backend/testing.md` (testing standards, patterns, best practices)
- Frontend bugs -- read ALL of these:
  - `dev/guides/frontend/writing-unit-tests.md`
  - `dev/guides/frontend/writing-component-tests.md`
  - `dev/guides/frontend/writing-e2e-tests.md`

## Step 2: Read conftest files

Read the `conftest.py` files in the target test directory AND its parent directories
(up to `backend/tests/conftest.py`) to understand available fixtures, their scopes,
and setup/teardown patterns. Do NOT reinvent setup logic that already exists as a fixture.

## Step 3: Check reusable utilities

Check `backend/tests/helpers/` and `backend/tests/adapters/` for reusable utilities:
- `helpers/test_app.py` -- base test classes (`TestInfrahub`, `TestInfrahubApp`)
- `helpers/graphql.py`, `helpers/events.py`, `helpers/db_validation.py` -- domain helpers
- `adapters/` -- `BusRecorder`, `BusSimulator`, `MemoryCache`, `FakeLogger`
Use these instead of writing your own test infrastructure.

## Step 4: Read existing tests

Read 2--3 existing tests in the target test directory to understand naming conventions,
class structure, and import patterns before writing your own test.

## Step 5: Choose the test type

Use the "When to use" / "When NOT to use" guidance in
`dev/knowledge/backend/testing.md` and the testing standards in
`dev/guidelines/backend/testing.md` to pick the right test level.
- **Backend:** pytest. Types: unit (`backend/tests/unit/`), component (`backend/tests/component/`),
  functional (`backend/tests/functional/`), integration docker (`backend/tests/integration_docker/`).
  Use existing schema fixtures and helpers when available.
- **Frontend:** Vitest for unit/component tests (colocated with source as `.test.ts`),
  pytest-playwright for E2E (`tests/e2e/` at the repo root, see its README).
  Use BDD GIVEN/WHEN/THEN structure. Use factories from `tests/fake/`.

## Step 6: Write the test

Write a single targeted test that reproduces the bug:
- **Assert the CORRECT/EXPECTED behavior.** The test fails because the bug prevents the
  expected behavior from happening. Do NOT assert that the buggy behavior succeeds.
  For example: if the bug is "duplicate branches can be created," assert that the second
  creation raises an error or that only one branch exists. This assertion will FAIL on
  buggy code (because the error is not raised / duplicates exist) and PASS once fixed.
- The test MUST exercise the **actual production code path**, not a reimplementation of it.
  Call the real functions/classes from the source code. Do NOT copy production logic
  into the test file.
- Test **observable behavior**, not internal implementation details. For example, test that
  an API returns wrong data or that a constraint is violated -- do NOT test that a specific
  constructor receives specific kwargs.
- **Test the affected code path.** The test should exercise the code identified
  in the analyst's "Affected files" section, not a lower-level abstraction.
  If the analyst identified a bug in a workflow function, test that function -- do not
  test the raw database operation it calls internally. A test that can pass without
  changing the affected code path is testing the wrong thing.
- Place it in the correct test folder following project conventions.
  Test files mirror source structure: `infrahub/core/foo.py` -> `tests/unit/core/test_foo.py`
- If adding to an existing test file is more appropriate than creating a new one, do that.

## Step 7: Verify the test FAILS

**CRITICAL: Verify the test FAILS on the current code.** Run it:
- Backend: `uv run pytest path/to/test_file.py::TestClass::test_name -x -v`
- Frontend unit/component: `cd frontend/app && pnpm run test path/to/test`
- Frontend E2E (repo root; needs a locally built image: `uv run invoke dev.build`): `INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false uv run pytest -c tests/e2e/pytest.ini tests/e2e/path/to/test.py -x -v`
- If a test run takes more than 5 minutes, kill it and investigate why.
- The test must fail with an **assertion error that directly relates to the root cause**
  described by the analyst. For example, if the root cause is "no uniqueness enforcement,"
  the failure should be something like `AssertionError: Expected ValidationError but none
  was raised` or `assert 2 == 1` (found 2 duplicates when expecting 1).
- If the test **PASSES**, your assertions are wrong -- you are likely asserting buggy
  behavior instead of correct behavior. Flip your assertions to assert what SHOULD happen.
- If the test fails for the **wrong reason** (import error, fixture missing, syntax error),
  fix those issues and re-run until it fails for the reason described in the root cause.

## Step 8: Format and lint

Run formatting and linting on the test file(s). Fix any issues before committing.

**Format** Python code:
```bash
uv run invoke format
```

**Lint** (YAML, Ruff, ty, mypy, markdownlint, vale):
```bash
uv run invoke lint
```

**Frontend** (if applicable):
```bash
cd frontend && pnpm exec biome check --write .
```

## Step 9: Commit test files

Commit ONLY the test file(s). Do NOT touch production code.
Stage files by name (`git add path/to/test_file.py`) -- never use `git add .` or
`git add -A`, as unrelated files in the working tree will be committed by mistake.
Use commit message: `test: add failing test for #<issue_number>`

## Step 10: Open draft PR

Push the branch and open a **draft Pull Request**:

```bash
git push -u origin <branch>
gh pr create --draft --base stable --title "<title>" --body-file .agent-tmp/gh-body.md
```

Write the PR body to `.agent-tmp/gh-body.md` first (using the Write tool), then pass it
via `--body-file`.

- Title: `test: failing test for #<issue_number> -- <short description>`
- Target branch: `stable`
- PR body with this exact structure:

````markdown
## Analyst's findings (summary)

> **Root cause:** <copied from analysis>
> **Affected files:**
> <copied from analysis>

## Replication test

**Test file:** `path/to/test_file.ext`
**Test name:** `test_name_here`

**What it tests:** <one sentence explaining the observable behavior being asserted>

**Verification:** Test confirmed FAILING on current code.
**Failure reason:** <one sentence explaining HOW the test fails and why that proves the bug>

<details><summary>Failure output (last 20 lines)</summary>

```
<paste the relevant failure output>
```

</details>

## Test expectations

<what the test asserts and any edge cases it covers -- NOT how to fix the bug>

<!-- AGENT_TEST_COMPLETE -->
````

Post a short comment on the issue linking to the draft PR.

## Failure handling

If the test cannot be made to fail for the right reason after 3 attempts, **STOP**
and escalate as described in your main prompt. Do NOT open a PR or include the
`AGENT_TEST_COMPLETE` marker.
