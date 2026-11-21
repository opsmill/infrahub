# Phase 3: Refine

Read this when phase 3 starts. The rules in `SKILL.md` still apply.

Invoke `emil-design-eng`. Take the chosen direction to a finished screen: hierarchy,
spacing, copy, keyboard behaviour, and every state it can be in, including loading,
empty, error, permission denied and too much data. Add `emil-animations` (or `animate`) only under
its condition in [`phase-2-explore.md`](phase-2-explore.md).

The chosen direction becomes `dj.variant=<pick>&dj.rev=1`. Keep the other directions
reachable, and create each new revision as a copy of the last, as
[`revisions.md`](revisions.md) describes.

## Rounds

Feedback arrives over days, so refining runs in rounds that can be resumed at any step:

1. **Build** rev N, commit and push. The push rebuilds the preview.
2. **Share**: post one comment on the design PR with what changed, the preview link and
   "pin notes, then press *Copy gh command* and run it". Set `status: awaiting feedback since <date>`.
3. **Collect**: reviewers pin notes and post them to the PR. Nothing to do.
4. **Gather**: when the owner says "gather", read the PR comments with
   `gh pr view <number> --comments` (or `gh api repos/{owner}/{repo}/issues/<number>/comments`
   for timestamps). Keep the comments that start with `<!-- design-jam:<slug> -->` and are
   newer than `gathered:`. Copy them word for word, with author and date, to
   `.design/<slug>/feedback/round-<N>.md`, and update `gathered:`. If `gh` cannot reach the
   PR, ask the owner to paste the comments or a *Copy all notes* block.
5. **Triage** every open note with the owner as one of:
   - `addressed`: it changes in rev N+1; say how.
   - `declined`: it does not change; write the reason in `03-decisions.md`.
   - `deferred`: write down what it waits for.

   Reply on the PR with one line per note, so reviewers see what happened to it.
6. **Checkpoint**, then start rev N+1.

Do not start rev N+1 while notes are untriaged. If a round gets no notes, write that down
and ask the owner whether nobody objected or nobody looked.

Write `03-decisions.md`: every choice that is not obvious, one line each, with its reason.
Record each knob's final value as a number.
