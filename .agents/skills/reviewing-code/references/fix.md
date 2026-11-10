# Phase 3: Fix and review the fixes

Show the classified list and wait for approval. Fix each approved finding with the smallest
change, run the checks in the touched area's `AGENTS.md`, and do not commit. Note each finding
the user rejects, with their reason, for Phase 4.

Rerun once a browser-mode Vitest or Playwright timeout in a file the fixes did not touch before
counting it as a failure: load from other agents on the machine can cause it. Report both runs.

## Review the fixes

Review the fixes as a new change after each round:

- **Scope.** List each path in `git diff HEAD --name-only` (minus the paths left out or set aside
  in Phase 0) that the manifest does not list. Revert it unless an approved Ask covers it.
- **Each fix.** A reviewer that did not write the fixes gets the classified list and
  `git diff HEAD`, and reports each fix that resolves nothing, resolves only part of its finding,
  or changes more than the finding needs. Those go back for the next round.
- **Bugs.** Run `code-review` with the arguments `high <path> <path> ...`.
- **Rules.** Run the rule check on `git diff HEAD -- <paths>` and the code around it.
- **Design.** When a fix moves code between files or entities, run the design check on it.
- **Claims.** When a fix touches docs, a changelog, a guideline or the pull request description,
  run the claims check on it.
- **Removed exceptions.** When a fix removes an exception from a rule, check that the rule still
  holds for the code already shipped. If not, narrow the rule or propose a cleanup task.

Stop when no P1 or P2 remains except declined or deferred ones, or after three rounds.

## Records outside the code

When an approved fix reverses a behaviour or decision written down elsewhere, list each record
that still states the old one, with the sentence to change, under "Records to update":

- the Jira ticket in the branch name or pull request title (read it with the Atlassian tools)
- the open pull request's description
- the `changelog/` fragments of this change
- `dev/specs/<feature>/` (grep for the old behaviour)

Do not edit Jira or GitHub: the user does.
