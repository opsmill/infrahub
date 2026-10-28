# Phase 8 — Report

If files were set aside, restore them first: `git stash apply <sha>`, then drop that entry
(`git stash list --format='%gd %H'` gives its reference).

```markdown
## Pre-push review — <branch> (base: <base>, from <argument | PR | closest of stable/develop>)

Scope: <committed only | committed and uncommitted>; left out: <globs or "nothing">; set aside: <paths or "nothing">
Context hooks: <active | inactive: paths passed explicitly>
Skill files read: <each file of references/ read during this run>
P1: <n> | P2: <n> | P3: <n> — fixed: <n>, declined: <n>, deferred: <n>, asked: <n>, rounds: <n>
Fixes outside the manifest: <paths, each with the approved Ask | "none">
cubic: <exit code, n findings | error: <message> | not installed>

### Context
| File | Kind | Why it applies | Read by |
|---|---|---|---|
| <path> | Rule / AGENTS.md / Guideline / Article opened | <glob match, or the question> | <reviewer, or "not read"> |

### Fixed
- `file:line` — <finding> (<source path:line, or the failure>)

### Declined — paste into the PR description
- `file:line` — "<finding>": <reason>

### Deferred
- `file:line` — <finding>, or the corrected PR-description sentence

### Questions for you
- `file:line` — <finding>; the fix would contradict <requirement ID: quote | commit sha: subject>

### Records to update
- <Jira ticket | PR description | changelog fragment | spec file>: <link or path> — "<old sentence>" → "<new sentence>" (fix: `file:line`)

### Challenge
Requirement from: <spec path | ticket or issue link | PR description | the user>
- <Requirement | Simpler version | Unrequested scope | Rejection>: `file:line` — <finding> (P1/P2; fixed | declined | deferred | asked)

### Architecture and decisions
- <Layer | ADR | Ask First | Reversal | Failure | Scale>: `file:line` — <finding> (`<doc path:line>`; P1/P2/P3/Ask; fixed | declined | deferred | asked)

| Decision | `file:line` | Alternative the codebase uses | Reason written in |
|---|---|---|---|
| <dependency, contract, data model, where the work runs, state, pattern> | <path:line> | <path:line, or "none"> | <spec, plan, ADR, PR description, commit, or "nowhere"> |

### Design
- <Queries | Request context | Entity dependencies | Position | Copied files | States | Volume | Reuse | Simplicity>: `file:line` — <finding> (P2/P3; fixed | declined | deferred | asked)

### Per file
- `file:line` — <need | simpler way | naming | comment | test cannot fail | duplicate test>: <one line>

### Advisory (P3)
- `file:line` — <one line>

### Out of scope (excluded paths)
- `file:line` — <finding> (<source>) — not counted above

### Rejected by you
- `file:line` — <finding> (<source>): <reason given>

### Proposed improvements
Rules and index:
- `<target path>` — <change in one line> (<the finding or file that shows the need>; <new | proposed in n runs | rejected on <date>: new reason>)

Knowledge and guideline articles:
- `<article path:line>` — "<old sentence>" → "<new sentence>" (shown by `file:line`)

This skill:
- `<SKILL.md | references/<file>>`, <step> — <change in one line> (<what happened in this run>)
```

Save the report to `$(git rev-parse --git-common-dir)/reviewing-changes/<branch>.md`, replacing
any earlier one. Inside `.git` it is never committed and every worktree of the repository can
read it.

Then follow "After the report" in `references/improve.md`: ask which proposals to apply, and log
the decisions.
