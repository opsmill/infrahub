---
name: reviewing-changes
description: >-
  Reviews a branch against the project's own written conventions before it is pushed - the path-scoped rules, the knowledge and guideline articles a scoping subagent selects from the diff, and the claims made outside the code (specs, changelog, PR description). Discovers where those live in the current repository rather than assuming a layout, grades findings P1-P3, and cites a rule or article for each. TRIGGER when: the user wants their branch reviewed against the project's conventions before opening a PR, wants to know whether a change respects the documented architecture, or wants to catch the rule violations that review bots raise after a push. DO NOT TRIGGER when: responding to review threads already on a PR → `opsmill-dev-addressing-review`; mining review threads into durable docs → `harvesting-review`; auditing documentation coverage for a feature → `audit-docs`; a general correctness or bug hunt with no rule angle → the `/code-review` command.
argument-hint: <PR number (#1234), branch name, or empty for the current branch; add `bugs` for a correctness pass>
compatibility: Any repository checked out with `origin` fetched. Works best where conventions live in an agent doc layer (`.agents/rules/`, `dev/knowledge/`, `dev/guidelines/`); degrades explicitly when they do not. PR-number scope requires the `gh` CLI authenticated.
metadata:
  version: 0.3.0
  author: OpsMill
---

# Review Changes Against the Project's Conventions

## User Input

```text
$ARGUMENTS
```

## What this does

A project's conventions live in two shapes a reviewer has to reach on purpose: path-scoped rules
(terse always/never, keyed by file path) and knowledge or guideline articles (how the system works and
how to write for it, keyed by concept). Neither reaches a reviewer working from a diff. Path-scoped
rules only inject when a matching file is opened with the Read tool, so a `git diff` review runs with
no rules loaded at all, and nothing selects articles for a change.

This skill discovers where those live in the current repository, loads the rules mechanically by path,
has a scoping subagent select articles from the diff, reviews with all of it in context, and then
checks the claims the diff cannot show. Every finding cites the rule or article it violates.

Nothing here is specific to one repository. Project specificity comes only from the files discovered
in §3 and loaded in §4 and §5.

## Scope

The default pass answers **"does this change obey what this project has written down?"** A logic bug
with no rule behind it is out of scope by default, because most projects already run a general
reviewer in CI.

Pass `bugs` in the arguments to add a correctness pass. Use it when no other reviewer runs before the
push - a local review that skips bugs is the only review some changes get.

A finding without a citation is not a finding, except in the `bugs` pass, where the evidence is the
failure it causes. See §8.

## Workflow

### 1. Resolve the change set

Resolve `$ARGUMENTS` to a base branch and a list of changed files.

- **A PR number** (`#1234` or `1234`) - `gh pr view <n> --json baseRefName,headRefName`; use
  `baseRefName` as the base.
- **A branch name** - resolve its open PR the same way.
- **Empty** - the current branch's PR (`gh pr view --json baseRefName -q .baseRefName`).

With no PR to resolve, fall back in this order and **name the fallback you used in the report**:
the upstream tracking branch (`git rev-parse --abbrev-ref @{u}`), then `develop` if it exists on
`origin`, then the repository default from `origin/HEAD`.

Do not take the default branch from `origin/HEAD` without checking. Repositories that release from a
separate branch point `origin/HEAD` at the release branch while features are cut from a development
branch, and diffing against the wrong one pulls in hundreds of unrelated commits.

```bash
git fetch origin <base>
git diff --name-only origin/<base>...HEAD
git status --porcelain          # uncommitted work, include it
```

**Review every changed file, not just the source.** Specs, task lists, e2e tests, changelog fragments
and documentation are where a large share of review comments land, and they are exactly what a
source-only reviewer never sees. Exclude only submodule pointer bumps (gitlinks), noting that those
are reviewed in their own repository. If the change set is empty, say so and stop.

### 2. Deterministic pre-pass on added comments

Run this before any subagent. It is free, it is exact, and it catches the single largest category of
repeat review comments: documentation style in added comments. An agent is not needed to find a ticket
ID in a comment.

```bash
git diff -U0 origin/<base>...HEAD -- '*.py' '*.ts' '*.tsx' | grep -nE '^\+' |
  grep -E '^[0-9]+:\+[[:space:]]*(#|//|\*|"""|'"'''"')' > /tmp/added-comments.txt
```

Over those added comment lines, flag:

| Pattern | Why |
|---|---|
| `[A-Z]{2,}-[0-9]+`, `#[0-9]{4,}`, `\bT[0-9]{3}\b`, `issues/[0-9]+` | Work-item and spec IDs belong in the commit and PR, not the source |
| `used to`, `no longer`, `previously`, `was rejected`, `would have`, `once did` | A comment states what the code does now, never its history |
| `Used by`, `Called from`, `See also`, `Mirrors`, a backticked `Class.method` | Naming other code rots silently when it is renamed |
| A comment that restates the line below it | Comment the why, never the what |

Report these as findings in their own right, cited to the project's code and documentation style rule
if one exists. Adapt the patterns to what that rule actually says: read it first, and do not invent
checks the project has not written down.

### 3. Discover the documentation layer

Never assume a layout. Work it out, and report what you found so a wrong discovery is visible rather
than silent.

**a. Read the map.** Read the root `AGENTS.md`, or `CLAUDE.md` if there is no `AGENTS.md`. Follow any
`@file` include one hop. These files conventionally say where the rest of the docs live, and that
statement beats any probe.

**b. Probe for the layer.** Record which of these exist, and skip the ones that do not:

```bash
ls -d .agents/rules .claude/rules .cursor/rules dev/knowledge dev/guidelines dev/guides docs 2>/dev/null
```

`.claude/rules` is often a symlink to `.agents/rules`. Resolve it and count it once.

**c. Find the nearest map per changed file.** A deeper `AGENTS.md` overrides the root one for files
beneath it, so collect them for the changed paths:

```bash
git ls-files '*AGENTS.md'
```

Load the nearest one for each changed area, not only the root.

**d. Degrade explicitly.** If no rules directory and no knowledge or guidelines directory exists,
review against whatever `AGENTS.md` provides, and open the report with a line saying the review ran
without a rule layer. Do not silently produce a thin review that reads like a clean bill of health.

### 4. Load the rules (mechanical, not a judgement call)

Read the frontmatter of every rule file in the discovered rules directory and match its `paths:` globs
against the changed paths:

```bash
head -12 <rules-dir>/*.md
```

Read **in full** every rule with at least one matching glob. This is mechanical: a matching glob means
the rule applies. No shortlisting, no relevance judgement, and no skipping a rule because the diff
"looks unrelated" - that judgement is what the globs exist to remove. A rule file with no `paths:`
frontmatter applies to everything.

Match globs relative to the directory that owns the rules, not the repository root, so a nested doc
layer resolves correctly.

Pass the matched paths explicitly to every subagent and have it Read them itself. Do not rely on
automatic path-scoped injection: it does not fire on Write, it does not fire for files touched through
Bash, and whether it fires inside a subagent is unverified.

### 5. Build the article digest

Knowledge and guideline libraries run to hundreds of kilobytes. Do not read them. Titles, section
headings and breadcrumbs are a small fraction of that and carry nearly all the selection signal,
because articles state headings as claims ("Two things are called 'default branch'", "Storage is per
worker, not shared"):

```bash
grep -rH "^#\{1,2\} \|^> " <knowledge-dir> <guidelines-dir> --include='*.md'
```

Generate it at call time. Never cache it to a file: a stale index silently stops selecting the article
that would have caught the bug.

### 6. Select the articles (scoping subagent)

Spawn **one** subagent - `subagent_type: Explore`, `model: haiku` is enough, and read-only tools mean
it cannot edit while "selecting". Give it the digest, the diff, and the list of rules already matched
in §4. It returns paths and reasons only, never article content, so the library never enters the
reviewing context.

Give it the diff, not just the file list. Concept selection keys off symbols and imports, which is what
maps to articles: a path like `core/branch/tasks.py` says little, while `default_branch` and
`get_staging_branch` say a lot. If the diff exceeds ~1500 lines, pass the file list plus the added and
removed definition lines (`grep -E '^[+-].*(def |class |function |interface )'` over the diff).

Pass this block verbatim as the subagent prompt, with the inputs appended:

```text
You are selecting background reading for a code review. You are not reviewing the code.

Given: a diff, a digest of the project's knowledge and guideline articles (path, title,
section headings), and the list of rules already loaded for this change.

Return three lists and nothing else. Do not summarise the diff. Do not comment on the code.

SELECTED   - articles the reviewer must read in full. For each: path, the heading that
             matched, and the symbol, file or behaviour in the diff that matched it.
REJECTED   - every article you did not select, one clause each on why not.
UNCERTAIN  - articles you cannot judge from headings alone. Open at most 3, then move each
             into SELECTED or REJECTED with the reason.

Select on what the change touches, not on which directory it lives in. A concern often spans
several directories, and the article that owns it will not be named after any of them.

Guidelines usually restate a rule at greater length. Select a guideline only when a loaded rule
cites it and the change touches that area. Loading both copies of the same standard wastes the
reviewer's context.

Prefer 3-6 articles. Selecting everything is the same as selecting nothing.
```

Keep the `REJECTED` list in the final report. It is the audit trail for a missed rule, and over a few
runs it shows which headings are too vague to select on - a docs fix, routed through
`harvesting-review`.

### 7. Review (reviewer subagent)

Spawn with `subagent_type: Explore` so "this skill reports, it does not fix" is enforced rather than
requested. Give it the matched rule paths from §4, the `SELECTED` article paths from §6, the nearest
`AGENTS.md` files from §3c, and the changed file list. Instruct it to:

1. Read the rules and selected articles **in full, before looking at any code**.
2. Read the changed files with the **Read tool**, not `git diff`. A diff hides the surrounding code a
   rule is usually about - where a symbol lives, what a module already imports, how the neighbouring
   test is written - and reading the file is also what triggers path-scoped rule injection.
3. Check each changed file against the loaded rules and articles.
4. Comment only on lines the change touches. A real problem on an untouched line is pre-existing debt,
   and belongs in an issue rather than this review.
5. Cite, for every finding, the `file:line` of the rule or article it violates plus the `file:line` in
   the change, and grade it per §8.
6. Not fix anything.

With `bugs` in the arguments, spawn a second reviewer over the same files for correctness only: logic
errors, unhandled states, concurrency, and data loss. It reports P1 findings with the failure they
cause, and stays off style entirely.

For a change spanning areas with different doc layers (backend and frontend, or a nested layer), spawn
one reviewer per area with only that area's rules and articles, rather than one reviewer holding both.

### 8. Check what the diff cannot show

Source review misses a large share of what reviewers actually comment on. Check, when the change set
contains them:

- **Specs and task lists** - do they describe the code that shipped, or the code that was first
  planned? Signatures, file names and anything deferred are where they drift.
- **Claims** - every statement in the drafted PR description, changelog fragment and documentation must
  match the diff. No "all" where the code covers some, nothing deferred described as done.
- **Changelog** - a user-visible change needs whatever fragment the project's convention requires.
- **Generated artifacts** - if a source of generation changed, its generated outputs must be
  regenerated in the same branch.

### 9. Grade and report

Grade every finding. Blocking findings are the ones the author is expected to fix before pushing;
advisory findings are the author's call. The point of the split is that a local review which produces
thirty equal-weight comments has only moved the problem onto the developer's machine.

| Grade | Meaning | Disposition |
|---|---|---|
| **P1** | A bug, a security issue, or a violation of a rule stated as always/never | Blocking |
| **P2** | A violation of a written rule or documented architecture with no behavioural break | Blocking |
| **P3** | Style or preference within a rule's spirit; the rule does not settle it | Advisory |

```markdown
## Review - <branch or PR> (base: <base>, resolved from <PR | upstream | fallback>)

**P1: <n> | P2: <n> | P3: <n>** - rules cited: <n>, articles read: <n>, files reviewed: <n>

### Discovery
Rules: <dir, n files> | Knowledge: <dir, n> | Guidelines: <dir, n> | Maps: <AGENTS.md files used>
Say plainly if any were absent, and if the review ran degraded.

### Blocking (P1, P2)
For each: grade, the rule or article cited as `file:line`, the offending `file:line`, and the
smallest fix. One finding per line touched.

### Advisory (P3)
One line each. The author decides.

### Claims and artifacts
Findings from §8, graded the same way.

### Context loaded
- Rules (by path match): <files>
- Articles (selected): <file - why>
- Articles (rejected): <count>, notable near-misses only

### Coverage gaps
Changed areas no rule and no article covered, and any article whose headings were too vague to
select on. Feed these to `harvesting-review`.
```

Keep the summary counts line even when everything is clean: it is the measurement, and it is what
tells you over time whether the review is getting cheaper.

Stop after the report. Offer to apply fixes; apply only on approval.

## Limits

- The scoping agent only sees headings. An article headed "Overview" and "Details" will never be
  selected, and the failure is silent unless someone reads the `REJECTED` list. Treat a missed article
  as a headings bug in that article, not a prompt bug here.
- Rule coverage is only as good as the `paths:` globs. A rule with no matching glob for a changed area
  is invisible to this skill.
- Loading a rule is not the same as it being followed. Rules already in context at authoring time are
  still violated, which is why §2 exists and why the review pass matters more than the routing.
- No deduplication against other review tooling. Running this alongside a review bot will repeat
  findings.
