---
description: Push the current branch and open a pull request via gh
argument-hint: "[--title \"<title>\"] [--body \"<body>\"] [--draft] [--base <branch>]"
allowed-tools:
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git branch:*)
  - Bash(git rev-parse:*)
  - Bash(git push:*)
  - Bash(gh pr create:*)
  - Bash(gh pr view:*)
---

# Open Pull Request

Push the current branch and open a GitHub PR. This command is the "PR" half of the commit → push → PR flow (use `/git-commit` for the commit + push half if commits aren't yet on remote).

**Arguments:**

- `--title "<title>"` (optional): PR title (≤70 chars). If omitted, derive from `git log <base>..HEAD --oneline` and the diff.
- `--body "<body>"` (optional): PR body. If omitted, draft a `## Summary` / `## Test plan` body from the diff.
- `--draft` (optional): Open as a draft PR.
- `--base <branch>` (optional): Base branch. Defaults to `develop`.

## Preconditions

1. Working tree must be clean. If anything is uncommitted or staged, **stop** and surface it to the user — do not auto-commit drift.

   ```bash
   git status --porcelain
   ```

   If non-empty, instruct the user to commit (e.g. via `/git-commit`) before proceeding.

2. The branch must have at least one commit ahead of `--base`:

   ```bash
   git log --oneline "${BASE:-develop}..HEAD"
   ```

   If empty, stop and inform the user there is nothing to PR.

3. Never open a PR with `--base stable`, `--base develop` only if the current branch *is* a feature branch (refuse if HEAD is itself `develop` or `stable`).

## Steps

1. **Confirm intent**: show the user the proposed title, body, base, and `--draft` flag (if any). Wait for approval before pushing.

2. **Push (set upstream if needed)**:

   ```bash
   if ! git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
     git push -u origin "$(git branch --show-current)"
   else
     git push
   fi
   ```

3. **Open the PR** using a HEREDOC body to preserve formatting:

   ```bash
   gh pr create \
     --base "${BASE:-develop}" \
     --title "<approved title>" \
     --body "$(cat <<'EOF'
   ## Summary
   <bullets>

   ## Test plan
   <checklist>
   EOF
   )" \
     ${DRAFT:+--draft}
   ```

4. **Report the PR URL** returned by `gh pr create`.

## Drafting title and body from the diff (when arguments omitted)

If `--title` is omitted:

- Read `git log --oneline <base>..HEAD` and `git diff <base>...HEAD --stat`.
- Compose `<type>(<scope>): <short description>` following the conventions in `dev/commands/git-commit.md`.
- Keep ≤70 chars.

If `--body` is omitted:

- `## Summary`: 1-3 bullets explaining *what changed* and *why*.
- `## Test plan`: bulleted checklist of how to verify the change locally.

Show the drafted title and body to the user for approval before invoking `gh pr create`.

## Notes

- Use this command after commits are already on `origin/<branch>` or about to be pushed. It does not create commits.
- For split-PR workflows (e.g. driven by `/feature-flow` Phase 6c), invoke this command per branch and add a `Depends on #<sibling-PR>` line at the top of dependent bodies.
- If the PR already exists for the current branch, `gh pr create` will fail — use `gh pr view --web` to open the existing one instead.
