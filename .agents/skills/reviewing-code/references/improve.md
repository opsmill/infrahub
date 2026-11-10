# Phase 4: Propose improvements

Draft a proposal for each case below and list it under "Proposed improvements" in the report.
Apply only what the user approves after reading it.

First read the log, `$(git rev-parse --git-common-dir)/reviewing-code/proposals.md`, when it
exists. Drop a draft rejected before unless this run gives a new reason, and quote the earlier
decision with its date. For a draft proposed before, say in how many runs.

## Rules and the index

- **A "Not violations" line**, for a finding declined because the rule did not name the accepted
  pattern. When the pattern is debt rather than accepted, propose a cleanup task instead.
- **A new rule line** in `.agents/rules/`, for what a pull request reviewer caught that no rule
  states.
- **A `paths:` glob or a new rule file**, for each changed area no rule covers.
- **A better "load before" line** in an `AGENTS.md`, for each article a reviewer had to find on
  its own.
- **A narrower rule line**, for each finding the user rejected because the rule asks for
  something they do not want. Quote their reason.

A new `dev/` article needs an `AGENTS.md` line, or `repo-context.py --check-index` fails in CI.

## Articles

- **A correction**, for each statement in a `dev/knowledge/`, `dev/guidelines/` or `dev/guides/`
  article the code contradicts: the article's `path:line`, the corrected sentence and the
  `file:line` that shows it.
- **An addition**, for a fact a reviewer had to find in the code that the next change in that
  area needs too. Name the article.

## This skill

Propose a change to a file of this skill, naming the step, when:

- a reviewer missed a listed file after the second request
- the user rejected or the skill declined every finding of one check
- the user rejected a finding for a reason the skill could have checked
- the user corrected the scope, the classification or a fix by hand
- the hooks were inactive and a reviewer lacked a file it needed
- a compare found a miss no rule or document change would prevent

## After the report

Ask the user which proposals to apply; in PR mode, log every proposal as pending without asking.
Apply the approved ones, run `python3 .agents/scripts/repo-context.py --check-index`, and do not
commit. Append one line per proposal to the log:

```text
<date> | <branch> | <target path> | <proposal> | <applied | rejected: reason | pending>
```
