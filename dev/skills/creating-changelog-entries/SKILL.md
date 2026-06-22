---
name: creating-changelog-entries
description: Use in a project that manages its changelog with Towncrier, when you've fixed a bug, added a feature, or made any user-facing change and need to record it — before committing or opening a PR, or whenever asked to add a changelog entry, towncrier fragment, or news fragment.
compatibility: Requires the project to use Towncrier for changelog management — a configured Towncrier setup (e.g. `[tool.towncrier]` in pyproject.toml) and the `towncrier` CLI available, typically via a Python runner such as uv or poetry.
---

# Creating Changelog Entries

## Overview

[Towncrier](https://towncrier.readthedocs.io/) assembles the changelog from per-change "fragment" files — one small file per change, collected and rendered at release time. This skill applies to any project that uses Towncrier. Every issue fix or new feature should ship with a fragment, written short and user-facing: describe *what* changed, not how it was implemented.

**Requires Towncrier.** If the project has no `[tool.towncrier]` config (or another Towncrier config file), this skill does not apply — follow that project's own changelog process instead.

**Core rule:** always create fragments with `towncrier create`, never hand-write them. The command derives the location and naming from the Towncrier config and places the fragment correctly no matter which directory you run it from.

## When to Use

- You fixed a bug or added a feature and are about to commit or open a PR.
- You're asked to "add a changelog entry", "create a news fragment", or "run towncrier".
- A PR checklist or CI flags a missing changelog entry.

When NOT to use: the project doesn't use Towncrier; pure internal refactors with no user-facing or maintenance impact; and changes the team has explicitly decided don't warrant an entry. (Most internal maintenance still gets a `housekeeping` fragment.)

## Quick Reference

```bash
towncrier create -c "content of changelog entry" ${ISSUE}.${TYPE}.md
```

If the project wraps Python tools in a runner, prefix accordingly — e.g. `uv run towncrier ...` (uv) or `poetry run towncrier ...` (Poetry).

- **ISSUE** — issue ID, or `+` when no issue exists (e.g. `+deps-update`).
- **TYPE** — one of the change types below.

| Type | Use For |
|------|---------|
| `added` | New features |
| `changed` | Changes in existing functionality |
| `deprecated` | Soon-to-be removed features |
| `removed` | Now removed features |
| `fixed` | Bug fixes |
| `security` | Security vulnerabilities |
| `housekeeping` | Internal maintenance, dependencies, tooling |

The available types come from the project's Towncrier config (`[tool.towncrier]`); the set above is the common default.

## Fragment Location

Fragments live in the directory Towncrier is configured to use (its `directory` setting — commonly the repo-root `changelog/` or `newsfragments/`). `towncrier create` puts them there automatically — don't move them or hand-place them.

In a monorepo, they do **not** belong in a sub-package directory such as `backend/changelog/` or `frontend/changelog/`. A fragment found there was hand-written in the wrong place and must move to the configured directory.

## Writing Good Messages

- Write from the user's perspective.
- Focus on what changed, not how.
- Use past tense ("Fixed", "Added", "Removed").
- Keep it concise — one sentence.
- Avoid technical jargon.

## Examples

```bash
# Bug fix for issue #1234
towncrier create -c "Fixed sidebar collapse issue" 1234.fixed.md

# New feature for issue #7549
towncrier create -c "Added breadcrumb navigation for hierarchical schemas" 7549.added.md

# Housekeeping without an issue
towncrier create -c "Updated dependencies to latest versions" +deps-update.housekeeping.md
```

## Common Mistakes

- **Hand-writing the fragment file.** Use `towncrier create` so the name and location are correct.
- **Placing it in a sub-package directory** (e.g. `backend/changelog/`) instead of the configured fragments directory.
- **Describing the implementation.** "Refactored the auth-token cache layer" → instead say what the user sees: "Fixed users being unexpectedly logged out".
- **Wrong tense or multiple sentences.** One past-tense sentence.

## See Also

- [Towncrier documentation](https://towncrier.readthedocs.io/) — fragment types, configuration, and CLI options.
- [Keep a Changelog](https://keepachangelog.com/) — changelog best practices.
- Your project's contributing or changelog guide for project-specific conventions (in Infrahub: `docs/docs/development/changelog.mdx`).
