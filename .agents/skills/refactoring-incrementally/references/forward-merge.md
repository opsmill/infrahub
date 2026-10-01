# Forward merge: keeping `develop` clean

Changes reach `develop` through the regular automated stable→develop process: a bot opens a PR
titled "Merge stable into develop" with head `stable`. When it conflicts, a person usually opens a
manual merge PR. This skill relies on that process and steps in **only for conflicts it caused**.

## Detecting conflicts

```bash
.agents/skills/refactoring-incrementally/scripts/forward_conflicts.sh <source-ref> <dest-ref>
```

Prints the conflicted paths of a trial merge of `<source-ref>` into `<dest-ref>`, one per line,
and exits 0 when clean, 1 when conflicted, 2 on error. It never modifies the working tree.

Find which conflicted files are ours: collect the files changed by this refactor's merged step
PRs (`gh pr view <n> --json files`) and intersect. Also check the open bot PR:

```bash
gh pr list --base develop --head stable --state open --json number,url,mergeable
```

## Acting on the result

| Situation | Action |
|-----------|--------|
| No conflicted file is ours | Nothing. Not this skill's job. |
| A bot (or manual) merge PR is open and **every** conflict is ours | Take it over with the `merging-branches` skill (`stable` into `develop`, or the PR link). Resolve only our files; the merge is otherwise clean. |
| Conflicts are a mix of ours and other people's | Open a **develop port PR** for our share (below), so that only the others remain for whoever does the merge. Comment on the bot PR linking it. |
| A person already has a manual merge PR in progress | Don't compete. Comment on it with how to resolve our files (which side to take and why), and stop. |

## Develop port PR

Goal: make `develop` already contain our change, so that git sees the same edit on both sides
and the stable→develop merge has nothing to reconcile in those hunks.

1. Branch off `origin/develop`: `<branch_prefix>-<NN>-develop-port`.
2. `git cherry-pick -x <step merge commit>` (for a squash merge, that is the single commit on
   `stable`). Resolve conflicts against `develop`'s version of the code.
3. Where possible, make the resulting text in the conflicted hunks **identical** to `stable`'s —
   identical edits on both sides merge cleanly. Where `develop` genuinely needs different code
   (it has extra callers, a renamed symbol), adapt it; the merge will still conflict there, but
   the resolution becomes "take develop's side", which the port PR description should say
   explicitly.
4. Verify with the script: `forward_conflicts.sh origin/stable HEAD` — our files should no longer
   appear (or only the ones noted as "take develop's side").
5. Run `/pre-ci` against the develop worktree, open the PR with base `develop`, title
   `refactor: port step <NN> of <name> to develop [<sub-task key>]`, and comment the URL on the
   sub-task.

## Prevention beats repair

- At plan time and at every reconciliation, prefer slices whose files are identical on `stable` and
  `develop` (`git diff --quiet origin/stable origin/develop -- <files>`).
- Before opening a step PR, trial-merge the branch into `develop`. If it conflicts, re-slice so
  the step avoids the divergent hunks when that's reasonable.
- If a region of the code is churning on `develop` (a feature in flight), park the steps that touch
  it until that work has landed, and note it in the plan's *Forward-merge notes*.
