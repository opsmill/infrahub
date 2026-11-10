# Phase 5: Report

If files were set aside in Phase 0, restore them first with `git stash apply <sha>`, then drop
that entry (`git stash list --format='%gd %H'` gives its reference).

Leave out empty sections. Each finding line has the form
``- <check>: `file:line`: <finding> (<source path:line>; P1/P2/P3)``, where `<check>` is Bugs,
Approach, Rules, Design, Cleanup, Architecture or Claims.

```markdown
## Review: <branch or pull request URL> (base: <base>, from <argument | pull request | closest of stable/develop>)

Mode: <branch | PR mode>; scope: <committed only | committed and uncommitted>; left out: <globs | nothing>; set aside: <paths | nothing>
Requirement from: <spec path | ticket or issue link | pull request description | the user | no requirement found>
Context hooks: <active | inactive>
Skill files read: <each file of references/ read>
Context read: <each rule, AGENTS.md and article, with the reviewer that read it>; not read: <paths | none>
P1: <n> | P2: <n> | P3: <n>; fixed: <n>, declined: <n>, deferred: <n>, asked: <n>, rounds: <n>
Ask First changes: <schema or migration, GraphQL schema, dependency, CI workflow, authentication | none>
Fixes outside the manifest: <paths, each with its approved Ask | none>

### Questions for you
- <finding line>; the fix would contradict <requirement: quote | commit sha: subject>, or <the decision and its missing reason>

### Fixed
- <finding line>

### Declined (paste into the pull request description)
- <finding line>: <reason>

### Deferred
- <finding line>, or the corrected sentence for the pull request description

### Pre-existing
- <finding line>

### Records to update
- <Jira ticket | pull request description | changelog fragment | spec file> <link or path>: "<old sentence>" becomes "<new sentence>"

### Decisions
| Decision | `file:line` | Alternative the codebase uses | Reason written in |
|---|---|---|---|

### Advisory (P3)
- <finding line>

More small findings: <the P3 findings past the first five, in one line>

### Out of scope
- <finding line>

### Rejected by you
- <finding line>: <reason given>

### Proposed improvements
- Rules and index: `<target path>`: <change> (<what shows the need>; <new | proposed in n runs | rejected on <date>, new reason>)
- Articles: `<path:line>`: "<old sentence>" becomes "<new sentence>" (shown by `file:line`)
- This skill: `<file>`, <step>: <change> (<what happened in this run>)
```

Save the report to `$(git rev-parse --git-common-dir)/reviewing-code/<branch>.md`, replacing any
earlier one; in PR mode, `<branch>` is the pull request's `headRefName`. It is inside `.git`, so
it is never committed and every worktree reads it. In PR mode, then remove the temporary
worktree: `git worktree remove --force <scratchpad>/pr-<n>`.

Then follow "After the report" in `references/improve.md`.
