---
description: Cut a new Infrahub release (patch by default, or specify exact version)
allowed-tools: Bash(git:*), Bash(uv:*), Bash(gh:*), Bash(date:*), Bash(sleep:*), Read, Edit, Write, Grep, Glob
argument-hint: [version] (e.g., "1.8.0") - leave empty for patch release
---

# Cut Release

Cut a new Infrahub release. The version is **derived from the latest git tag** and stamped into the
build by hatch-vcs. There is **no `[project].version` field** in either `pyproject.toml`, and this
command **never edits `pyproject.toml`** — a release is declared solely by the annotated
`infrahub-v<version>` git tag. (The hatch-vcs `fallback-version` is a static sentinel, identical on
every branch, and is never bumped — a moving value would conflict on every stable/develop merge.)

**Argument**: `$ARGUMENTS`
- If empty: increment the patch of the most recent release tag (e.g., 1.10.0 -> 1.10.1)
- If provided: use the exact version specified (e.g., 1.11.0)

## Step 1: Determine Version

1. **Read the most recent release tag**:

   ```bash
   git fetch --tags
   git describe --tags --match 'infrahub-v*' --abbrev=0
   ```

   Strip the `infrahub-v` prefix to get the current version (e.g., `infrahub-v1.10.0` -> `1.10.0`).
   Parse into major, minor, patch components.

2. **Calculate the new version**:
   - If `$ARGUMENTS` is empty or whitespace: increment the patch (e.g., 1.10.0 -> 1.10.1).
   - If `$ARGUMENTS` is provided: validate it is a valid version (X.Y.Z, with an optional PEP 440
     pre-release/dev suffix such as `1.11.0b1`).

3. **Validate**:
   - The new version MUST be greater than the current tag version.
   - If validation fails, stop and report the error.

## Step 2: Pre-flight Checks

Before proceeding, verify:

1. **Check for changelog fragments**:

   ```bash
   ls changelog/*.md 2>/dev/null | grep -v towncrier | grep -v .gitignore | wc -l
   ```

   Report how many fragments exist. If none, warn the user but allow proceeding (they may want to
   release without new changes).

2. **Show current branch** (informational):

   ```bash
   git branch --show-current
   ```

   Releases are normally cut from `stable`. Report the branch so the user can confirm they are on
   the right one.

3. **Preview towncrier output**:

   ```bash
   uv run towncrier build --draft --version <new_version>
   ```

   Show the user what changelog entries will be included.

**Present findings to the user and ask for confirmation before proceeding with AskUserQuestion.**

## Step 3: Update docker-compose.yml & Helm Chart via the Propagation Workflow

**Skip this step for pre-release versions** (e.g. `1.11.0b1`) — docker-compose.yml and the Helm
chart only track final releases, and the workflow rejects pre-release/dev versions.

**Hard requirement**: the tagged release commit MUST already contain docker-compose.yml pinned to
the new version. The New Release workflow validates this and refuses to publish otherwise.

Trigger the "Update Docker Compose & helm chart" workflow with the target version. It updates the
docker-compose.yml image pins (committed to the branch by opsmill-bot) AND the Helm chart
`appVersion` in the separate `opsmill/infrahub-helm` repository:

```bash
gh workflow run update-compose-file-and-chart.yml --ref <current_branch> -f version=<new_version>
```

Wait for the run to complete successfully, then pull the bot commit into the local branch:

```bash
sleep 5  # give GitHub a moment to register the run
RUN_ID=$(gh run list --workflow=update-compose-file-and-chart.yml --branch <current_branch> --limit 1 --json databaseId --jq '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
git pull --rebase origin <current_branch>
```

Verify the compose file is now pinned correctly (the same check the New Release workflow runs):

```bash
uv run invoke release.validate-docker-compose --version <new_version>
```

If the workflow run fails, or the validation fails after pulling, stop — do NOT tag with a stale
docker-compose.yml.

## Step 4: Build Changelog

Run towncrier to:

1. Generate changelog content from fragments
2. Prepend to CHANGELOG.md
3. Remove the processed fragment files

```bash
uv run towncrier build --version <new_version> --yes
```

## Step 5: Create Release Notes Page

### Determine the release date

Format: "Month DDth, YYYY" (e.g., "January 27th, 2026")

Use proper ordinal suffix:
- 1st, 21st, 31st (numbers ending in 1, except 11)
- 2nd, 22nd (numbers ending in 2, except 12)
- 3rd, 23rd (numbers ending in 3, except 13)
- th for all others (4th, 5th, 11th, 12th, 13th, etc.)

### Extract changelog content for this release

Read the updated `CHANGELOG.md` and extract only the new release section:
- Start: After the `## [Infrahub - v<new_version>]` header line
- End: Before the next `## [Infrahub - v` line (previous release)

From the extracted content:
- Keep the section headers (### Added, ### Fixed, ### Changed, etc.)
- Keep all bullet points with their issue links
- Remove blank lines at start/end

### Create the release notes MDX file

File path: `docs/docs/release-notes/infrahub/release-<major>_<minor>_<patch>.mdx`
(e.g., `release-1_7_2.mdx` for version 1.7.2 - note underscores, not dots)

Use this template:

```mdx
---
title: Release <version>
release_date: <YYYY-MM-DD>
release_type: <"minor" for X.Y.0 releases, "security" if the changelog has a ### Security section, otherwise "patch">
description: "<1-2 plain-text sentences summarizing the release>"
---
<table>
  <tbody>
    <tr>
      <th>Release Number</th>
      <td><version></td>
    </tr>
    <tr>
      <th>Release Date</th>
      <td><formatted_date></td>
    </tr>
    <tr>
      <th>Tag</th>
      <td>[infrahub-v<version>](https://github.com/opsmill/infrahub/releases/tag/infrahub-v<version>)</td>
    </tr>
  </tbody>
</table>

<changelog_sections>
```

Where `<changelog_sections>` contains the ### Added, ### Fixed, etc. sections extracted from the changelog.

Frontmatter contract (consumed by the release-notes feed at `/release-notes/infrahub`
and the generated sidebar — see `docs/plugins/release-notes-data.js` and
`docs/sidebar-releases.ts`):

- `release_date` (required): ISO date `YYYY-MM-DD`.
- `release_type` (required): `minor` for X.Y.0 releases, `security` when the
  changelog contains a `### Security` section, otherwise `patch`.
- `description` (required): 1–2 plain-text sentences shown as the release
  summary in the feed (no markdown, no code formatting).
- `breaking: true` (only when applicable): set when the release notes contain a
  Breaking-changes section; renders a "Breaking changes" chip in the feed.

`node scripts/backfill-release-frontmatter.mjs --check` (run from `docs/`)
verifies that no release file is missing a required field.

<<<<<<< HEAD
For example, if releasing 1.7.2, insert:

```typescript
            'release-notes/infrahub/release-1_7_2',
```

before the existing first entry.
=======
## Step 6: Verify Sidebar Generation

The release-notes sidebar is generated automatically from the files in
`docs/docs/release-notes/infrahub/` by `docs/sidebar-releases.ts` — no manual
`docs/sidebars.ts` edit is needed. The new release appears in its "X.Y release"
category once the file exists.
>>>>>>> origin/stable

## Step 7: Commit, Tag, and Push

The release is one commit (changelog + docs) on top of the workflow's docker-compose commit
(Step 3), plus an annotated `infrahub-v<new_version>` tag. The tag is what the build resolver
reads — there is no version file to bump.

1. **Review the changes**:

   ```bash
   git status
   git diff
   ```

2. **Commit** the release files (docker-compose.yml is NOT staged here — the propagation workflow
   already committed it in Step 3):

   ```bash
   git add CHANGELOG.md docs/docs/release-notes/infrahub/release-<major>_<minor>_<patch>.mdx docs/sidebars.ts
   git commit -m "chore: release <new_version>"
   ```

3. **Create the annotated tag** on the release commit:

   ```bash
   git tag -a infrahub-v<new_version> -m "Release infrahub-v<new_version>"
   ```

4. **Push** the commit and the tag:

   ```bash
   git push origin HEAD
   git push origin infrahub-v<new_version>
   ```

## Step 8: Verify Changes

Review all modified files:

1. `CHANGELOG.md` - new release section added, fragments removed
2. `docs/docs/release-notes/infrahub/release-<version>.mdx` - new file created
3. `docs/sidebars.ts` - new entry added at top of releases list
4. **No `pyproject.toml` changes**: `git diff HEAD~1 -- pyproject.toml python_testcontainers/pyproject.toml`
   MUST be empty
5. `docker-compose.yml` - all infrahub services pin `<new_version>` via the workflow's bot commit
   (`uv run invoke release.validate-docker-compose --version <new_version>` passes)
6. The annotated tag `infrahub-v<new_version>` exists and points at the release commit

## Step 9: Summary and Next Steps

Present a summary of changes made:
- Old version -> New version
- Files modified/created
- Number of changelog entries included
- The tag created and pushed

To publish the release artifacts, **create the GitHub release** at
https://github.com/opsmill/infrahub/releases/new with tag `infrahub-v<version>` — this triggers the
New Release workflow (PyPI, docker image, Helm publish). Its publish guards validate that the
resolved version matches the tag and that docker-compose.yml is up to date, and abort otherwise.
The Helm chart `appVersion` was already propagated by the workflow run in Step 3, so the published
chart carries the new version.

## Error Handling

- If `git describe` finds no `infrahub-v*` tag, stop and report (the very first tag must be created manually)
- If towncrier fails, stop and report the error
- If version parsing fails, show a clear error about the expected format (X.Y.Z)
- If `gh` is not authenticated or the workflow dispatch fails, stop and report (the propagation
  workflow MUST run before tagging)
- If the propagation workflow run concludes in failure, or `release.validate-docker-compose` fails
  after pulling, stop — do NOT tag with a stale docker-compose.yml
- If the release notes file already exists, ask the user before overwriting
- If the sidebar update location cannot be found, report the error and show what manual edit is needed
- This command NEVER edits `pyproject.toml` at any step (`[project].version` does not exist, and
  the `fallback-version` sentinel is static); if any guidance suggests otherwise, it is stale
