# Phase 5: Hand off

Read this when phase 5 starts. The rules in `SKILL.md` still apply.

Write the design doc to `05-handoff.md`, publish it as an Artifact, and add the URL at the
top of the file. The repo copy is the one that lasts; links can break or sit behind
access rules. The doc has these sections, in order:

1. **What and why**: the brief, in the user's words.
2. **Proposal**: the chosen direction, a screenshot of each state, the prototype URL, and
   the review level (full or reduced) from `04-review.md`.
3. **Rejected directions**: one paragraph per direction from `02-directions.md`, with the
   reason.
4. **Decisions**: from `03-decisions.md`.
5. **Open questions**: what the user still has to decide.
6. **System gaps**: the `Missing` list from `01-system.md`.
7. **History**: `dj.variant` and `dj.rev` links to every direction and revision, and the
   `git log -p .design/<slug>/` command. Say that old revisions change if design tokens
   change.

Save the screenshots in `.design/<slug>/shots/`. Give the user the link and one sentence
to post above it.

Replace the design PR body with `05-handoff.md`, set `status: awaiting approval`, and
stop. The design PR is never merged; approving it is the decision to implement. Details
are in [`design-pr.md`](design-pr.md).

Write `05-implement.md`, so implementation starts by copying the approved revision rather
than rebuilding it. Its lists, the implementation branch and the teardown checklist are in
[`implementation.md`](implementation.md).
