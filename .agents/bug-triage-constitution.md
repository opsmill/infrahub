# Bug triage constitution

The bug triage skills read this file on every run. Edit it by hand when a detail changes.

## Repositories

- Main repository: opsmill/infrahub
- Related repositories: opsmill/infrahub-sdk-python

### opsmill/infrahub

- Jira project: IFC
- Bug label: type/bug
- Feature label: type/feature
- Duplicate label: type/duplicate
- Type label prefix: type/
- Priority labels: priority/1, priority/2, priority/3, priority/4
- Labels removed before a close: state/need-more-info, state/need-triage
- Routing labels: group/, category/, chosen by the rules in .github/workflows/shared/issue-taxonomy.md, from the labels described in .github/labels.yml
- Issue types: Bug, Feature
- Title prefixes: bug:, feature:
- GA release tag: infrahub-v<major>.<minor>.<patch>
- Release branch: release-<major>.<minor>
- Integration branches: stable, develop, release-<major>.<minor>

### opsmill/infrahub-sdk-python

- Jira project: IHS
- Bug label: type/bug
- Feature label: type/feature
- Duplicate label: type/duplicate
- Type label prefix: type/
- Priority labels: priority/1, priority/2, priority/3, priority/4
- Labels removed before a close: state/need-more-info, state/need-triage
- Routing labels: none
- Issue types: Bug, Feature
- Title prefixes: bug:, feature:
- GA release tag: v<major>.<minor>.<patch>
- Release branch: none
- Integration branches: stable, develop, infrahub-develop

## Jira

- Site: <https://opsmill.atlassian.net>, cloudId 2fc122cd-1b87-4eb7-8f51-482827e5d17b
- Board: 12
- GitHub URL field: customfield_10063
- Sprint field: customfield_10020
- Customer field: Customer(s) (customfield_10815)
- Fields copied from GitHub: labels, priority, assignee, description, fix version
- Draft status: Draft
- Not-planned statuses: Move to Roadmap
- Bug issue type: Bug (10012)
- Jira-only priorities: Highest is 1, High is 2, Medium is 3, Low is 4, Lowest is 4
- Default priority: Medium
- Release bug epic: the epic whose summary is "Targeted bugs within the <release> release cycle"
- Next patch release: the active sprint and the current release's bug epic; the scheduling comment says the bug is a first candidate for the next patch release
- Security epic: none
- Ideas board: INFP, Roadmap field customfield_10075, Product stage field customfield_10252
- Ideas before building: `1 'Shaping'`, `2 'Discovery'`, `3 'Release Planning'`, `4 'Solutioning'`
- Bug to idea link: Polaris work item link, the bug implements the idea

## Slack

- Escalation channel: #eng-bugs (C0BTB5U90S1)
- Customer channel prefixes: cust- for customers, prosp- for prospects
- Customer channel exceptions: #cust-general-all, #cust-test
- Never-read prefixes: ext-
- Channels left out of link searches: #eng-jira-update
- SA and FAE titles: Solution Architect, Solutions Architect, FDE, FAE, Field Automation Engineer
- Link lookback: 21 days

## Priority rules

- Priority page: <https://app.notion.com/p/770228b8302583f2a554819f1860f68a>, section "Priority"
- Bug or feature page: <https://app.notion.com/p/a50228b8302583f69a8401963bba2d95>

## Releases

- Current release: the minor version after the highest GA release tag of the main repository
- Release cut: the release branch of the current release exists in the main repository
- Previous minor release day: the day the GA release <major>.<minor>.0 before the current release was published
- Current release branches: before the cut, develop, stable; after the cut, release-<major>.<minor>, stable
- Release status meetings: Notion data source collection://b8b55472-9212-4b1f-a7ed-e25900465ee1
