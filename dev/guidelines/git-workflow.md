# Git Workflow

> Part of: `dev/guidelines/` | Related: `docs/docs/development/git-best-practices.mdx`

Git workflow and commit conventions for the project.

## Branch Strategy

- **Main branches:** `stable` (production), `develop` (development), `release-*` (releases)
- **Feature branches:** Create from `develop`, merge back via PR
- **Branch naming:** `<initials>-<short-description>` (e.g., `jd-add-breadcrumbs`)

## Submodules

Infrahub includes `python_sdk` as a Git submodule. Always handle submodules correctly.

### Essential Commands

```bash
# Clone with submodules (required for new clones)
git clone --recursive git@github.com:opsmill/infrahub.git

# Pull with submodules (always use this)
git pull --recurse-submodules

# Sync submodules to recorded commits (after pull or checkout)
git submodule update --init --recursive

# Reset submodule to match main repo (if showing modified)
git submodule update --recursive
```

### Update Submodule to New Version

```bash
cd python_sdk
git fetch --tags origin
git checkout v1.10.0      # or desired version/commit
cd ..
git add python_sdk
git commit -m "chore: update python_sdk to v1.10.0"
```

### Resolve Submodule Conflicts

When `git status` shows `both modified: python_sdk`:

```bash
cd python_sdk
git checkout <desired-commit-hash>  # choose which version to keep
cd ..
git add python_sdk
git commit -m "resolve submodule conflict in python_sdk"
```

## Commit Messages

Follow conventional commits format:

```
<type>: <short description> [<issue reference>]
```

**Types:**
- `feat` - new feature or enhancement
- `fix` - bug fix
- `docs` - documentation changes
- `refactor` - code refactoring without behavior changes
- `test` - adding or updating tests
- `chore` - maintenance tasks, dependencies, tooling

**Issue references:**
- GitHub issue: `#1234`
- Jira ticket: `IFC-1234`

**Examples:**
```
feat: add breadcrumb navigation for hierarchical schemas [#7549]
fix: resolve sidebar collapse issue [IFC-2847]
```

## Changelog

Add changelog fragments to `changelog/` using Towncrier. See `dev/guidelines/changelog.md` for change types and examples.

## Pull Requests

**PR title pattern:** `<type>: <short description> [<issue reference>]`

**PR description should include:**
- What was changed and why
- Any notable implementation details
- Testing performed

## Critical Rules

- Never force push to `stable` or `develop`
- Always run formatters before committing (`uv run invoke format`, `npm run biome:fix`)
- Include issue references in commit messages when applicable

## See Also

- `dev/guidelines/changelog.md` - Changelog entry guidelines
- `docs/docs/development/git-best-practices.mdx` - Comprehensive Git guide (submodules, troubleshooting, advanced workflows)
