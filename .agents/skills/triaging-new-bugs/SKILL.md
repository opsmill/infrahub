---
name: triaging-new-bugs
description: >-
  Proposes what each incoming bug is and how serious it is (bug or feature request, duplicate,
  already fixed in a newer release, too big for a release, priority, customers), shows one table,
  and writes the results only after the goalie approves. TRIGGER when: the goalie wants to triage
  new or unprioritised bugs, rate incoming issues, run the daily bug triage, or check the bugs
  escalated or linked from customer channels ("triage today's bugs", "what came in", "rate the new
  issues"), or the bug triager agent starts its daily run. DO NOT TRIGGER when: deciding which
  sprint or release bugs go into → scheduling-bugs; setting up the routine or the triage
  constitution → setting-up-bug-triage; analyzing or fixing one bug → opsmill-product-analyzing-bugs
  or opsmill-product-fixing-bugs.
argument-hint: "[--daily] [--dry-run] [<issue URL, owner/name#number or Jira key> ...]"
compatibility: >-
  Needs the triage constitution in the repository, the Atlassian connector with Jira read and
  write, the Slack connector with search across public and private channels, the Notion connector,
  and GitHub REST access (gh api or the session's GitHub tools) to the constitution's repositories.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Triage new bugs

## Input

```text
$ARGUMENTS
```

- `--daily`: the bug triager agent's daily run. scheduling-bugs adds the placement of the priority
  1 and 2 bugs to the same table, and one approval covers both.
- `--dry-run`: end with the table.
- Issue URLs, `<owner>/<name>#<number>` or Jira keys: triage only these, and ignore the skip rule.
- Nothing: collect the bugs as described below.

## Before anything

1. Load the bug-triage-rules skill, in `../bug-triage-rules/SKILL.md` from this skill's folder.
   Its approval guard, its never-do list and its recipes apply throughout.
2. Find and read the triage constitution.
3. Fetch the priority page, and the bug or feature page when the constitution names one.
4. Make one read from GitHub, Jira, Slack and Notion. Stop when one fails.

## What this skill decides

It decides what an issue is: its kind, its priority, its customers and the result of its checks.

- It never touches sprints, epics or releases, except to put a bug tied to a security advisory in
  the security epic. scheduling-bugs does the rest.
- It never writes a label that records a reproduction.
- It never adds a label that asks for more information, never waits for a reporter, and never
  closes a bug because nobody answered.

## Collect the bugs (read only)

"Since the previous working day" means since 00:00 UTC on the working day before today. From every
repository in the constitution, and from Jira, collect these open issues:

- bugs with no priority label
- issues with no type label: those reported since the previous working day, and older ones whose
  title starts with the bug title prefix
- issues linked in the escalation channel or in a customer or prospect channel within the link
  lookback, whatever their type and priority
- bugs linked by an SA or FAE in any other channel within the link lookback, and bugs an SA or FAE
  filed within the link lookback
- bugs reopened since the previous working day, and bugs that got a priority label since then and
  have no `Bug triage` comment
- bugs whose `Bug triage` comment records a fix merged but not released, when their repository
  published a GA release after that comment
- Jira-only bugs with no `Bug triage` comment that are in the draft status, or that still hold the
  default priority in any open status
- bugs tied to a security advisory of high or critical severity, in draft or triage

**Skip rule.** Skip every collected issue whose Jira issue already has a `Bug triage` comment,
whatever its type, and count it under the table, unless one of these happened after that comment:

- it was linked again in the escalation channel or in a customer or prospect channel
- it was reopened
- its repository published a GA release, and the comment records a fix merged but not released

**Order of the run.** Handle the groups in this order, so the bugs that block customers are done
even when a run stops early. A bug belongs to the first group that applies to it.

1. bugs tied to a security advisory
2. bugs linked from the escalation channel or a customer or prospect channel
3. bugs reported by an SA or FAE
4. issues reported, reopened or given a priority since the previous working day, oldest first
5. the backlog: every other collected issue, at most 10 in one run. Bugs come first (the bug label,
   the bug title prefix, or the bug issue type), then a priority a person set before none, then the
   oldest.

The backlog issues a run leaves out are counted under the table and wait for the next runs.

## Check each issue (read only)

Only bugs are checked and rated. An issue of another type that a channel links, such as tech debt,
gets only the customer step.

For every bug, also one that already has a priority:

- **Bug or another kind.** It is a feature request when it asks for something the product does not
  do, or when the behaviour works as designed, even when someone disputes that design. Follow the
  bug or feature page when the constitution names one. An issue with no type can also be a task, a
  piece of tech debt or documentation work.
- **Duplicate.** Another open issue reports the same failure. A bug filed again because an earlier
  fix did not work is not a duplicate: find the earlier report and its fix.
- **Fixed in a release newer than the reporter's version.** Find the fix and the first GA release
  that contains it.
  - A fix the report says did not work does not make the bug fixed. When the reporter's version
    contains it, the result is a bug. When the version is older, keep the bug open and ask the
    reporter to try the first release that contains the fix. When the report states no version,
    keep it open and ask for the version.
  - A fix that is merged but in no GA release yet, or only on a branch or in an open pull request,
    does not count: say so in the table and keep the bug open.
- **Too big for a release.** The bug needs design or planning, not a fix. Look on the ideas board
  for the idea of the larger initiative that covers it.
- **Priority.** Rate with the priority page, following bug-triage-rules. A post in the escalation
  channel is an escalation when it asks for the bug to be handled; a post that only asks for a
  review of a fix is a link, not an escalation.
- **Customers.** Follow bug-triage-rules.
- **SA or FAE report.** The person who posted the link, or who filed the issue, is one. Find a
  GitHub author in Slack by the name on their GitHub profile or by their login, as the recipes say,
  and the reporter of a Jira-only bug by their name. When nobody is found, write "not known".
- **Routing labels.** For a repository with routing labels, propose the missing ones with the rules
  file the constitution names. Never replace a routing label that is already set.
- **Issue type.** When the repository uses issue types and the issue has none, propose the one that
  matches its result.
- **Missing information.** Write the question for the reporter. The bug still gets its priority
  from what the report says.

When more than five bugs need these checks, split them among subagents, a few bugs each, with this
section and the recipes. Each returns one row per bug with its sources. Check every "duplicate" and
"fixed" result yourself before it goes in the table.

## Bugs tied to a security advisory

These get a light triage only, and none of the other checks.

- Flag each one first in the report, with the GHSA id, the summary and the severity.
- Propose a priority with the priority page. When no criterion of the page fits a security bug,
  keep the priority the bug has; with none, leave it for the goalie to set, and say so.
- Nothing about them goes on GitHub: no issue, no label, no comment.
- After approval, set the constitution's security epic as the parent of the advisory's Jira issue,
  or create a Jira-only issue in it when there is none. With no security epic in the constitution,
  list them and say the epic is missing.
- When the advisory's Jira issue is already done, report the advisory for its owner to publish or
  close, and write nothing.
- They are not passed to scheduling-bugs.

## What each result writes after approval

| Result | GitHub | Jira |
|---|---|---|
| A bug | the priority label, and the old priority label removed when it changes; the bug label when it has none; the missing routing labels; the bug issue type when it has none; a comment only to ask for missing information | none |
| Not a bug | the feature label instead of the bug label, the priority label removed, the feature issue type, the bug title prefix changed to the feature title prefix, a comment that explains why | none |
| Another kind, such as a task | the type label that matches; no comment. List the issue for the goalie to set its issue type by hand | none |
| Too big, an idea exists | as for a bug, and a comment that says the bug is part of a larger initiative | the link from the bug to the idea |
| Too big, no idea | the same as "not a bug" | none |
| Duplicate | the labels removed before a close, the duplicate label, a comment that names the other issue, close as duplicate | none |
| Fixed in a newer release | the labels removed before a close, a comment that names the fix and the first release that contains it, close as completed | none |

Every issue that stays open also gets its customer codes. A duplicate's customer codes go to the
issue it duplicates. Every handled issue ends with its `Bug triage` comment in Jira.

**A Jira-only bug** has no GitHub issue, so its writes all go to Jira: its priority, and its routing
labels by the main repository's rules. The skills never change a Jira status or type, so a result
other than "a bug", and a question for the reporter, go in its `Bug triage` comment, and the bug is
listed under the table for the goalie to change by hand.

## Daily run

With `--daily`, after the checks and before the table, load scheduling-bugs, in
`../scheduling-bugs/SKILL.md` from this skill's folder, and run its daily part. Pass it the issues
whose result is "a bug" and whose priority, proposed or kept, is 1 or 2. Bugs tied to a security
advisory and bugs that are too big for a release are not passed. Its frame goes above the table and
its placement in the table, and one approval covers both.

When the goalie changes a row so that it becomes a priority 1 or 2 bug, run the daily part for that
bug, show its placement, and ask for approval of that row; write the other approved rows
meanwhile. When the change takes a row out of that, drop its placement.

## Show one table and wait

Above the table, in this order:

- bugs tied to a security advisory: GHSA id, severity, proposed priority, where they go in Jira
- priority 1 bugs with their evidence, for the goalie to escalate as the priority page says
- in a daily run, the frame from scheduling-bugs

The table, one row per issue, numbered:

| # | Issue | What goes wrong | Result | Priority and criterion | Customers | GitHub changes | Jira changes |
|---|---|---|---|---|---|---|---|

- Link every issue and every source.
- "Priority and criterion" shows a change as `3 → 2` with the criterion of the page that matched.
- In a daily run, scheduling-bugs adds a "Placement" column.

Under the table:

- the exact text of every GitHub comment, by row number, because GitHub can be public
- customer names with no matching code, with the codes already on the issue, for the goalie to
  choose one
- fixes that are merged but not released, and fixes found only on a branch or in an open pull
  request
- Jira-only bugs whose result the goalie applies by hand
- issues not handled, with the reason, such as a GitHub issue with no Jira copy yet
- how many issues the skip rule left out, and how many backlog issues wait for the next runs
- the advisories that could not be read, when the call failed

Then ask the goalie to approve or change rows. A scheduled run, or a run with `--dry-run`, ends
here.

## Apply after approval

One bug at a time, in this order:

1. **GitHub:** one call that sets the labels, the issue type and the title, as the GitHub recipes
   say; then the comments; then, for a close, the close.
2. **Jira:** the customer codes, the link to the idea, the security epic, and the labels and
   priority of a Jira-only bug.
3. **Placement:** in a daily run, the writes of scheduling-bugs for that bug.
4. **Run record:** the `Bug triage, <date>:` comment on the bug's Jira issue. It is always the last
   write for a bug.

The run record says, with links to the sources:

- the priority and the criterion of the page that matched, or why the bug got none
- the customers and the source that ties each one to the bug
- the result of the checks, with `Fix merged, not released:` and its link when that is the result
- whether an SA or FAE reported the bug
- the question asked of the reporter, when there was one

Example:

> Bug triage, 26 October 2026: priority 2, "<the criterion, in the page's words>": the list takes
> several seconds longer to load since the last minor release. Customers: two codes added, from a
> thread in each customer channel (links). Checks: a bug; no open duplicate; not fixed in a newer
> release. Reported by an SA (link).

## Report

Read every changed issue back, when the approval guard says, then report:

- what changed, and the rows skipped because someone changed the issue after the table was built
- what the read-back found different from what was written, such as a label put back on the issue
- the priority 1 bugs, for the goalie to escalate
- issue types that did not change, to set by hand
- the Jira-only bugs to change by hand, and the triaged Jira-only bugs still in the draft status
- customer names still without a code
- issues not handled, which the next run picks up

## Common mistakes

| Mistake | What to do instead |
|---|---|
| Closing an issue that still carries a label from the "removed before a close" list | Remove those labels first; otherwise the sync reopens the issue |
| Changing labels in several calls, one label at a time | Send the labels, the issue type and the title in one call; between two calls the sync can put a removed label back |
| Adding the new priority label and leaving the old one | Remove the old priority label in the same row |
| Treating a report filed again after a failed fix as a duplicate, or as fixed | A failed fix means the bug is still open; check the reporter's version |
| Calling a bug fixed because a merged pull request mentions it | Read the change, then check that a GA release contains it |
| Calling a bug live because no pull request mentions it | Fixes often land in changes that never name the issue; read the code history |
| Treating every post in the escalation channel as an escalation | Only a post that asks for the bug to be handled is one |
| Lowering a priority because the report lacks information | Rate from what the report says, and ask in a comment |
| Opening a thread in a never-read channel because the search returned it | Drop the hit unread |
| Running `gh issue …` commands in a cloud session | Use `gh api` on `repos/<owner>/<name>/…` endpoints |
