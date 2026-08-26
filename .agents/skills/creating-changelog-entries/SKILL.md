---
name: creating-changelog-entries
description: Use when you've fixed a bug, added a feature, or made any user-facing change in a project that uses Towncrier and need to record it for the changelog — before committing or opening a PR, or whenever asked to add a changelog entry, towncrier fragment, or news fragment.
compatibility: Requires the project to use Towncrier for changelog management — a configured Towncrier setup (e.g. `[tool.towncrier]` in pyproject.toml) and the `towncrier` CLI available, typically via a Python runner such as uv or poetry.
---

# Creating Changelog Entries

## Overview

[Towncrier](https://towncrier.readthedocs.io/) assembles the changelog from per-change "fragment" files — one small file per change, collected and rendered at release time. This skill applies to any project that uses Towncrier. Every issue fix or new feature should ship with a fragment, written short and user-facing: describe *what* changed, not how it was implemented.

**Core rule:** always create fragments with `towncrier create`, never hand-write them. The command derives the location and naming from the Towncrier config and places the fragment correctly from anywhere in the repo.

## When to Use

- You fixed a bug or added a feature and are about to commit or open a PR.
- You're asked to "add a changelog entry", "create a news fragment", or "run towncrier".
- A PR checklist or CI flags a missing changelog entry.

When NOT to use: the project doesn't use Towncrier; pure internal refactors with no user-facing or maintenance impact; and changes the team has explicitly decided don't warrant an entry. (The boundary for internal maintenance is below — don't add a `housekeeping` fragment by default.)

**Exception — unreleased features need no fragment.** A fix or follow-up to a feature that has not
shipped in any release is not user-observable: the feature's own `added` fragment already covers
everything a user will ever see, and a `fixed` entry for something never released is noise.

**`housekeeping` is not a catch-all.** It covers internal work a user could still notice — a
build, tooling, or CI change. A change with no user-facing effect at all (an internal
type annotation, a behavior-preserving refactor, a lint or type-checker config cleanup that touches
no source code, cleanup of internal docs or spec scaffolding) gets no fragment. When it's unclear
whether a change is user-facing, ask instead of adding one by default.

## Quick Reference

```bash
uv run towncrier create -c "content of changelog entry" ${ISSUE}.${TYPE}.md
```

These commands use `uv run`, which runs the project's pinned Towncrier and is the convention across these Python projects. If your project doesn't use uv, drop the prefix (`towncrier create ...`) or use its runner (e.g. `poetry run towncrier ...`).

- **ISSUE** — issue ID, or `+` when no issue exists (e.g. `+pnpm-workspaces`).
- **TYPE** — one of the change types below.

| Type | Use For |
|------|---------|
| `added` | New features |
| `changed` | Changes in existing functionality |
| `deprecated` | Soon-to-be removed features |
| `removed` | Now removed features |
| `fixed` | Bug fixes |
| `security` | Security vulnerabilities |
| `housekeeping` | Internal maintenance and tooling (build, CI, dev scripts) |

The available types come from the project's Towncrier config (`[tool.towncrier]`); the set above is the common default. How a project classifies some changes is project-specific — dependency-version bumps in particular land under `changed` in some projects and `housekeeping` in others, so follow the project's changelog guide rather than assuming.

## Fragment Location

Fragments live in the directory Towncrier is configured to use (its `directory` setting — commonly the repo-root `changelog/` or `newsfragments/`). `towncrier create` puts them there automatically — don't move them or hand-place them.

In a monorepo, they do **not** belong in a sub-package directory such as `backend/changelog/` or `frontend/changelog/`. A fragment found there was hand-written in the wrong place and must move to the configured directory.

Exception: a nested package with its *own* Towncrier config (e.g. a submodule like Infrahub's `python_sdk`) keeps its own fragments in that package's configured directory — those stay put and must not be moved to the root.

## Writing Good Messages

- Write from the user's perspective.
- Focus on what changed, not how.
- Use past tense ("Fixed", "Added", "Removed").
- Keep it concise — one sentence.
- Avoid technical jargon.

## Examples

```bash
# Bug fix for issue #1234
uv run towncrier create -c "Fixed sidebar collapse issue" 1234.fixed.md

# New feature for issue #7549
uv run towncrier create -c "Added breadcrumb navigation for hierarchical schemas" 7549.added.md

# Housekeeping without an issue
uv run towncrier create -c "Migrated the frontend build to pnpm workspaces" +pnpm-workspaces.housekeeping.md
```

## Common Mistakes

- **Getting the filename shape wrong.** It is `<issue-or-+slug>.<type>.md`; the type segment is
  required, and a file without one is not picked up. Everything before it is either a GitHub issue
  number or a `+`-prefixed slug, because `issue_format` turns a bare name straight into a GitHub
  issue URL: `IFC-2747.fixed.md` ships a link to an issue that does not exist. The `+` marks the
  entry as an orphan and suppresses the link, so `+ifc-2546-lorem-ipsum.changed.md` is valid — but
  the ticket ID never appears in the output, so spend the slug on a description instead.
- **Hand-writing the fragment file.** Use `towncrier create` so the name and location are correct.
- **Placing it in a sub-package directory** (e.g. `backend/changelog/`) instead of the configured fragments directory.
- **Describing the implementation.** "Refactored the auth-token cache layer" → instead say what the user sees: "Fixed users being unexpectedly logged out".
- **Wrong tense or multiple sentences.** One past-tense sentence.
- **Duplicating an existing fragment.** On a feature branch spanning multiple PRs, list the fragments directory first — numbered (`NNNN.type.md`) and `+`-prefixed fragments all render into the changelog. If a fragment already describes the same user-visible change, extend or reconcile it instead of adding an overlapping one.

## See Also

- [Towncrier documentation](https://towncrier.readthedocs.io/) — fragment types, configuration, and CLI options.
- [Keep a Changelog](https://keepachangelog.com/) — changelog best practices.
- Your project's contributing or changelog guide for project-specific conventions (in Infrahub: `docs/docs/development/changelog.mdx`).
