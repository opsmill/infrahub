# The bug triager agent's routine

Fill in the values in angle brackets from the triage constitution and the goalie's answers.

| Setting | Value |
|---|---|
| Name | `Bug triager agent: <main repository>` |
| Schedule | working days at the goalie's time: `CRON_TZ=<time zone> <minute> <hour> * * 1-5`; without `CRON_TZ=`, the time is read as UTC |
| Repositories | the main repository and every related repository of the constitution, so that the run can write to each of them |
| Connectors | the goalie's Atlassian connector with Jira read and write, Slack, and Notion; remove the others |
| Model | the most capable model the account offers |
| Allowed tools | `Bash`, `Read`, `Write`, `Edit`, `Glob`, `Grep`, `Skill`, `ToolSearch`, `Agent`, `PushNotification`, and the tools of the three connectors |
| Notifications | push, when the account offers it |

- The prompt points the run at the skill files in its checkout of the main repository. Each run
  clones the default branch of each repository: the skills and the constitution take effect once
  they are merged there.
- When the first run's log shows that the Atlassian connector cannot connect or is refused, choose
  another Atlassian connector of the account and run again.
- A routine whose GitHub connection expires skips its runs until the goalie reconnects GitHub on
  claude.ai.

## Prompt

```text
You are the bug triager agent for <main repository>. Run today's triage.

Read .claude/skills/triaging-new-bugs/SKILL.md in the checkout of <main repository> below the
working directory, and follow it with the argument --daily. Read the other skills and references
it names from the same skills folder.

Nobody approves during this scheduled run. End with the table, and write nothing to GitHub or
Jira. When the session has a push notification tool, send one notification at the end: when the
table is ready, say how many bugs it holds, how many are priority 1, and how many are tied to a
security advisory; when the run stops before the table, name the reason.

When the goalie replies in this session later, follow the approval guard of the skills.
```
