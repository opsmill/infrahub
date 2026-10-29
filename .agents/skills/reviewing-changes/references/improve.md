# Phase 7 — Propose improvements

Every run shows where the rules, the docs or this skill fell short. Draft a proposal for each
case below, put them in the report under "Proposed improvements", and apply only the ones the
user approves after reading the report.

## Read the log first

Read `$(git rev-parse --git-common-dir)/reviewing-changes/proposals.md` when it exists. For each
draft, look for the same target and the same change in the log:

- Rejected before: keep the draft only when this run adds a new reason, and quote the earlier
  decision with its date.
- Proposed before and still pending, or applied and the problem came back: say how many runs
  proposed it.

## Rules and the index

- **A "Not violations" line** in a rule, for a finding declined because the rule did not mention
  the accepted pattern. When the declined pattern is debt rather than an accepted pattern,
  propose a cleanup task instead: a rule states the target, not exceptions for existing code.
- **A new rule line** in `.agents/rules/`, for what cubic or a reviewer caught that no rule states.
- **A `paths:` glob or a new rule file**, for each changed area that no rule's globs cover.
- **A better "load before" line** in an `AGENTS.md`, for each article a reviewer had to open on
  its own: say when that article applies, so the next agent is pointed to it.
- **A narrower rule line**, for each finding the user rejected in Phase 6 because the rule asked
  for something they do not want. Quote the reason they gave.

Keep each `cubic.yaml` entry under 9,000 characters (`wc -m`); cubic drops everything past
10,000. A new rule file with new paths also goes in `cubic.yaml`; a new `dev/` article needs an
`AGENTS.md` line, or `repo-context.py --check-index` fails in CI.

## Knowledge and guideline articles

- **A correction**, for each statement in a `dev/knowledge/`, `dev/guidelines/` or `dev/guides/`
  article that the code read during the verification contradicts. Give the article's
  `path:line`, the corrected sentence, and the `file:line` that shows it.
- **An addition**, for a fact a reviewer had to find in the code or a library's source because
  no article states it, when the next change in that area needs it too. Name the article it
  belongs in. Do not propose one for a fact only this change needs.

## This skill

Propose a change to `SKILL.md` or a file of `references/`, naming the step, for each of these:

- cubic failed or returned a result the skill could not read
- a reviewer's `READ:` list missed a listed file after the second request
- every finding of one check was declined or rejected by the user
- the user rejected a finding for a reason the skill could have checked itself
- the user had to correct the scope, the classification or a fix by hand
- the hooks were inactive, and pasting the context block did not give a reviewer the file it
  needed
- in a compare, a miss that no rule or document change would prevent

## After the report

Ask the user which proposals to apply. Apply the approved ones, then run
`python3 .agents/scripts/repo-context.py --check-index`. Do not commit: the user reviews the
changes.

Append one line per proposal to the log, whatever the decision:

```text
<date> | <branch> | <target path> | <proposal in one line> | <applied | rejected: reason | pending>
```

The log is inside `.git`, so it is never committed, and every worktree of the repository reads
the same one.
