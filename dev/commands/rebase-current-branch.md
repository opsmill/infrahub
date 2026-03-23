---
description: Rebase the current branch on another branch, handling migration renumbering if needed
argument-hint: [target-branch] [--skip-backend] [--skip-frontend]
---

# Rebase Current Branch

Rebase the current branch on a target branch (defaults to `develop`), handling any conflicts that may arise, especially migration renumbering.

**Arguments:**
- `target-branch` (optional): The branch to rebase onto. Defaults to `develop`.
- `--skip-backend` (optional): Skip backend-specific conflict resolution (migrations, generated files, docs).
- `--skip-frontend` (optional): Skip frontend-specific conflict resolution (package-lock.json, GraphQL types).

## Steps to Follow

1. **Parse arguments**:
   - If a target branch is provided, use it. Otherwise, default to `develop`.
   - Check for `--skip-backend` or `--skip-frontend` flags.

2. **Check current state**: Run `git status` to check for uncommitted changes

3. **Stash uncommitted changes**: If there are uncommitted changes (including untracked files), stash them:
   ```bash
   git stash --include-untracked
   ```

4. **Fetch and rebase**: Fetch the target branch and rebase:
   ```bash
   git fetch origin <target-branch> && git rebase origin/<target-branch>
   ```

5. **Handle conflicts**: If conflicts occur during rebase:
   - Check which files have conflicts with `git diff --name-only --diff-filter=U`
   - For each conflicting file, read it and resolve the conflict
   - See sections below for specific conflict types
   - **Skip sections based on flags**: If `--skip-backend` is set, skip backend conflicts. If `--skip-frontend` is set, skip frontend conflicts.

6. **Continue rebase**: After resolving conflicts:
   ```bash
   git add <resolved-files> && git rebase --continue
   ```

7. **Restore stashed changes**: If changes were stashed:
   ```bash
   git stash pop
   ```
   - If stash pop has conflicts, resolve them similarly (respecting skip flags).
   - For skipped areas, use `git checkout HEAD -- <file>` to keep the rebased version.

8. **Verify history**: Show the commit history to confirm the rebase:
   ```bash
   git log --oneline -20
   ```

9. **Ask before pushing**: Always ask the user if they want to push. If they confirm, use force-with-lease:
   ```bash
   git push --force-with-lease
   ```

## Backend Conflicts

> **Skip this section if `--skip-backend` is set.** For conflicts in backend files when skipping, use `git checkout --theirs <file>` to accept the target branch version.

### Migration Renumbering

Migration conflicts are common when rebasing. If the conflict is in `backend/infrahub/core/migrations/graph/__init__.py`, it usually means migrations need renumbering.

1. **Keep migrations from target branch** (they take precedence)

2. **Renumber your migration(s)** to the next available number:
   - Update the migration file name: `git mv m0XX_... m0YY_...`
   - Update the class name inside the migration file (e.g., `Migration0XX` -> `Migration0YY`)
   - Update `name` and `minimum_version` in the migration class

3. **Update the imports and MIGRATIONS list** in `backend/infrahub/core/migrations/graph/__init__.py`

4. **Update test files**:
   - Rename test file to match new migration number
   - Update class name, function names, and all references inside the test

5. **Bump GRAPH_VERSION**: Update `backend/infrahub/core/graph/__init__.py` to the new migration number

**Important:**
- Migration numbers must be sequential with no gaps
- The `GRAPH_VERSION` must match the highest migration number
- Test file names should match their corresponding migration numbers

### Generated Files

If conflicts occur in generated backend files, accept the target branch version and regenerate:

```bash
git checkout --theirs schema/schema.graphql backend/infrahub/core/protocols.py
uv run invoke backend.generate
git add schema/schema.graphql backend/infrahub/core/protocols.py backend/infrahub/core/schema/generated/
```

Generated backend files:
- `schema/schema.graphql` - GraphQL schema
- `backend/infrahub/core/protocols.py` - Protocol definitions
- `backend/infrahub/core/schema/generated/` - Schema definitions

### Schema Documentation

If schema changes occurred, regenerate the schema documentation:

```bash
uv run invoke docs.generate-schema
git add docs/docs/reference/schema/
```

## Frontend Conflicts

> **Skip this section if `--skip-frontend` is set.** For conflicts in frontend files when skipping, use `git checkout --theirs <file>` to accept the target branch version, or `git checkout HEAD -- <file>` to keep your version.

### package-lock.json

If `frontend/app/package-lock.json` has conflicts:

```bash
git checkout --theirs frontend/app/package-lock.json
cd frontend/app && npm install
git add frontend/app/package-lock.json
```

### Generated GraphQL Types

If the backend GraphQL schema changed, regenerate frontend types:

```bash
cd frontend/app && npm run codegen:graphql
git add frontend/app/src/shared/api/graphql/generated/
```

### Other Generated Files

If conflicts occur in other generated files (e.g., `frontend/app/src/shared/api/rest/types.generated.ts`), accept the target branch version and regenerate after rebase completes.

## General Notes

- Always use `--force-with-lease` instead of `--force` when pushing rebased branches
- If rebase encounters multiple conflicts, handle them one commit at a time
- When in doubt, abort the rebase with `git rebase --abort` and ask for help
