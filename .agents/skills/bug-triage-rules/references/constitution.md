# The triage constitution

The triage constitution is `.agents/bug-triage-constitution.md` at the root of the main repository.
The setting-up-bug-triage skill writes it, and every bug triage skill reads it on every run.

The skills look values up by heading and field name, so keep both exactly as in the template.

- In the template, words in angle brackets describe the value to write. A filled file holds none of
  them, except the variables of a pattern: `<major>`, `<minor>`, `<patch>`, and `<release>`, which
  stands for `<major>.<minor>`, such as `1.12`.
- A field with nothing to name says `none`.
- A URL is written as `<https://…>`.

## Template

```markdown
# Bug triage constitution

The bug triage skills read this file on every run. Edit it by hand when a detail changes.

## Repositories

- Main repository: <owner>/<name>
- Related repositories: <owner>/<name>, <owner>/<name> | none

### <owner>/<name>

- Jira project: <key>
- Bug label: <label>
- Feature label: <label>
- Duplicate label: <label> | none
- Type label prefix: <prefix>
- Priority labels: <label for 1>, <label for 2>, <label for 3>, <label for 4>
- Labels removed before a close: <label>, <label> | none
- Routing labels: none | <prefixes>, chosen by the rules in <path>, from the labels described in <path>
- Issue types: <type for a bug>, <type for a feature request> | none
- Title prefixes: <prefix for a bug>, <prefix for a feature request> | none
- GA release tag: <pattern with <major>.<minor>.<patch>>
- Release branch: <pattern with <major>.<minor>> | none
- Integration branches: <branch>, <branch>

## Jira

- Site: <site URL>, cloudId <id>
- Board: <id>
- GitHub URL field: <field id>
- Sprint field: <field id>
- Customer field: <field name> (<field id>)
- Fields copied from GitHub: <field>, <field> | none
- Draft status: <status name> | none
- Not-planned statuses: <status name>, <status name> | none
- Bug issue type: <name> (<id>)
- Jira-only priorities: <Jira priority> is <1 to 4>, one entry for every Jira priority
- Default priority: <Jira priority that a new issue gets>
- Release bug epic: the epic whose summary is "<text with <release>>"
- Next patch release: <where a bug for the next patch release goes>
- Security epic: <key> | none
- Ideas board: <project key>, Roadmap field <field id>, Product stage field <field id>
- Ideas before building: `<stage, written exactly as the field option>`, `<stage>`
- Bug to idea link: <link type name>, the bug <outward description> the idea

## Slack

- Escalation channel: #<name> (<channel id>)
- Customer channel prefixes: <prefix> for customers, <prefix> for prospects
- Customer channel exceptions: #<name>, #<name> | none
- Never-read prefixes: <prefix>, <prefix>
- Channels left out of link searches: #<name>, #<name> | none
- SA and FAE titles: <title>, <title>
- Link lookback: <days> days

## Priority rules

- Priority page: <page URL>, section "<heading>"
- Bug or feature page: <page URL> | none

## Releases

- Current release: <rule>
- Release cut: <rule>
- Previous minor release day: <rule>
- Current release branches: before the cut, <branch>, <branch>; after the cut, <branch>, <branch>
- Release status meetings: <Notion data source or page> | none
```

## The fields, and how to check them

The setup skill checks every field of an existing constitution with the read in the last column.
"Goalie confirms" marks a value that no read can prove: show it to the goalie and ask.

| Field | What it is | How to check it |
|---|---|---|
| Main repository | The repository whose releases the bugs are scheduled into | `gh api repos/<repo>` answers, and it is the checkout's `origin` |
| Related repositories | Repositories whose bugs the goalie also owns; every run looks at them too | `gh api repos/<repo>` answers for each |
| Jira project | The Jira project that holds the copies of the repository's issues | The GitHub URL field finds the copy of a recent issue in this project |
| Bug, feature and duplicate labels, priority labels | The labels with those meanings | Each is in `gh api --paginate repos/<repo>/labels` |
| Type label prefix | An open issue with no label that starts with it has no type yet | Labels with the prefix exist |
| Labels removed before a close | Labels that make the Jira sync reopen a closed issue when they are still on it | Each label exists; goalie confirms the list |
| Routing labels | The label prefixes, the rules file for choosing them and the file that describes each label | Labels with each prefix exist, and both files are on the default branch |
| Issue types | The GitHub issue types for a bug and a feature request | `gh api orgs/<org>/issue-types` lists them, and the repository's issues use them |
| Title prefixes | The prefixes that start the title of a bug and of a feature request. A bug that turns out to be a feature request gets the second instead of the first | The repository's issue templates use them |
| GA release tag | The tag pattern of a general availability release; a tag with a pre-release suffix (`a1`, `b0`, `rc1`) is not GA | The highest GA release matches the pattern |
| Release branch | The branch created when a release is cut | At least one branch matches the pattern |
| Integration branches | The branches a fix is merged into, the default branch first. A fix is merged when one of them contains it | Each branch exists, or the pattern matches one |
| Site | The Jira site and its cloudId | The Atlassian connector lists the site with this cloudId |
| Board | The board that holds the sprints | `listJiraBoardSprints` finds an active sprint; report when its end date has passed |
| GitHub URL, sprint and customer fields | The field ids | `getJiraIssueTypeMetaWithFields` lists each on the bug issue type of every Jira project, and the GitHub URL field finds a copy by exact match |
| Fields copied from GitHub | Fields the sync overwrites from the GitHub issue; the skills never edit them on a Jira copy | Goalie confirms |
| Draft status | The status of an issue nobody has triaged yet | A new Jira copy has this status |
| Not-planned statuses | Statuses a person sets to say a bug is not planned for a release; scheduling-bugs counts them as a decision | Each is a status of the bug issue type; goalie confirms |
| Bug issue type | The bug issue type and its id | The bug issue type of every Jira project has this id |
| Jira-only priorities | How each Jira priority maps to priority 1 to 4, for a bug with no GitHub copy | Every priority of the site has an entry; goalie confirms the mapping |
| Default priority | The priority Jira gives a new issue. A Jira-only bug with no `Bug triage` comment that still has it counts as having no priority | New Jira-only bugs have it |
| Release bug epic | The epic that lists the bugs planned for one release | The pattern finds the epic of the current release |
| Next patch release | Where scheduling-bugs puts a priority 2 bug when the current release is already cut | Goalie confirms |
| Security epic | The epic that holds the Jira-only issues of bugs tied to a security advisory. With `none`, triaging-new-bugs still flags those bugs and says the epic is missing | The epic exists and is not done |
| Ideas board and its fields | The ideas project, and its Roadmap and Product stage fields | The fields are on the idea issue type, and the Roadmap field finds ideas for the current release |
| Ideas before building | The Product stage values of an idea that is not being built yet | Each is an option of the Product stage field |
| Bug to idea link | The Jira link that ties a bug to the idea of a larger initiative | `listJiraIssueLinkTypes` has the type with this outward description |
| Escalation channel | The channel where bugs are escalated | The channel exists with this id |
| Customer channel prefixes | A channel named with one of them belongs to one customer or prospect, named by the rest of the channel name | Channels with each prefix exist |
| Customer channel exceptions | Channels with a customer prefix that belong to no customer | Each exists |
| Never-read prefixes | Channels shared with people outside the company. The skills never read them | Goalie confirms that every shared channel starts with one |
| Channels left out of link searches | Channels whose posts fill the link searches without adding a report, such as a Jira notification channel | Each exists |
| SA and FAE titles | A Slack profile title that contains one of them, ignoring case, marks a solutions architect or a field engineer | At least one profile has each |
| Link lookback | How far back the Slack link search goes | A number of days |
| Priority page | The page and section that hold the priority criteria | The page opens, the section holds the criteria, and the page is not archived or below a page marked outdated |
| Bug or feature page | The page that says what counts as a bug or a feature request | It opens and says so |
| Current release, Release cut, Previous minor release day | Rules a run applies without asking, such as "the minor version after the highest GA release tag of the main repository" | Apply each rule and show today's answer |
| Current release branches | The branches the current release ships from, before and after its cut; a fix whose pull request targets one of them reaches the current release | Each branch exists, or the pattern matches one; goalie confirms |
| Release status meetings | Where the release status meeting notes are | The source holds recent meetings |
