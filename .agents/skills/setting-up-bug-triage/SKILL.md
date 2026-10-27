---
name: setting-up-bug-triage
description: >-
  Sets up bug triage for a new goalie: writes the project's triage constitution when the
  repository has none, checks the goalie's access to GitHub, Jira, Slack and Notion, and creates
  the bug triager agent, a routine in the goalie's own Claude account that runs every working day.
  TRIGGER when: a new goalie takes over the rotation, someone wants to set up or recreate the bug
  triager agent or its routine, a project needs its triage constitution, or another bug-triage
  skill stops because the constitution is missing ("set me up as goalie", "set up the bug triage
  routine", "write the triage constitution"). DO NOT TRIGGER when: triaging bugs →
  triaging-new-bugs; scheduling bugs → scheduling-bugs.
argument-hint: "[--constitution-only | --routine-only]"
compatibility: >-
  Runs on the goalie's machine in a checkout of the main repository. Needs the Atlassian, Slack and
  Notion connectors, gh signed in to GitHub, and a way to create routines (the schedule skill, the
  RemoteTrigger tool, or the routines page of claude.ai/code).
metadata:
  version: 0.1.0
  author: OpsMill
---

# Set up bug triage for a goalie

## Input

```text
$ARGUMENTS
```

- `--constitution-only`: write or check the triage constitution and run the access check, then
  stop before the routine.
- `--routine-only`: skip to the routine. The constitution must already exist.

## Before anything

Load the bug-triage-rules skill, in `../bug-triage-rules/SKILL.md` from this skill's folder, and
read its [constitution format](../bug-triage-rules/references/constitution.md).

## The triage constitution

Look for `.agents/bug-triage-constitution.md` at the root of the checkout.

**When it exists,** keep it, and check it:

- Every field of the format is present and holds a value or `none`.
- Each field passes the check in the last column of the format's field table. Show the fields
  marked "goalie confirms" to the goalie and ask them to confirm each one.
- The default branch holds the same file:
  `gh api 'repos/<main repository>/contents/.agents/bug-triage-constitution.md?ref=<default branch>'`.
  The routine reads only that copy, so report when it is missing there or differs.

Report what is missing or broken, and change a field only when the goalie asks. Remind the goalie
that in a public repository the channel names and page links in the file are public.

**When it is missing,** build it with the goalie, one section at a time. Find each value yourself
first, then ask the goalie to confirm it or give the right one:

- **Repositories:** the main repository is the checkout's `origin`. Ask for the related
  repositories whose bugs the goalie also owns.
- **Each repository:**
  - its Jira project: find the Jira copy of one recent issue through the GitHub URL field
  - its labels: `gh api --paginate repos/<repo>/labels`, or the label file when the repository has
    one
  - the labels removed before a close: ask, and explain that these are the labels that make the
    Jira sync reopen a closed issue
  - its routing labels: look for the rules file that a labeling workflow or agent uses
  - its issue types: the organization's issue types (`gh api orgs/<owner>/issue-types`) that the
    repository's issues use
  - its title prefixes for a bug and a feature request, from its issue templates
  - its GA release tag pattern from its releases, its release branch pattern from its branches, and
    the integration branches that fixes are merged into
- **Jira:**
  - the site and cloudId, from the Atlassian connector
  - the board that holds the sprints: list the boards and ask which one
  - the bug issue type and its id, and the field ids of the GitHub URL, sprint and customer fields,
    from the bug issue type's fields
  - the fields the sync copies from GitHub, the draft status, the statuses that mean a bug is not
    planned, the Jira-only priority mapping and the default priority of a new issue: ask
  - the release bug epic pattern: search the epics, and ask
  - where a bug for the next patch release goes, and the security epic: ask
  - the ideas board, its Roadmap and Product stage fields, the stages before building, and the link
    type from a bug to an idea: list the link types, and ask
- **Slack:** the escalation channel, the customer and prospect channel prefixes and the channels
  with those prefixes that belong to no customer, the never-read prefixes of channels shared with
  people outside the company, the channels whose posts fill the link searches (such as a Jira
  notification channel), the SA and FAE profile titles, and the link lookback (21 days unless the
  goalie says otherwise).
- **Priority rules:** the page and section that hold the priority criteria, and the page that says
  what counts as a bug or a feature request. Fetch each and confirm it holds what it should.
- **Releases:** propose rules for the current release, the release cut and the previous minor
  release day from the tags and branches, and the branches the current release ships from before
  and after its cut, and ask. Ask where the release status meeting notes are.

Show the whole file, and write it only after the goalie approves it. Then tell the goalie:

- The routine reads the file from the repository's default branch, so it must be committed and
  merged there before the first scheduled run.
- In a public repository, the channel names and page links in the file are public.

## Access check

Make these reads as the goalie, and report the results in a short list:

- **GitHub:** one open bug of each repository through `gh api`, the goalie's write access to each
  repository (`gh api repos/<repo> --jq .permissions`, where `push` or `triage` must be `true`), and
  its draft security advisories, which need the security manager role
- **Jira:** one search in each Jira project, with each Atlassian connector the session has. Name
  the connector that works: the routine gets that one.
- **Slack:** one link search
- **Notion:** the priority page

Stop when a read fails, and say what to fix. An advisory read that fails does not stop the setup:
report that the runs will say the advisories could not be read.

## The bug triager agent

The bug triager agent is a routine in the goalie's own Claude account. It runs triaging-new-bugs
every working day, which hands the priority 1 and 2 bugs to scheduling-bugs, and it stops at one
table for the goalie to approve.

1. List the goalie's routines. When a bug triager agent routine for this repository already exists,
   show it and ask whether to keep it, update it or replace it. Never create a second one.
2. Ask for the time and the time zone of the daily run.
3. Show the routine's definition from [references/routine.md](references/routine.md), filled in,
   and ask the goalie to approve it.
4. Create it with the schedule skill or the RemoteTrigger tool, whichever the session has. When it
   has neither, give the goalie the values to enter on the routines page of claude.ai/code.
5. Read the routine back and check its schedule, repositories, connectors and prompt.
6. With the goalie's agreement, start one run now. The run ends with the table and writes nothing.
   Read its log and look for connector errors, refused calls and a missing constitution.

## Tell the goalie how a day works

- The routine runs every working day at the chosen time. When the account offers push
  notifications, it sends one when the table is ready, or when the run stops before its table.
- No notification by the usual time means the run did not happen or stopped: open the routine's
  latest run on claude.ai/code.
- Open the run's session from the notification or from claude.ai/code, read the table and the
  GitHub comments under it, and reply in that session: "approve", "approve all but 2 and 5", or a
  change to a row.
- Escalate the priority 1 bugs the report lists, as the priority page says. The routine sends no
  Slack messages or emails.
- To schedule bugs over a period, or to triage one bug by hand, start Claude Code in a checkout of
  the main repository and run `/scheduling-bugs` or `/triaging-new-bugs`. The skills load from the
  repository's skills folder, with nothing to install.
