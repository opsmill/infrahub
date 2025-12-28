---
description: Find and fix a previously-ignored ruff rule violation in the codebase
allowed-tools: Bash(ruff check:*), Bash(ruff rule:*), Bash(uv run invoke backend.lint)
argument-hint: <rule-code e.g., PLR0915 or SIM108>
---

# Fix Ruff Rule

Fix the ruff linting rule: $ARGUMENTS

**Important**: First validate that `$ARGUMENTS` matches a valid ruff rule code pattern (e.g., `PLR0915`, `SIM108`, `E501`). If it doesn't look like a valid rule code, ask for clarification before proceeding.

## Context

The pyproject.toml file contains ignored ruff rules in two locations:

1. **Global ignores** in `[tool.ruff.lint]` under the `ignore = [...]` list
2. **Per-file ignores** in `[tool.ruff.lint.per-file-ignores]` under specific file patterns

Some rules have comments indicating they should be investigated and fixed:

- Rules marked with "# Review and change the below later" or similar comments are candidates for fixing
- Rules marked with "# The ignored rules below should be removed once the code has been updated" should be fixed
- Rules with permanent justification comments (like "# pydocstyle" or "# flake8-copyright") are intentionally ignored and should NOT be addressed

## Steps to Follow

1. **Understand the rule**: Run `ruff rule $ARGUMENTS` to understand what the rule checks for and how to fix violations

2. **Locate the ignore statement**: Read pyproject.toml and find where `$ARGUMENTS` is ignored:
   - Check the global `ignore = [...]` list in `[tool.ruff.lint]`
   - Check `[tool.ruff.lint.per-file-ignores]` for file-specific ignores
   - Note any comments explaining WHY the rule is ignored

3. **Assess if the rule should be fixed**:
   - If the rule has a comment indicating it's intentionally ignored (permanent), inform me and ask whether to proceed
   - If the rule is marked for investigation/fixing, proceed with the fix
   - If unclear, ask me before proceeding

4. **Find current violations**: Before removing the ignore, run:

   ```bash
   ruff check --select=$ARGUMENTS --no-fix .
   ```

   This shows what violations exist without modifying any files. Analyze the scope of work.

5. **Present findings**: Before making any changes, summarize:
   - Number of files affected
   - Types of violations found
   - Whether this is a global or per-file ignore
   - Estimated complexity of the fix

   Then ask for approval to proceed with the fixes.

6. **Fix the violations**: For each affected file:
   - Make the minimal necessary changes to comply with the rule
   - Prefer automated fixes where available: `ruff check --select=$ARGUMENTS --fix <file>`
   - For changes that can't be auto-fixed, implement manually
   - Ensure changes maintain code functionality and readability

7. **Remove the ignore statement**: Edit pyproject.toml to remove `$ARGUMENTS` from the appropriate ignore list(s)

8. **Validate**: Run the following to confirm the fix is complete:

   ```bash
   ruff check --select=$ARGUMENTS .
   ```

   The command should return no violations.

9. **Run full linting**: Verify no regressions with:

   ```bash
   uv run invoke backend.lint
   ```

10. **Run relevant tests**: If the changes are non-trivial, run related tests to ensure nothing is broken

## Important Notes

- Do NOT remove rules that are intentionally ignored (have permanent justification)
- If a rule affects many files (>20), fix in batches of ~10 files at a time and ask how to proceed
- Some rules may require refactoring that could introduce bugs - be cautious and test
- If `ruff check --fix` can auto-fix violations, use it but review the changes
- Preserve code functionality - the goal is compliance, not rewriting
- If validation fails after fixes, revert the changes before investigating further
