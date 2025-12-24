# Git Workflow

> Part of: `dev/guidelines/` | Related: `dev/guides/`

Git workflow and commit conventions for the project.

## Branch Strategy

- **Main branches:** `stable` (production), `develop` (development), `release-*` (releases)
- **Feature branches:** Create from `develop`, merge back via PR
- **Branch naming:** `<initials>-<short-description>` (e.g., `jd-add-breadcrumbs`)

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

Add changelog fragments to `changelog/` using Towncrier format:

```bash
uv run towncrier -c "content of changelog entry" ${ISSUE}.{ACTION}.md
```

Where:
- `${ISSUE}`: GitHub issue ID or `+` if no issue
- `${ACTION}`: `added`, `fixed`, or `housekeeping`

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

