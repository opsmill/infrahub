# Jira recipes

Values in angle brackets come from the constitution's Jira section. Pass the cloudId on every call.
Operations named here that are not tools of their own run through `executeRead` or
`executeWrite`. When an operation name is refused, look it up with `discover`; never invent one.

Use the Atlassian connector whose tools include `executeRead` and `discover`. An account can have
another Atlassian connector that refuses Jira with "The app is not installed on this instance".

## Contents

- [Find the Jira issue of a bug](#find-the-jira-issue-of-a-bug)
- [Read queries](#read-queries)
- [Writes](#writes)

## Find the Jira issue of a bug

- **Jira copy of a GitHub issue:** the GitHub URL field holds the issue URL. It is a URL field, so
  JQL matches it exactly and `~` fails:
  `cf[<GitHub URL field number>] = "https://github.com/<owner>/<name>/issues/<number>"`.
  When that finds nothing, try `summary ~ "<issue title>"`. A copy can lag a few minutes behind a
  new GitHub issue. With no copy yet, report the bug as not handled; the next run picks it up.
- **Jira-only bug:** its GitHub URL field is empty. Its labels and its priority live in Jira, so the
  skills read and write them there:
  - Map its priority with the constitution's Jira-only priorities. To write a priority that two
    Jira priorities map to, use the first one listed.
  - The rule for the default priority is in bug-triage-rules, under "Rating a bug with the priority
    page".
- **Jira issue of a security advisory:** `project in (<projects>) AND text ~ "\"<GHSA id>\""`.

## Read queries

- **Sprints:** `listJiraBoardSprints` with `{"boardId": <board>, "state": "active"}`, and with
  `"state": "future"` for the next sprint. A bug's own sprints are in the sprint field; the active
  one has `state: active`.
- **Release bug epic of a release:**
  `issuetype = Epic AND summary ~ "\"<release bug epic summary, with the release filled in>\""`.
- **Open bugs in a sprint:**
  `sprint = <id> AND issuetype = "<bug issue type name>" AND statusCategory != Done`.
- **Open bugs in some epics:**
  `parent in (<keys>) AND issuetype = "<bug issue type name>" AND statusCategory != Done`.
- **Jira-only bugs nobody triaged:**
  `project in (<projects>) AND issuetype = "<bug issue type name>" AND statusCategory != Done AND cf[<GitHub URL field number>] is EMPTY AND (status = "<draft status>" OR priority = "<default priority>")`,
  then drop the bugs whose comments hold a `Bug triage` record. Do not filter with
  `comment !~` in the query: it leaves out every issue that has no comment at all.
- **Bugs with a run record:** `project in (<projects>) AND comment ~ "\"Bug triage\""`, and the same
  with `"Bug scheduling"` and `"Release triage"`. Then read each bug's comments to get the date of
  the newest record. Use the comment's creation date, not the date in its text.
- **Bugs waiting for a release of their fix:**
  `project in (<projects>) AND statusCategory != Done AND comment ~ "\"Fix merged, not released\""`.
- **Comments:** `listJiraIssueComments` with `{"issueIdOrKey": "<key>"}`.
- **Change history:** `listJiraIssueChangelogs`, with `responseFields` `values.created`,
  `values.author.displayName`, `values.items.field`, `values.items.fromString` and
  `values.items.toString`, because descriptions in the history are long. Sprint changes have the
  field `Sprint`, epic changes `IssueParentAssociation`.
- **Custom fields in search results:** pass `view: "evidence"` or name the fields; the default view
  leaves them out.
- **Customer codes and their ids:** `getJiraIssueTypeMetaWithFields` with
  `{"projectIdOrKey": "<project>", "issueTypeId": "<bug issue type id>", "requiredFieldsOnly": false, "maxResults": 200}`.
  The customer field's entry lists each code's `value` and `id`.
- **Ideas of a release:** `project = <ideas board> AND cf[<Roadmap field number>] = "<release>"`,
  with `view: "evidence"` to read the Roadmap and Product stage fields.
- **Epics that work on ideas:** merge the results of both queries, and drop the release bug epics:
  - linked on the board: `issuetype = Epic AND (<one "issue in linkedIssues(<idea key>)" clause per idea, joined with OR>)`
  - named in text: `issuetype = Epic AND statusCategory != Done AND (summary ~ "\"<release>\"" OR <one description ~ "<idea key>" clause per idea, joined with OR>)`
- **Links of one issue:** `getJiraIssue` with `view: "evidence"` returns `fields.issuelinks`.
- **An idea for a larger initiative:**
  `project = <ideas board> AND statusCategory != Done AND text ~ "<words that name the feature>"`.

## Writes

Only after the goalie approves the table, and only these. Each one can be undone.

| Change | Call |
|---|---|
| Into a sprint | `transitionJiraIssue` with `{"issueIdOrKey": "<key>", "sprintId": <id>}` |
| Out of the sprint, to the backlog | `transitionJiraIssue` with `{"issueIdOrKey": "<key>", "assignToBacklog": true, "boardId": <board>}` |
| Set the parent epic | `editJiraIssue` with `{"fields": {"parent": {"key": "<epic>"}}}` |
| Clear the parent epic | `editJiraIssue` with `{"fields": {"parent": null}}` |
| Add customer codes | `editJiraIssue` with `{"fields": {"<customer field id>": [{"id": "<code id>"}, …]}}`, listing the codes already there too |
| Link a bug to an idea | `createJiraIssueLink` with `{"linkType": "<bug to idea link type>", "inwardIssue": "<bug>", "outwardIssue": "<idea>"}`, then read the bug's links back and check that the bug shows the outward description |
| Labels or priority of a Jira-only bug | `editJiraIssue` with `{"fields": {"labels": [<all labels>]}}` or `{"fields": {"priority": {"name": "<name>"}}}` |
| Jira-only issue in the security epic | `createJiraIssue` with the main repository's Jira project, the bug issue type, a summary that names the GHSA id, and the security epic as parent |
| Comment | `addOrEditJiraIssueComment` with `{"issueIdOrKey": "<key>", "commentBody": "<opening words> …"}` |

- Never call `manageJiraSprint`, and never change a status.
- Clear a parent only when it is a release bug epic, never a topic epic or the security epic. Read
  the bug back after clearing it. When the parent is still set, stop and report it; do not try
  another way.
