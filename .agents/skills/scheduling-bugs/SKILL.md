---
name: scheduling-bugs
description: >-
  Decides where each rated bug goes (the current sprint, the current release, the next patch
  release, the next release or the backlog) and lines Jira up with that decision after the goalie
  approves. It never changes a priority. TRIGGER when: the goalie or the team wants to plan which
  bugs go into a release or sprint, clean the bugs out of a sprint, re-plan after a release is cut,
  or schedule the bugs of a period ("which bugs go into the next release", "clean up the sprint",
  "schedule the bugs since 1 October"), or triaging-new-bugs hands over the priority 1 and 2 bugs
  of a daily run. DO NOT TRIGGER when: rating new bugs or setting a priority → triaging-new-bugs;
  setting up the routine or the triage constitution → setting-up-bug-triage; analyzing or fixing
  one bug → opsmill-product-analyzing-bugs or opsmill-product-fixing-bugs.
argument-hint: "[--since <YYYY-MM-DD>|last-run] [--dry-run]"
compatibility: >-
  Needs the triage constitution in the repository, the Atlassian connector with Jira read and
  write, the Slack connector with search across public and private channels, the Notion connector,
  and GitHub REST access (gh api or the session's GitHub tools) to the constitution's repositories.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Schedule bugs

## Input

```text
$ARGUMENTS
```

- **Daily part:** triaging-new-bugs runs it in the bug triager agent's daily run and passes the
  bugs whose result is "a bug" and whose priority is 1 or 2. See [Daily part](#daily-part).
- **Run on its own**, over a period:
  - `--since <YYYY-MM-DD>`: from that date.
  - `--since last-run`: from the date of the newest release planning record: a
    `Bug scheduling, <date>, release planning:` or `Release triage, <date>:` comment. A dry run
    writes no comment, so it does not count as a run.
  - No `--since`: `last-run` when a release planning record exists after the previous minor
    release day, otherwise the previous minor release day, by the constitution's rule.
- `--dry-run`: end with the tables.

## Before anything

1. Load the bug-triage-rules skill, in `../bug-triage-rules/SKILL.md` from this skill's folder.
   Its approval guard, its never-do list and its recipes apply throughout.
2. Find and read the triage constitution.
3. Make one read from GitHub, Jira, Slack and Notion. Stop when one fails.

## What this skill decides

It decides where a bug goes. It reads what triaging-new-bugs left behind (the priority label, the
customer codes, the `Bug triage` comment) and never changes any of it.

- **Only rated bugs.** It never moves, edits or comments on tasks, stories, tech debt or epics. A
  bug with no priority gets no decision: it is listed under the tables for triaging-new-bugs. The
  rule for a Jira-only bug's default priority is in bug-triage-rules.
- **Sprints:** it moves bugs in and out of sprints, and never closes or edits a sprint.
- **GitHub:** it writes nothing there.
- **Jira fields:** it changes only the sprint, the parent epic and the comments.

## The frame

Work out the frame with the constitution's rules, reading the release status meetings as you go,
then show it in a short list:

- **Releases:** the current release, whether it is cut, and the next release.
- **Sprints:** the active sprint, with its name, id and number of open bugs, and the next sprint
  when one exists. Say so when the active sprint is past its end date. With no active sprint,
  nothing can be placed: a run on its own says so and writes nothing.
- **Bug epics:** the release bug epics of the current and the next release. Say so when one is
  missing. A bug that needs a missing epic gets "cannot place" with the reason.
- **Current work:** the ideas whose Roadmap field is the current release and whose stage is past
  the constitution's ideas before building, and the epics that work on them. A bug in one of those
  epics counts as current work. The release bug epics do not count.
- **Upcoming initiatives:** the ideas whose Roadmap field is the next release, the current-release
  ideas in a stage before building or with no stage, the scope notes of the three newest release
  status meetings, and the epics that work on all of these. Leave out ideas that are done or
  duplicates.
- **Period:** the start date and where it comes from.

In a run on its own, ask the goalie to confirm the frame and to name any bug they already want kept
or dropped. Their answer overrides the cases under [Decide each bug](#decide-each-bug).

## Filing rules

| The bug has… | Current release | Next release |
|---|---|---|
| no epic, or a release bug epic | the current release bug epic and the active sprint | the next release bug epic, and the next sprint when one exists |
| a topic epic, or the security epic | its epic, and the active sprint | its epic, and the next sprint when one exists, otherwise the backlog |

- **Next patch release:** when the current release is cut, a priority 2 bug that would go into the
  current release goes where the constitution's "Next patch release" field says, and a topic epic
  stays. A priority 1 bug stays in the current release.
- **Not recommended for the next release:** the bug goes to the backlog. It keeps a topic epic and
  leaves a release bug epic, whose list would otherwise hold a bug nobody plans to fix.
- A bug already where the rules put it needs no change and gets no comment.

## Daily part

Input: the bugs triaging-new-bugs passed: their result is "a bug" and their priority is 1 or 2.
The daily part reuses the constitution and the connector checks of that run, and works out only
the short frame below.

- **Priority 1:** the current release, by the filing rules, even when the release is cut.
- **Priority 2:** the current release, or the next patch release when the current release is cut.
- **An earlier decision** stands unless something new happened after it, as
  [Earlier decisions](#earlier-decisions) says. A priority raised in this run counts as new. Show
  the earlier decision in the placement.
- **A fix merged into a current release branch:** the bug stays where it is.
- **Missing sprint or epic:** when the active sprint or the release bug epic the rules need is
  missing, the placement is "cannot place" with the reason.

Return to triaging-new-bugs a short frame (the releases, whether the current one is cut, the active
sprint and whether it is past its end date, the two release bug epics) and one placement per bug:
the sprint and epic change, "no change", "keeps its earlier decision" with the decision and its
date, or "cannot place". After approval, write the moves of each approved bug, then, for a bug that
changed, the `Bug scheduling, <date>, daily run:` comment, before the bug's `Bug triage` comment.

## Earlier decisions

A run respects what earlier runs and people decided. Before collecting:

- Find the bugs with a release planning record (a `Bug scheduling, <date>, release planning:` or
  `Release triage` comment), and keep for each the date, the decision and the reason of the newest
  one.
- Read the change history only of the bugs whose proposed decision differs from where they sit, and
  of the bugs in the active sprint that have an earlier decision. Read only the fields `Sprint`,
  `IssueParentAssociation`, `status` and `priority`.
- A hand decision is any move by a person into or out of a release bug epic or the active sprint,
  or a status the constitution lists as not planned, made after the bug's newest scheduling
  comment. A move made with no scheduling comment on that bug is a hand decision, even when the
  person who ran an earlier run made it.
- Planning is not a decision: a bug placed in the sprint when the sprint started, or by a daily
  run, is the plan this run reviews. Only release planning records and hand decisions count.
  Otherwise every bug in the sprint would be protected, and the run could clean nothing.

An earlier decision stands unless something new happened after it:

- a new SA, customer or prospect report
- a priority change
- new discussion
- a new fix
- the initiative the decision named left the release or changed stage
- the goalie asks to revisit it

A decision of "current release" taken before the release was cut still holds after the cut, as
"next patch release", when the Jira placement is the same.

## Collect (read only)

Read Jira and the release status meetings yourself, and give Slack, GitHub and Notion to three
subagents in parallel, each with the period start, the releases and the recipes. Each returns rows
of: Jira key, GitHub number, one line on what goes wrong, source link, date, the signal found, and
the customer or prospect the source names, or "none named".

- **Jira:** the bugs in the active sprint, in the release bug epics and in the epics of current
  work, whatever their dates; and the open bugs with no epic created or changed in the period.
- **Security advisories:** the high and critical ones in draft or triage, matched to their Jira
  bugs by GHSA id. List under the tables an advisory with no Jira bug, and an advisory whose Jira
  bug is done, for its owner to publish or close.
- **Slack:** every link to a bug since the period start, found and sorted as the Slack recipes say.
- **GitHub:** open bugs with discussion in the period; open fix pull requests that wait only for a
  review or a merge, as the GitHub recipes define it; and fix pull requests merged in the period.
- **Notion:** the bug rows of the three newest release status meetings, when the constitution names
  them.

## Decide each bug

Merge the rows into one entry per bug, and note its signals:

1. an open security advisory of high or critical severity
2. a customer or prospect report, or an escalation, within the link lookback
3. an SA or FAE report
4. an older customer link, including customer codes already on the Jira issue
5. recent discussion: within the link lookback, by at least two people or by one person outside
   the organization. Posts by bots and comments that only run a command do not count.
6. current work

The signals order the rows of each table: the strongest signal first, then the priority.

| Priority | Signal | Decision |
|---|---|---|
| 1 | any | current release |
| 2 | at least one | current release, or the next patch release when the current release is cut |
| 2 | none | next release |
| 3 or 4 | at least one | next release |
| 3 or 4 | none | not recommended for the next release |

These cases override the table:

- A bug the goalie named in the frame follows the goalie.
- A bug tied to an open security advisory of high or critical severity goes to the current release.
- A bug with an earlier decision keeps it, unless something new happened since.
- A bug that belongs to an upcoming initiative goes to the next release, to be fixed with that work.
  It belongs to one when it is linked to the idea with the constitution's bug to idea link, or sits
  in an epic that works on it. List other possible matches under the tables for the goalie.
  - When someone already works on the bug (its status is in progress or in review, or a fix pull
    request was updated in the period), or its fix waits only for a review or a merge, place it in
    the current release and flag the initiative instead.
  - When the bug also has an SA or customer signal, show it in table 2 marked "goalie decides",
    even when nothing would change in Jira.
- A bug whose fix waits only for a review or a merge goes to the current release, when the pull
  request targets one of the constitution's current release branches, or, in a related repository,
  one of its integration branches. List the other waiting fixes under the tables.
- A bug whose fix is merged into a current release branch stays where it is, and is listed under
  the tables for closing once a GA release contains the fix.

An owner is not needed. The team assigns owners by hand, so a bug for the current release joins the
active sprint with or without one.

## Show two tables and wait

Number the rows of both tables in one sequence.

**Table 1: bugs for the active sprint.**

| # | Bug | What goes wrong | Why it is in, with sources | Priority | Owner | Earlier decision | Change in Jira |
|---|---|---|---|---|---|---|---|

"Change in Jira" is none, "set sprint", "set epic", "set epic and sprint", or "cannot place" with
the reason. "Owner" is the assignee, or "no owner yet". Table 1 also holds bugs outside the sprint
that this run brings in.

**Table 2: bugs leaving the active sprint, moving to another release, or for the goalie to decide.**

| # | Bug | Now | Why, with sources | Earlier decision | Decision | Where it goes |
|---|---|---|---|---|---|---|

It holds every other bug this run changes in Jira, and the bugs marked "goalie decides".

**Bugs the tables leave out.** When an earlier run exists, a bug appears in a table only when, after
its earlier decision or the period start, whichever is later:

- a person changed its sprint, epic, status, priority, assignee or customer codes
- a source found something new about it
- this run proposes a different decision

The moves and comments of earlier runs are not news, and neither is a change of rank.

Under the tables, list:

- the advisories with no Jira bug, and those whose Jira bug is done, named as the GitHub recipes say
- the fixes that wait only for a review or a merge, and the waiting fixes that do not reach the
  current release
- the fixes merged into a current release branch, for closing once a GA release contains them
- the bugs with no priority, for triaging-new-bugs
- other possible matches to an upcoming initiative
- requests from an SA with a deadline
- the bugs with something new whose decision stays, with what is new
- the bugs whose earlier decision changes between "next release" and "not recommended"
- how many bugs keep their earlier decision, and how many get a decision that changes nothing

Then ask the goalie to approve or change rows. With `--dry-run`, end here.

## Apply after approval

Write one approved bug at a time, and finish it before the next:

1. Out of the active sprint, for a bug of table 2 that is in it.
2. The parent epic, changed or cleared as the filing rules say.
3. Into the active sprint for a bug of table 1, or into the next sprint, when one exists, for a bug
   of table 2 that goes to the next release.
4. One comment, starting with `Bug scheduling, <date>, release planning:`. It records the decision,
   the reason and the sources. Do not state or question the priority: it comes from the label, and
   the reason stands on its own.

> Bug scheduling, 26 October 2026, release planning: moved out of the active sprint, next release
> (2.4). It belongs to the search performance work planned for 2.4 (link to the idea). It now sits
> in the 2.4 release bug epic (link).

## Check and report

Read Jira again and confirm each changed bug's sprint, epic and comment. Then report what changed,
how many open bugs the active sprint holds, and what is left for the goalie: bugs in the active
sprint with no owner yet, SA deadlines, and fixes waiting for a review or a merge.
