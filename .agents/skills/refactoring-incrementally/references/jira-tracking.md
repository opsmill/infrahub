# Jira tracking

Site `opsmill.atlassian.net` (cloud id: resolve with `getAccessibleAtlassianResources`), project
`IFC`. Jira mirrors the plan file for people who track work there; it is never the place the
skill decides what to do next — but human edits in Jira are input to reconciliation.

## Structure

- **Parent:** issue type `Task`, summary `Refactor: <name>`, label `refactor`. Description: the
  plan's Goal and End state paragraphs plus a link to the plan file on `stable` (the link 404s
  until step 0 merges — that's fine). If the user names an epic, set it as the parent's parent.
- **Sub-task per step:** issue type `Sub-task`, parent = the Task. Summary
  `[<NN>] <step intent>` so the Jira list sorts in plan order. Description: the step's detail
  block (touches, prerequisites, done-check).

Create sub-tasks for every planned step at plan time; re-planning adds, splits (create `7a`,
`7b`, close `7` as *Won't Do* with a comment pointing to them), or drops sub-tasks.

## Lifecycle per step

| Event | Jira action |
|-------|-------------|
| Branch created for the step | transition to *In Progress* |
| PR opened | transition to *In Review* (or the closest status `getTransitionsForJiraIssue` offers); comment with the PR URL |
| PR merged | transition to *Done*; comment with the merge commit |
| Forward port needed / opened | comment with the develop PR URL; stay *Done* |
| Step found already done by someone else | *Done* with a comment naming the commit/PR that did it |
| Step dropped | *Won't Do* (or *Done* if no such status) with the reason |
| Hand-off | add label `needs-human`; comment with the specific question for a person |

Transition names vary by workflow: always list transitions on the issue and pick by name rather
than hard-coding ids. If a transition doesn't exist, leave the status and say so in the comment.

## Reading human input

Each `next` run reads, on the parent and every open sub-task, comments newer than the last
skill comment, plus status changes and new sub-tasks made by people. Treat a person removing the
`needs-human` label (or commenting an answer) as the go-ahead to resume that step.

Never delete issues and never edit a person's comment. Keep skill comments short and factual —
they are an audit trail, not a chat.
