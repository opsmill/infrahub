# Fix implementation steps

These are the shared steps for implementing a bug fix.
Read this file when directed by your main prompt.

Before starting, you should already have:
- The root cause analysis (root cause, affected files, fix strategy)
- The PR with the failing test
- The working branch checked out

## Step 1: Read fix strategy

Read the analyst's fix strategy. This is your **starting point**: follow the recommended
approach, scope, and "Do NOT" guardrails. If you believe the strategy is wrong after reading
the code, explain why before deviating -- do not silently ignore it.

## Step 2: Read failing test

Read the failing test in the PR diff. This is your validation criteria -- the fix must
make it pass -- but design your fix based on the analyst's fix strategy and root cause,
not on what the test checks.

## Step 3: Reason about the fix

Before writing any code, reason explicitly about the fix:
- Is the root cause a shallow symptom (null check, off-by-one) or a deeper design issue?
- If shallow: a targeted fix is appropriate.
- If deeper: a proper fix may require refactoring the affected component.
  In that case, do it: do NOT paper over a design flaw with a guard clause.

## Step 4: Implement the fix

- Fix the actual root cause, not just the symptom.
- Do NOT change the test the test-writer wrote.
- Do NOT refactor code unrelated to the root cause.
- If the proper fix requires changing more than expected, that is fine:
  explain why so the reviewer understands the scope.
- Stage files by name (`git add path/to/file`) -- never use `git add .` or `git add -A`,
  as unrelated files in the working tree will be committed by mistake.
- Commit the fix with an explicit commit message.

## Step 5: Verify replication test passes

Run the specific test the test-writer wrote using the same runner they used:
- Backend: `uv run pytest path/to/test_file.py::TestClass::test_name -x -v`
- Frontend unit/component: `cd frontend/app && pnpm run test path/to/test`
- Frontend E2E (repo root; needs a locally built image: `uv run invoke dev.build`): `INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false uv run pytest -c tests/e2e/pytest.ini tests/e2e/path/to/test.py -x -v`
- If the test still FAILS, revisit your fix. Do NOT proceed until it passes.
- Before continuing, verify `git diff` shows no changes to the test file(s) from the
  test-writer's PR. If you accidentally modified a test file, revert those changes.

## Step 6: Pre-CI checks

Run pre-CI checks before pushing. Fix any issues they surface and commit the fixes
separately (do NOT amend previous commits).

**Phase 1 -- Auto-fix formatting (sequential, in this order):**
```bash
uv run invoke format
uv run invoke docs.format
(cd frontend && pnpm exec biome check --write .)
```

If Phase 1 changed any source files, you must re-run from Phase 2.

**Phase 2a -- Regenerate schemas (run in parallel):**
- `uv run invoke backend.generate`
- `uv run invoke schema.generate-graphqlschema`
- `uv run invoke schema.generate-jsonschema`
- `uv run invoke docs.generate`

**Phase 2b -- Lint & frontend codegen (run in parallel, after 2a completes):**
- `uv run invoke main.lint`
- `uv run invoke backend.lint`
- `uv run invoke docs.lint`
- `(cd frontend/app && pnpm run codegen:graphql)`
- `(cd frontend/app && pnpm run codegen:openapi)`
- `(cd frontend/app && pnpm exec betterer --update)`

Stage any files changed by generation or betterer by name (`git add path/to/file`)
-- never use `git add .` or `git add -A`.

**Phase 3 -- Unit tests:**
```bash
uv run invoke backend.test-unit
```
If the fix touches frontend code, also run:
```bash
cd frontend/app && pnpm run test
```

If any check fails, fix the issue and re-run that check before proceeding.

**Phase 4 -- Changelog entry:**
Create a changelog fragment for this bug fix. Use the issue number and the `fixed` type:
```bash
uv run towncrier create -c "<user-facing description of what was fixed>" <issue_number>.fixed.md
```
Write the message from the user's perspective, in past tense, one sentence, no technical
jargon (use the `creating-changelog-entries` skill). Commit the generated file.

## Step 7: Scope check

If the fix requires changes to more than ~10 files or fundamentally alters a public API
contract, **STOP** and escalate as described in your main prompt.

## Step 8: Update the PR

- Update the PR title to: `fix: <short description> (closes #<issue number>)`
- Update the PR body: read the file `.github/pull_request_template.md` from the
  repository and fill in every section using the context from this task.
  Do not skip or remove any section from the template. For sections where you have
  nothing meaningful to add (e.g., Screenshots), write "N/A" rather than inventing content.
- Make sure the hidden marker `<!-- AGENT_FIX_COMPLETE -->` appears
  somewhere in the PR body: it is used by downstream automation to detect this PR.
- Use `gh pr edit` to update the title and body.

## Step 9: Push

**Push your fix commits to the PR branch LAST** (after the PR body update):
```bash
git push -u origin <branch>
```

Post a comment on the issue linking to the updated PR.

## When to stop

If at any point you determine that:
- The analyst's root cause is incorrect and the real cause is substantially different,
- The test cannot be made to pass with a correct fix (i.e., it tests the wrong behavior),
- The fix is beyond the scope an automated agent should handle,

then **STOP** and escalate as described in your main prompt. Do NOT push to the PR.
