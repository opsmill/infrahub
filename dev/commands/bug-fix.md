---
description: Fix a bug based on /bug-analyze root cause and /bug-test failing test
argument-hint: <issue number or URL>
---

# Bug fixer

## Your role

You are a senior engineer implementing a bug fix. Two prior steps have already been completed:
`/bug-analyze` identified the root cause, and `/bug-test` wrote a failing test (which has been
reviewed and approved). Your job is to fix the root cause identified by the analyst. The test
is your validation criteria -- it must pass -- but the analyst's root cause analysis is what
drives your fix, not the test.

## Tool usage

- Use the `Read` tool to read files -- do NOT use `cat` or `head`/`tail` in Bash.
- Use the `Glob` tool to find files -- do NOT use `find` or `ls -R` in Bash.
- Use the `Grep` tool to search file contents -- do NOT use `grep` or `rg` in Bash.
- Reserve Bash for git commands, `gh` CLI, and commands that require shell execution.

## Input and setup

Parse `$ARGUMENTS` to extract the issue number or URL. If a URL is provided, extract the
issue number from it.

Find the draft PR opened by `/bug-test`:

```bash
gh pr list --head ai-bug-pipeline-<issue_number> --json number,title,body,headRefName --jq '.[0]'
```

If no PR is found, try a broader search:

```bash
gh pr list --search "head:ai-bug-pipeline-<issue_number>" --json number,title,body,headRefName --jq '.[0]'
```

Validate the PR:
- PR body must contain `AGENT_TEST_COMPLETE`. If not, inform the developer:
  "No `AGENT_TEST_COMPLETE` marker found. Run `/bug-test` first." and **STOP**.
- PR body must NOT contain `AGENT_FIX_COMPLETE`. If it does, inform the developer:
  "Fix has already been applied (`AGENT_FIX_COMPLETE` present)." and **STOP**.
- Search PR comments for `AGENT_REVIEW_VERDICT: TEST_APPROVED` (any author):
  ```bash
  gh api "repos/{owner}/{repo}/issues/<pr_number>/comments" --paginate --jq '.[] | select(.body | contains("AGENT_REVIEW_VERDICT: TEST_APPROVED")) | .id' | head -1
  ```
  If no `TEST_APPROVED` verdict is found, inform the developer:
  "Test not yet approved by reviewer. Wait for `TEST_APPROVED` verdict." and **STOP**.

Check out the PR branch:

```bash
git fetch origin
git checkout <branch name from PR>
```

Read `.bug-analysis.md` from the repo root for the root cause and fix strategy.
If the file is missing, inform the developer: "Run `/bug-analyze <issue>` first." and **STOP**.

Read the PR diff to understand the failing test.

## Implement the fix

1. Read the analyst's fix strategy from `.bug-analysis.md` (the "Fix strategy" section).
   This is your **starting point**: follow the recommended approach, scope, and "Do NOT"
   guardrails. If you believe the strategy is wrong after reading the code, explain why
   to the developer before deviating -- do not silently ignore it.

2. Read the failing test in the PR diff. This is your validation criteria -- the fix must
   make it pass -- but design your fix based on the analyst's fix strategy and root cause,
   not on what the test checks.

3. Before writing any code, reason explicitly about the fix:
   - Is the root cause a shallow symptom (null check, off-by-one) or a deeper design issue?
   - If shallow: a targeted fix is appropriate.
   - If deeper: a proper fix may require refactoring the affected component.
     In that case, do it: do NOT paper over a design flaw with a guard clause.
   - State your reasoning to the developer before implementing.

4. Implement the fix:
   - Fix the actual root cause, not just the symptom.
   - Do NOT change the test the test-writer wrote.
   - Do NOT refactor code unrelated to the root cause.
   - If the proper fix requires changing more than expected, that is fine:
     explain why so the reviewer understands the scope.
   - Stage files by name (`git add path/to/file`) -- never use `git add .` or `git add -A`,
     as unrelated files in the working tree will be committed by mistake.
   - Commit the fix with an explicit commit message.

5. **Verify the replication test passes.** Run the specific test the test-writer wrote
   using the same runner they used:
   - Backend: `uv run pytest path/to/test_file.py::TestClass::test_name -x -v`
   - Frontend unit/component: `cd frontend/app && npm run test path/to/test`
   - Frontend E2E: `cd frontend/app && npx playwright test path/to/test`
   - If the test still FAILS, revisit your fix. Do NOT proceed until it passes.
   - Before continuing, verify `git diff` shows no changes to the test file(s) from the
     test-writer's PR. If you accidentally modified a test file, revert those changes.

6. Run pre-CI checks before pushing. Fix any issues they surface and commit the fixes
   separately (do NOT amend previous commits).

   **Phase 1 -- Auto-fix formatting (sequential, in this order):**
   ```bash
   uv run invoke format
   uv run invoke docs.format
   (cd frontend/app && npx biome check --write .)
   ```

   If Phase 1 changed any source files, you must re-run from Phase 2.

   **Phase 2 -- Regenerate & lint (run all in parallel):**
   - `uv run invoke main.lint`
   - `uv run invoke backend.lint`
   - `uv run invoke backend.generate`
   - `uv run invoke schema.generate-graphqlschema`
   - `uv run invoke schema.generate-jsonschema`
   - `uv run invoke docs.generate`
   - `uv run invoke docs.lint`
   - `(cd frontend/app && npm run codegen:graphql)`
   - `(cd frontend/app && npm run codegen:openapi)`
   - `(cd frontend/app && npx betterer --update)`

   Stage any files changed by generation or betterer by name (`git add path/to/file`)
   -- never use `git add .` or `git add -A`.

   **Phase 3 -- Unit tests:**
   ```bash
   uv run invoke backend.test-unit
   ```
   If the fix touches frontend code, also run:
   ```bash
   cd frontend/app && npm run test
   ```

   If any check fails, fix the issue and re-run that check before proceeding.

   **Phase 4 -- Changelog entry:**
   Create a changelog fragment for this bug fix. Use the issue number and the `fixed` type:
   ```bash
   uv run towncrier create -c "<user-facing description of what was fixed>" <issue_number>.fixed.md
   ```
   Write the message from the user's perspective, in past tense, one sentence, no technical
   jargon (see `dev/guidelines/changelog.md`). Commit the generated file.

7. **Scope check:** If the fix requires changes to more than ~10 files or fundamentally
   alters a public API contract, inform the developer explaining the scope and **STOP**.

8. Update the PR:
   - Update the PR title to: `fix: <short description> (closes #<issue number>)`
   - Update the PR body: read the file `.github/pull_request_template.md` from the
     repository and fill in every section using the context from this task.
     Do not skip or remove any section from the template. For sections where you have
     nothing meaningful to add (e.g., Screenshots), write "N/A" rather than inventing content.
   - Make sure the hidden marker `<!-- AGENT_FIX_COMPLETE -->` appears
     somewhere in the PR body: it is used by downstream automation to detect this PR.
   - Use `gh pr edit` to update the title and body.

9. **Push your fix commits to the PR branch LAST** (after the PR body update):
   ```bash
   git push -u origin <branch>
   ```

## When to stop

If at any point you determine that:
- The analyst's root cause is incorrect and the real cause is substantially different,
- The test cannot be made to pass with a correct fix (i.e., it tests the wrong behavior),
- The fix is beyond the scope an automated agent should handle,

then inform the developer explaining your findings and **STOP**. Do NOT push to the PR.
