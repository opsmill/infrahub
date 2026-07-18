---
description: Cut a new Infrahub release (patch by default, or specify exact version)
allowed-tools: Bash(uv:*), Bash(date:*), Read, Edit, Write, Grep, Glob
argument-hint: [version] (e.g., "1.8.0") - leave empty for patch release
---

# Cut Release

Cut a new Infrahub release. If no version is provided, performs a patch release (increments the patch version).

**Argument**: `$ARGUMENTS`
- If empty: Increment patch version (e.g., 1.7.1 -> 1.7.2)
- If provided: Use the exact version specified (e.g., 1.8.0)

## Step 1: Determine Version

1. **Read current version** from `pyproject.toml`:
   - Look for `version = "X.Y.Z"` at line 3 in the `[project]` section
   - Parse into major, minor, patch components

2. **Calculate new version**:
   - If `$ARGUMENTS` is empty or whitespace: increment patch (e.g., 1.7.1 -> 1.7.2)
   - If `$ARGUMENTS` is provided: validate it's a valid semver format (X.Y.Z where X, Y, Z are non-negative integers)

3. **Validate**:
   - New version must be greater than current version
   - Version format must be valid (X.Y.Z)
   - If validation fails, stop and report the error

## Step 2: Pre-flight Checks

Before proceeding, verify:

1. **Check for changelog fragments**:
   ```bash
   ls changelog/*.md 2>/dev/null | grep -v towncrier | grep -v .gitignore | wc -l
   ```
   Report how many fragments exist. If none, warn the user but allow proceeding (they may want to release without new changes).

2. **Show current branch** (informational):
   ```bash
   git branch --show-current
   ```
   Inform the user which branch they're on.

3. **Preview towncrier output**:
   ```bash
   uv run towncrier build --draft --version <new_version>
   ```
   Show the user what changelog entries will be included.

**Present findings to user and ask for confirmation before proceeding with AskUserQuestion.**

## Step 3: Bump Project Versions

### Main project version

```bash
uv version <new_version>
```

This updates `pyproject.toml` in the root directory.

### Testcontainers version

```bash
uv version --directory python_testcontainers <new_version>
```

Verify both files now have the same version by reading them.

## Step 4: Update Changelog

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

## Step 6: Update Sidebar

Edit `docs/sidebars.ts`:

1. Find the Infrahub release notes items array (search for `'release-notes/infrahub/release-1_7_1'`)
2. Add the new release at the TOP of the list (releases are in descending order, newest first)
3. The new entry format: `'release-notes/infrahub/release-<major>_<minor>_<patch>',`

For example, if releasing 1.7.2, insert:
```typescript
            'release-notes/infrahub/release-1_7_2',
```
before the existing first entry.

## Step 7: Verify Changes

Review all modified files:

1. `pyproject.toml` - version updated
2. `python_testcontainers/pyproject.toml` - version updated
3. `CHANGELOG.md` - new release section added, fragments removed
4. `docs/docs/release-notes/infrahub/release-<version>.mdx` - new file created
5. `docs/sidebars.ts` - new entry added at top of releases list

## Step 8: Summary and Next Steps

Present a summary of changes made:
- Old version -> New version
- Files modified/created
- Number of changelog entries included

Suggest next steps (DO NOT execute these automatically):
1. Review the changes: `git diff`
2. Stage and commit: `git add -A && git commit -m "chore: release <version>"`
3. Push the branch: `git push -u origin <branch_name>`
4. Open a PR targeting `stable`
5. Merge the PR
6. Create a GitHub release at https://github.com/opsmill/infrahub/releases/new with tag `infrahub-v<version>`

**IMPORTANT: Do NOT automatically commit or push. Let the user review and execute these steps manually.**

## Error Handling

- If `uv version` fails, stop and report the error
- If towncrier fails, stop and report the error
- If version parsing fails, show clear error message about expected format (X.Y.Z)
- If release notes file already exists, ask user before overwriting
- If sidebar update location cannot be found, report the error and show what manual edit is needed
