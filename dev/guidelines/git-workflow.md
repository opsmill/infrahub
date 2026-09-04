# Git Workflow

> Part of: `dev/guidelines/` | Related: `docs/docs/development/git-best-practices.mdx`

Git workflow and commit conventions for the project.

## Branch Strategy

- **Main branches:** `stable` (production), `develop` (development), `release-*` (releases)
- **Feature branches:** Create from `develop`, merge back via PR
- **Bug fixes:** target the oldest branch that needs the fix — `stable` when the bug is in released
  code and the fix should ship in a patch release, `develop` when the code only exists there or the
  fix can wait for the next minor
- **Repo-tooling/lint/CI-config changes:** target `develop` if the diff also edits runtime source —
  converting call sites, changing behavior a new lint rule now gates — since what the code emits at
  runtime changed regardless of how enabling it was triggered. Target `stable` only when the diff has
  no source-code changes at all (pure config, docs, CI).
- **Verify the base before cutting:** check that the code the ticket references actually exists on
  the chosen base (`git ls-tree <base> -- <path>`); follow-up tickets often reference modules that
  are only on `develop`
- **Branch naming:** `<initials>-<short-description>` (e.g., `jd-add-breadcrumbs`)

### Stacked PRs

A PR that targets another feature branch rather than `develop` does not see what `develop` has
fixed since the two diverged. GitHub runs CI on the **merge ref** — the head merged into its own
target — so the lower PR silently picks up `develop`'s fixes while the stacked one does not. Two
PRs holding identical code can therefore disagree about whether CI passes, which reads like a
flake and is not one.

Before recording a failure on a stacked PR as inherited or pre-existing, check whether the
ultimate base already fixes it:

```bash
git log origin/develop --oneline -- <failing file>   # is there a fix the stack never saw?
git diff HEAD origin/develop -- <failing file>
```

A fix that exists on `develop` is cherry-picked onto the stack, not documented as a known
failure.

## Versioning

`infrahub-server` and `infrahub-testcontainers` derive their version from the `infrahub-v*` git tags
at build time (hatch-vcs). There is no `version` field in `pyproject.toml`, and releases do not bump
one. Implications for local work:

- **Fetch tags on a fresh clone** (`git fetch --tags`), or a build resolves a development fallback
  version instead of the real one (the build still succeeds — it never fails on a missing tag).
- **Editable installs pin the version at `uv sync` time.** After moving to a different commit or
  fetching new tags, re-run `uv sync` to refresh the version reported at runtime.
- **Maintenance-branch hygiene:** never merge a newer main-line `infrahub-v*` tag into an older
  `release-x.y` branch — the resolver would then pick up the wrong version line. Cherry-pick patches
  onto the release branch instead of merging `stable`/`develop` into it.

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

```text
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

```text
feat: add breadcrumb navigation for hierarchical schemas [#7549]
fix: resolve sidebar collapse issue [IFC-2847]
```

## Changelog

Add changelog fragments to `changelog/` using Towncrier. Use the `creating-changelog-entries` skill for change types and examples.

## Pull Requests

**PR title pattern:** `<type>: <short description> [<issue reference>]`

**PR description should include:**

- What was changed and why
- Any notable implementation details
- Testing performed

**Scope to match the change.** A trivial, code-only fix with no behavior change ships as just the
code diff — no spec-kit design record (`dev/specs/<feature>/`, see
[Repository Organization](repository-organization.md)), no changelog fragment (see the
`creating-changelog-entries` skill). Trim both before opening the PR if the workflow that produced
the change generated them by default.

**A lint- or rule-suppression PR ships the suppression only.** If resolving a lint violation
(e.g. adding a justified `# noqa`) surfaces a pre-existing behavioral bug in the code you're
annotating, don't fix the bug in the same PR — keep the diff limited to the annotation and file
the bug separately. The justification comment may record what you found (see
[Exception Handling](backend/exceptions.md)), but the fix belongs in its own PR.

## Critical Rules

- Never force push to `stable` or `develop`
- Never merge a newer main-line `infrahub-v*` tag into an older `release-x.y` branch (cherry-pick patches instead)
- Always run formatters before committing (`uv run invoke format`, `pnpm biome:fix`)
- Include issue references in commit messages when applicable

## See Also

- Use the `creating-changelog-entries` skill - Changelog entry guidelines
- `docs/docs/development/git-best-practices.mdx` - Comprehensive Git guide (submodules, troubleshooting, advanced workflows)
