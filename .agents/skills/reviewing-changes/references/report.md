# Phase 5: Report

If files were set aside in Phase 0, restore them first: `git stash apply <sha>`, then drop that
entry (`git stash list --format='%gd %H'` gives its reference).

Leave out a section that has no entries.

```markdown
## Review: <branch or pull request URL> (base: <base>, from <argument | pull request | closest of stable/develop>)

Mode: <branch | PR mode>; scope: <committed only | committed and uncommitted>; left out: <globs or "nothing">; set aside: <paths or "nothing">
Requirement from: <spec path | ticket or issue link | pull request description | the user | no requirement found>
Context hooks: <active | inactive: paths passed explicitly>
Skill files read: <each file of references/ read during this run>
P1: <n> | P2: <n> | P3: <n>; fixed: <n>, declined: <n>, deferred: <n>, asked: <n>, rounds: <n>
Ask First changes: <each change an "Ask First" list in an AGENTS.md names: schema or migration, GraphQL schema, dependency, CI workflow, authentication or permissions | "none">
Fixes outside the manifest: <paths, each with the approved Ask | "none">
cubic: <exit code and number of findings | error: <message> | not installed>

### Context
| File | Kind | Why it applies | Read by |
|---|---|---|---|
| <path> | Rule / AGENTS.md / Guideline / Article opened | <glob match, or the question> | <reviewer, or "not read"> |

### Fixed
- `file:line`: <finding> (<source path:line, or the failure>)

### Declined (paste into the pull request description)
- `file:line`: "<finding>": <reason>

### Deferred
- `file:line`: <finding>, or the corrected sentence for the pull request description

### Pre-existing
- `file:line`: <finding on a line the change did not touch> (<source>)

### Questions for you
- `file:line`: <finding>; the fix would contradict <requirement ID: quote | commit sha: subject>, or <the decision and its missing reason>

### Records to update
- <Jira ticket | pull request description | changelog fragment | spec file>: <link or path>: "<old sentence>" becomes "<new sentence>" (fix: `file:line`)

### Approach
- <Requirement | Simpler version | Unrequested scope | Rejection>: `file:line`: <finding> (P1/P2; fixed | declined | deferred | asked)

### Architecture and decisions
- <Layer | ADR | Ask First | Reversal | Failure | Scale>: `file:line`: <finding> (`<doc path:line>`; P1/P2/P3/Ask; fixed | declined | deferred | asked)

| Decision | `file:line` | Alternative the codebase uses | Reason written in |
|---|---|---|---|
| <dependency, contract, data model, where the work runs, state, pattern> | <path:line> | <path:line, or "none"> | <spec, plan, ADR, pull request description, commit, or "nowhere"> |

### Design
- <Queries | Request context | Entity dependencies | Position | Copied files | States | Volume | Reuse | Simplicity>: `file:line`: <finding> (P2/P3; fixed | declined | deferred | asked)

### New files
- `file:line`: <need | simpler way | naming | comment | test cannot fail | duplicate test>: <one line>

### Advisory (P3)
- `file:line`: <one line>

More small findings: <the P3 findings past the first five, in one line>

### Out of scope (excluded paths)
- `file:line`: <finding> (<source>), not counted above

### Rejected by you
- `file:line`: <finding> (<source>): <reason given>

### Proposed improvements
Rules and index:
- `<target path>`: <change in one line> (<the finding or file that shows the need>; <new | proposed in n runs | rejected on <date>, new reason>)

Knowledge and guideline articles:
- `<article path:line>`: "<old sentence>" becomes "<new sentence>" (shown by `file:line`)

This skill:
- `<SKILL.md | references/<file>>`, <step>: <change in one line> (<what happened in this run>)
```

Save the report to `$(git rev-parse --git-common-dir)/reviewing-changes/<branch>.md`, replacing
any earlier one. In PR mode, `<branch>` is the pull request's `headRefName`; once the report is
saved, remove the temporary worktree with `git worktree remove --force <scratchpad>/pr-<n>`. Inside `.git` it is never committed, and every worktree of the repository can
read it.

Then follow "After the report" in `references/improve.md`.
