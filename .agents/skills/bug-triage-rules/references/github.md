# GitHub recipes

Every call a run makes here is REST on an endpoint under `repos/<owner>/<repo>/`, so it works both
on the goalie's machine and in a cloud session, which refuses GraphQL, the search endpoints and the
other endpoints. The session's GitHub tools, when it has them, make the same REST calls and can
replace `gh api`.

`<repo>` is `<owner>/<name>` from the constitution. Labels and branches come from the constitution's
repository section.

## Contents

- [Lists](#lists)
- [One issue](#one-issue)
- [Fixes and releases](#fixes-and-releases)
- [Security advisories](#security-advisories)
- [Writes](#writes)

## Lists

The issues endpoint also returns pull requests: drop every entry that has a `pull_request` key.

- **Open bugs:**

  ```bash
  gh api --paginate 'repos/<repo>/issues?state=open&labels=<bug label>&per_page=100' \
    --jq '.[] | select(.pull_request | not) | {number, title, created_at, updated_at,
          labels: [.labels[].name], type: .type.name, author: .user.login,
          association: .author_association}'
  ```

- **Open bugs with no priority:** the same list, keeping the entries that carry none of the
  priority labels.
- **Open issues with no type:** the same call without `labels=`, keeping the entries that carry no
  label starting with the type label prefix.
- **Events since the previous working day**, for reopens and for priority labels added: the
  repository's issue events, newest first. Stop paging once the events are older than the date.

  ```bash
  gh api 'repos/<repo>/issues/events?per_page=100&page=<n>' \
    --jq '.[] | select(.event == "reopened" or .event == "labeled")
          | {event, label: .label.name, number: .issue.number, created_at}'
  ```

- **Closed bugs updated since a date:**
  `repos/<repo>/issues?state=closed&labels=<bug label>&since=<ISO date>&per_page=100`.
- **Pull requests merged since a date:**
  `gh api 'repos/<repo>/pulls?state=closed&sort=updated&direction=desc&per_page=100&page=<n>' --jq '.[] | {number, title, body, head: .head.ref, base: .base.ref, updated_at, merged_at, merge_commit_sha}'`.
  Keep the entries with `merged_at`, and stop paging at the first entry updated before the date.
  Use it to find a fix that names an issue or a Jira key in its title, body or branch name.

## One issue

- **The issue:** `gh api repos/<repo>/issues/<number>`. The `type` field is the issue type, `null`
  when none is set.
- **Comments:** `gh api --paginate repos/<repo>/issues/<number>/comments --jq '.[] | {user: .user.login, created_at, body}'`.
- **Timeline**, for reopens, closes, and the pull requests and issues that mention the issue:

  ```bash
  gh api --paginate repos/<repo>/issues/<number>/timeline \
    --jq '.[] | {event, created_at, actor: .actor.login,
                 source: .source.issue.html_url, is_pr: (.source.issue.pull_request != null)}'
  ```

- **Reporter inside or outside the organization:** the issue's `author_association`. `OWNER` and
  `MEMBER` are inside. Any other value is outside.
- **Reporter's name**, to find the person in Slack: `gh api users/<login> --jq .name`. Cloud
  sessions refuse this endpoint; search Slack by the login there.

## Fixes and releases

- **A pull request:**
  `gh api repos/<repo>/pulls/<number> --jq '{state, draft, merged_at, merge_commit_sha, base: .base.ref, head: .head.ref, head_sha: .head.sha}'`.
- **Is a fix merged:** a fix is merged when one of the constitution's integration branches contains
  its commit. `gh api repos/<repo>/compare/<branch>...<commit> --jq .status` answers `behind` or
  `identical` when the branch contains the commit, and `ahead` or `diverged` when it does not.
- **GA releases:** read the tags, because the releases list can leave a release out:
  `gh api --paginate 'repos/<repo>/git/matching-refs/tags/<tag prefix>' --jq '.[].ref'`, where the
  tag prefix is the GA release tag pattern up to `<major>`. Keep the tags that match the pattern,
  and compare versions as numbers, not by date: a patch of an older minor can be published after a
  newer minor. The day a release came out: `gh api repos/<repo>/releases/tags/<tag> --jq .published_at`,
  or the date of the tag's commit when the release has no page.
- **Does a release contain a fix:** the same compare call with the tag in place of the branch.
- **The first release that contains a fix:** check the GA tags in version order, starting with the
  first one published after the fix was merged. A merged fix that no GA tag contains is not
  released yet.
- **Backports:** a fix can reach a release through another pull request with another commit, such as
  a backport. Check the pull requests that mention the fix pull request in its timeline, and test
  their merge commits too.
- **A fix that waits only for a review or a merge:** an open pull request that is not a draft, has
  no review whose latest state is `CHANGES_REQUESTED`, and whose checks pass:
  - reviews: `gh api repos/<repo>/pulls/<number>/reviews --jq '.[] | {user: .user.login, state, submitted_at}'`
  - checks: `gh api repos/<repo>/commits/<head sha>/check-runs --jq '[.check_runs[] | .conclusion] | unique'`
- **An earlier report of the same bug:** read the new report and its timeline for a link to the
  earlier report first. Without one, list the closed bugs updated since the previous minor release
  day, and compare what goes wrong.
- **Release branch exists:** `gh api repos/<repo>/branches/<branch> --jq .name` answers with the
  name, or with HTTP 404 when the branch does not exist.
- **Write access:** `gh api repos/<repo> --jq .permissions`. `push` or `triage` must be `true` to
  label, comment and close.

## Security advisories

```bash
gh api 'repos/<repo>/security-advisories?state=draft&per_page=100' \
  --jq '.[] | select(.severity == "high" or .severity == "critical") | {ghsa_id, severity, summary}'
```

Run it again with `state=triage`. Reading advisories needs the security manager role. When the call
answers 403 or 404, report that the advisories could not be read, rather than reporting none. A
draft or triage advisory is confidential: name it only by its GHSA id and summary, and only in the
chat and in Jira.

## Writes

Only after the goalie approves the table, and only these:

| Change | Call |
|---|---|
| Labels, issue type and title | one call per issue, described below |
| Comment | write the text to a file, then `gh api -X POST repos/<repo>/issues/<number>/comments -F body=@<file>` |
| Close | `gh api -X PATCH repos/<repo>/issues/<number> -f state=closed -f state_reason=<reason>` |

**Labels, issue type and title:** send all of an issue's changes to these in one call, never one
label at a time. Between two calls, the sync between GitHub and Jira can copy the half-changed
labels to Jira and back, which puts a removed label back on the issue.

1. From the issue as read just before the write, build its full new label list: the labels it has,
   plus the labels to add, minus the labels to remove.
2. Write a JSON file with `labels` set to that list, and `type` and `title` only when they change:

   ```json
   {"labels": ["<bug label>", "<routing label>", "<priority label>"], "type": "<issue type>"}
   ```

3. Send it: `gh api -X PATCH repos/<repo>/issues/<number> --input <file>`.

The call replaces the whole label list, so a label someone adds between the read and the write is
lost: read the issue right before the call. When GitHub refuses the call because of `type`, send it
again without `type`, and list the issue in the report for the goalie to set the type by hand.

- **Close reasons:** `completed` for a bug fixed in a release, `duplicate` for a duplicate. When
  `duplicate` is refused, use `not_planned`. Add the duplicate label when the constitution names
  one, and name the other issue in the comment either way.
- **Before a close:** leave the constitution's labels removed before a close out of the label list,
  and send that call before the comment and the close.
- **Issue type:** at the read-back the approval guard describes, when the type did not change, list
  the issue in the report for the goalie to set by hand.
