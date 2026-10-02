# Reviewing your branch with cubic before pushing

> Part of: `dev/guides/` | Related: [reviewing-local-changes skill](../../.agents/skills/reviewing-local-changes/SKILL.md), [`cubic.yaml`](../../cubic.yaml)

cubic reviews every Infrahub pull request. Running the same reviewer locally before you push
catches most of what it would comment on, so the PR opens with fewer threads to answer.

## One-time setup

1. Get a seat on OpsMill's cubic subscription. The organisation plan does not cover an account
   on its own: reviews fail with `Subscription expired` until a cubic admin assigns you a seat.
2. Install the CLI:

   ```bash
   curl -fsSL https://cubic.dev/install | bash
   ```

   The installer adds `~/.cubic/bin` to your shell profile. Open a new terminal, or run
   `exec $SHELL -l`, before using `cubic`.
3. Sign in with the account that holds the seat:

   ```bash
   cubic auth login
   ```

4. Optional, recommended: let cubic use your Claude Code or Codex subscription for a stronger
   review model than the included one.

   ```bash
   cubic auth connect claude-code
   ```

Check the setup at any time:

```bash
bash .agents/skills/reviewing-local-changes/scripts/check-cubic.sh
```

It exits non-zero and prints the fix when the CLI is missing or you are not signed in. It cannot
detect a missing seat; only a review reports that.

## Running a review

Commit your work first: the review covers the commits on your branch, as the PR review does.

- **With an AI agent**, run the `reviewing-local-changes` skill (`/reviewing-local-changes` in
  Claude Code). It reviews, checks each finding against the code, fixes the real ones with your
  approval, and reviews again until clean. It also checks what the diff cannot show, such as
  specs, changelog fragments, and PR description claims.
- **From the terminal**, run:

  ```bash
  uv run invoke dev.cubic-review
  ```

  Add `--base develop` to choose the base branch, or `--json` for machine-readable output. The
  task only reports findings; fixing them is up to you.

A review takes a few minutes. Exit code 1 means cubic reported findings or the review failed; the
output says which.

## How the rules reach cubic

Infrahub's review rules live in [`dev/guidelines/review/`](../guidelines/review/README.md), one
checklist per area (`frontend.md`, `backend.md`, `testing.md`), next to the passes no tool runs.
`.cubic/` holds a symlink to each checklist, and `cubic.yaml` attaches those paths to PR reviews.
cubic reads `cubic.yaml` only from the default branch, so the local task passes the checklists of
your branch directly; a checklist change applies to your local reviews before it merges.

When cubic flags something that is intentional in Infrahub, add a line to the matching checklist's
**Do NOT flag** section. Edit the file under `dev/guidelines/review/`, not the symlink. When it misses something reviewers keep catching, add a rule. Keep each
checklist under 9,000 characters: cubic reads only the first 10,000 per checklist and drops the
rest without warning. If you change which paths a checklist covers, update both `cubic.yaml` and
`CUBIC_CHECKLISTS` in `tasks/dev.py`.
