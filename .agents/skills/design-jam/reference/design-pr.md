# The design PR

Read this at the end of phase 2, before opening the design PR, and again in phase 5.

The PR is opened at the **end of phase 2**, as soon as there are directions to look at,
because its preview is the only link reviewers can open and its comments are where their
notes go. Until phase 5 its body is short: what is being designed, the preview link, and
how to give feedback (pin notes, press *Post to PR*). At phase 5 the body is replaced with
`05-handoff.md` and the PR becomes the approval vehicle.

The design is 100% ready when there is a **draft pull request** that someone can approve.
Not the artifact page, not a Slack message: a PR, because approval on a PR is recorded,
attributable, and sits next to the code it approves. Open it through the repo's own `pr`
skill (`.agents/skills/pr`, or the `opsmill-dev:pr` plugin skill) so branch discipline
and attribution follow house rules. Neither version takes a base argument, and they differ
on drafts:

- Both infer the base from `origin/HEAD` — `stable` in this repo — unless the branch is
  clearly forked from elsewhere, and both present the base for approval before creating
  anything. Pass `base: <value from STATE.md>` in the invocation text anyway, and **at the
  approval step, check the proposed base against `STATE.md` and correct it if they differ.**
- Both take labels from `gh label list`; ask for `cd/preview` there.
- The plugin version opens drafts by default; the repo version does not. After the PR URL
  comes back, run `gh pr view <number> --json isDraft`, and if it says `false`, run
  `gh pr ready --undo <number>`. An undrafted design PR looks mergeable.

- **Base:** `base:` from `STATE.md`.
- **Title:** `design(<slug>): <the one-line "done looks like" from the brief>`.
- **Body:** at phase 2, the short feedback body above. At phase 5, `05-handoff.md`,
  verbatim — it was written to be this — via `gh pr edit <number> --body-file`. Lift sheet
  linked at the bottom.
- **Draft.** It must never read as mergeable code; the prototype route is registered
  unconditionally and merging it ships the prototype.
- **No design label.** The `design(<slug>)` title prefix is what makes design PRs
  findable (`is:pr in:title "design("`). Do not create a label for it on the PR.
- **Label `cd/preview`.** This is what turns the design into something anyone can open:
  CI builds a preview instance from the PR, and *that* URL — not localhost — is the
  shareable prototype. Once it exists, replace `preview:` in `STATE.md` with it and put it
  at the top of the PR body. If the label did not make it on, `gh pr edit --add-label
  cd/preview`.

Record the PR URL as `pr:` in `STATE.md` when it opens. At phase 5, add it at the top of
`05-handoff.md`, set `status: awaiting approval`, and stop. **The design PR is never
merged.** Approval on it is the decision to implement.
