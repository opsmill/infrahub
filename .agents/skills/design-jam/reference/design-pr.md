# The design PR

Read this at the end of phase 2, before opening the design PR, and again in phase 5.

The design PR is a draft opened at the end of phase 2. Its preview is the link reviewers
open, and its comments hold their notes. Until phase 5 its body says what is being
designed, gives the preview link, and explains how to give feedback (pin notes, press
*Post to PR*). At phase 5 the body becomes `05-handoff.md` and the PR is where the design
is approved. Approval goes on a PR because it is recorded, has an author, and sits next to
the code. The design PR is never merged.

## Opening it

Use the repo's `pr` skill (`.agents/skills/pr` or the `opsmill-dev:pr` plugin skill).
Neither takes a base argument, and they handle drafts differently:

- Both propose the base from `origin/HEAD`, which is `stable` here, and ask for approval.
  Put `base: <value from STATE.md>` in the request anyway, and correct the base at the
  approval step if it differs from `STATE.md`.
- Both take labels from `gh label list`. Ask for `cd/preview`.
- The plugin version opens a draft; the repo version does not. After the PR opens, run
  `gh pr view <number> --json isDraft`, and if it is `false`, run
  `gh pr ready --undo <number>`.

## What it must have

- **Base**: `base:` from `STATE.md`.
- **Title**: `design(<slug>): <the "done looks like" sentence from the brief>`. The prefix
  is how design PRs are found (`is:pr in:title "design("`); there is no design label.
- **Body**: the short feedback body until phase 5, then `05-handoff.md` unchanged, with
  `gh pr edit <number> --body-file`, and a link to `05-implement.md` at the bottom.
- **Draft**: always. The prototype route is always registered, so merging the PR would ship
  the prototype.
- **`cd/preview` label**: CI builds a preview instance from the PR, and that URL is the
  shareable prototype. When it exists, write it as `preview:` in `STATE.md` and at the top
  of the PR body. If the label is missing, run `gh pr edit <number> --add-label cd/preview`.

Write the PR URL as `pr:` in `STATE.md` when it opens. At phase 5, also put it at the top
of `05-handoff.md`.
