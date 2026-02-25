---
description: Stage, commit, and push changes with a conventional commit message
argument-hint: [message] [--no-push] [--amend]
allowed-tools:
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git add:*)
  - Bash(git commit:*)
  - Bash(git push:*)
  - Bash(git branch:*)
  - Bash(git stash:*)
  - Bash(git rev-parse:*)
---

# Commit and Push

Stage all changes, create a conventional commit, and push to the remote branch.

**Arguments:**
- `message` (optional): A commit message or description of what changed. If not provided, auto-generate from the diff.
- `--no-push` (optional): Skip pushing to remote after committing.
- `--amend` (optional): Amend the previous commit instead of creating a new one.

## Steps to Follow

1. **Check current state**:
   ```bash
   git status
   git diff --stat
   git diff --cached --stat
   ```
   - If there are no changes (working tree clean, nothing staged), stop and inform the user.

2. **Analyze the changes**:
   ```bash
   git diff
   git diff --cached
   ```
   - Read through all staged and unstaged changes to understand what was modified.
   - Identify the type of change (feat, fix, docs, refactor, test, chore).
   - Identify a scope if applicable (e.g., backend, frontend, schema, api).

3. **Check recent commit history** for style consistency:
   ```bash
   git log --oneline -10
   ```

4. **Compose the commit message**:
   - If the user provided a message argument, use it as the basis, but ensure it follows conventional commit format.
   - If no message was provided, generate one from the diff analysis.
   - Format: `<type>(<scope>): <short description>`
   - Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
   - Scope is optional but encouraged (e.g., `frontend`, `backend`, `schema`, `api`, `docs`)
   - Keep the first line under 72 characters
   - Add a blank line and bullet points for multi-file or complex changes
   - Include issue references if mentioned by the user (e.g., `[#1234]`, `[IFC-1234]`)

5. **Present the commit message to the user** and ask for confirmation before proceeding. Show:
   - The proposed commit message
   - A summary of files being committed
   - Whether this will push to remote

6. **Stage changes**:
   ```bash
   git add -A
   ```

7. **Commit**:
   - For a new commit:
     ```bash
     git commit -m "<message>"
     ```
   - For amending (only if `--amend` flag was passed):
     ```bash
     git commit --amend -m "<message>"
     ```
   - Use a HEREDOC for multi-line messages:
     ```bash
     git commit -m "$(cat <<'EOF'
     <type>(<scope>): <short description>

     - Detail 1
     - Detail 2
     EOF
     )"
     ```

8. **Push to remote** (unless `--no-push` was passed):
   - Check if the branch has an upstream:
     ```bash
     git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null
     ```
   - If no upstream, set it:
     ```bash
     git push -u origin $(git branch --show-current)
     ```
   - If upstream exists, push normally:
     ```bash
     git push
     ```
   - If amending, use force-with-lease:
     ```bash
     git push --force-with-lease
     ```

9. **Confirm success**: Show the final commit hash and remote status:
   ```bash
   git log --oneline -1
   ```

## Commit Message Guidelines

Follow the project's conventional commit format from `dev/guidelines/git-workflow.md`:

| Type | When to use |
|------|------------|
| `feat` | New feature or enhancement |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `refactor` | Code refactoring without behavior changes |
| `test` | Adding or updating tests |
| `chore` | Maintenance tasks, dependencies, tooling |

### Scope Examples

- `feat(frontend)`: New UI feature
- `fix(api)`: API bug fix
- `chore(deps)`: Dependency update
- `refactor(schema)`: Schema refactoring
- `docs(guides)`: Documentation update

### Good Commit Messages

```text
feat(frontend): add search results page with pagination [#7890]
fix(api): handle null values in filter queries
chore(deps): update pydantic to 2.10
refactor(backend): extract validation logic into shared utils
```

## Important Rules

- Always show the proposed commit message and get user confirmation before committing
- Never commit secrets, API keys, credentials, or `.env` files
- If you see suspicious files (`.env`, credentials, tokens), warn the user and exclude them
- Use `--force-with-lease` (never `--force`) when pushing amended commits
- Never force push to `stable`, `develop` or any `release-*` branches
