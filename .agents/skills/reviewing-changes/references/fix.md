# Phase 3: Fix and review the fixes

Show the classified list and wait for approval. Fix each approved finding with the smallest
change, run the checks in the touched area's `AGENTS.md`, and do not commit: the user reviews the
fixes. Note each finding the user rejects, with the reason they give, for Phase 4.

A browser-mode Vitest or Playwright timeout in a file the fixes did not touch can come from load
on the machine, for example other agents driving browsers at the same time. Rerun the failing
files once before counting the timeout as a failure, and report both runs.

## Review the fixes

Review the fixes as a new change, every time. A fix can break something the first round never
looked at, or resolve a finding only in part.

- **Scope.** Take `git diff HEAD --name-only`, minus the paths left out or set aside in Phase 0.
  List each path in it that the manifest does not list. Each such path must come from an Ask the
  user approved. Revert any other change to it before the review goes on.
- **Each fix.** Give one reviewer that did not write the fixes the classified list and
  `git diff HEAD`. For each fix it answers: does the change resolve the finding it cites, fully
  or in part, and is it the smallest change that does? It reports a fix that resolves nothing,
  resolves another problem, or changes more than the finding needs. A partial or oversized fix
  goes back to the fixer for the next round.
- **Bugs.** Run `code-review` with the arguments `high <path> <path> ...` for those paths.
- **Rules.** Give one reviewer per area, as in the rule check, `git diff HEAD -- <paths>` as the
  change, and ask it to check the fixed lines and the code around them.
- **Design.** When a fix moves code between files or entities, run the design check on the fixed
  lines: a move can add an import cycle, or a request the old place did not make.
- **Claims.** When a fix touches docs, a changelog, a guideline or the pull request description,
  run the claims check again on the fixed lines.
- **Removed exceptions.** When a fix removes an exception from a rule or guideline, check that the
  rule and its reason still hold for the code already shipped. If they do not, narrow the rule or
  propose a cleanup task instead of deleting the exception.

Stop when no P1 or P2 remains other than declined or deferred ones, or after three rounds.

## Records outside the code

When an approved fix reverses a behaviour or decision that is also written down elsewhere, find
each record that still states the old one:

- the Jira ticket named in the branch name or the pull request title (read it with the Atlassian
  tools)
- the open pull request's description (`gh pr view <n> --json body`)
- the `changelog/` fragments of this change
- the spec folder: grep `dev/specs/<feature>/` for the old behaviour

List each record with the sentence to change under "Records to update" in the report. Do not
edit Jira or GitHub yourself: the user updates them.
