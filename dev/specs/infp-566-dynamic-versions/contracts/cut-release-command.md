# Contract: `/cut-release` command (FR-021)

**Location correction**: the command lives at **`.agents/commands/cut-release.md`** (the spec
cited `dev/commands/cut-release.md`). A `/cut-release` **Skill** is also registered — check
whether it points at the same file or duplicates the steps, and update both so they agree.

## Why it must change

Its current premise breaks under dynamic versioning:
- Step 1 reads `version = "X.Y.Z"` from line 3 of `pyproject.toml` — that field is gone (FR-008).
- Step 3 runs `uv version <new>` and `uv version --directory python_testcontainers <new>` —
  both operate on `[project].version` and fail.

First invocation after the change would fail immediately. FR-021 lands with FR-001/FR-008.

## New flow

1. **Determine version**: read the most recent reachable tag
   `git describe --tags --match 'infrahub-v*' --abbrev=0` → strip `infrahub-v` → increment
   patch (default) or honor an explicit `$ARGUMENTS` version.
2. **Pre-flight (preserved)**: changelog-fragment count, current-branch report,
   `towncrier build --draft --version <new>` preview, `AskUserQuestion` confirmation.
3. **Build changelog**: `towncrier build --version <new> --yes` (prepends `CHANGELOG.md`,
   removes fragments). Release-notes page + sidebar steps preserved.
4. **Tag**: create annotated `infrahub-v<new>` on the changelog commit; push the tag and the
   changelog commit.
5. **No `pyproject.toml` edit at any step** — state this explicitly in the command.

## Removed from the command

- All `pyproject.toml`-bumping steps (`uv version …`).
- Any verification that the two `pyproject.toml` versions match.

## Guarantee

Running `/cut-release` produces a release commit + `infrahub-v<new>` tag with zero edits to
either `pyproject.toml`; the build resolver derives the version from the tag.
