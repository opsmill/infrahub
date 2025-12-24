# Changelog

> Part of: `dev/guidelines/` | Related: `docs/docs/development/changelog.mdx`

Guidelines for creating changelog entries using Towncrier.

## Creating Changelog Entries

Every issue fix or new feature should include a changelog entry. The message should be short, user-facing, and describe what was fixed or implemented without technical implementation details.

### Command

```bash
uv run towncrier create -c "content of changelog entry" ${ISSUE}.${TYPE}.md
```

### File Naming

Format: `${ISSUE}.${TYPE}.md`

- **ISSUE**: GitHub issue ID, or `+` if no issue exists
- **TYPE**: One of the change types below

### Change Types

| Type | Use For |
|------|---------|
| `added` | New features |
| `changed` | Changes in existing functionality |
| `deprecated` | Soon-to-be removed features |
| `removed` | Now removed features |
| `fixed` | Bug fixes |
| `security` | Security vulnerabilities |
| `housekeeping` | Internal maintenance, dependencies, tooling |

### Examples

```bash
# Bug fix for issue #1234
uv run towncrier create -c "Fixed sidebar collapse issue" 1234.fixed.md

# New feature for issue #7549
uv run towncrier create -c "Added breadcrumb navigation for hierarchical schemas" 7549.added.md

# Housekeeping without an issue
uv run towncrier create -c "Updated dependencies to latest versions" +deps-update.housekeeping.md
```

## Writing Good Changelog Messages

- Write from the user's perspective
- Focus on what changed, not how
- Use past tense ("Fixed", "Added", "Removed")
- Keep it concise (one sentence)
- Avoid technical jargon

## See Also

- `docs/docs/development/changelog.mdx` - Comprehensive changelog guide for contributors
- [Keep a Changelog](https://keepachangelog.com/) - Best practices we follow
