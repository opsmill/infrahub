---
name: pr
description: >-
  Opens a pull request, publishing the current branch as a PR. TRIGGER when: the user wants to
  open a pull request, publish the current branch as a PR, or take the current work through to an
  open PR. DO NOT TRIGGER when: only committing changes → commit; babysitting CI after the PR is
  already open → monitoring-pull-requests.
argument-hint: Optional `commit` to stage, commit, and push uncommitted changes before opening the PR
compatibility: Requires a Git working tree and GitHub access (gh CLI authenticated, GitHub MCP server, or equivalent). Works best alongside the `commit` and `monitoring-pull-requests` skills from this plugin.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Open Pull Request

## Introduction

Handle the full workflow from current branch state to an open, CI-monitored pull request. This skill enforces branch discipline, analyzes all branch changes for a business-value-focused description, ensures documentation is current, and requires user approval at every step.

It is project-agnostic: base branch, validation commands, documentation layout, and labels are all discovered from the repository itself rather than assumed.

## Arguments

<arguments> $ARGUMENTS </arguments>

**Supported arguments:**

- `commit` — Stage, commit, and push uncommitted changes before proceeding. **Without this argument, no commits are made** — the skill works only with what is already committed on the branch.

## Main Tasks

### 1. Safety Checks & Branch State

First, verify the agent is on a safe branch and understand the current git state. Branch creation and commit logic are owned by the `commit` skill — this phase only inspects state and decides what to do next.

1. Run `git status` to see uncommitted/staged/untracked files.
2. Run `git branch --show-current` to identify the current branch.
3. Determine the base branch the PR should target:
   - Prefer the repository's default branch: `git symbolic-ref --short refs/remotes/origin/HEAD` (the name after `origin/`).
   - If the current branch was clearly forked from a different long-lived branch (e.g. a release branch), use that instead.
   - When ambiguous, ask the user.
4. **If on an unsafe branch** — the default branch, a long-standing integration branch, a release branch, or a placeholder/scratch branch (the `commit` skill's step 2 holds the canonical rules; don't re-derive the list here):
   - **If `commit` was passed:** proceed to Phase 2; the `commit` skill will refuse the unsafe branch, propose a properly named feature branch, and ask the user for approval before creating it. Do not pre-create the branch here — let the `commit` skill own that conversation so the rules stay in one place.
   - **If `commit` was NOT passed:** STOP. There's no feature branch to open a PR from. Tell the user they need to either invoke `/pr commit` (so the `commit` skill creates a branch and captures the changes), or switch to a feature branch first.
5. If already on a feature branch, continue to the next phase.

### 2. Commit Changes (only when `commit` argument is provided)

**Skip this phase entirely if `commit` was NOT passed as an argument.** If there are uncommitted changes and `commit` was not provided, warn the user that uncommitted changes exist but will not be included in the PR.

When `commit` IS provided, run any project-specific prep first, then delegate the actual commit + push to the `commit` skill so branch discipline, secret hygiene, and message conventions stay in one place:

1. If the project defines fast validation commands (formatters, linters), run them first. Discover them from the project's own context — `AGENTS.md`/`CLAUDE.md`/`CONTRIBUTING.md`, a `Makefile`/`Taskfile`/`justfile`, `package.json` scripts, `pyproject.toml`/`tox.ini`, or a `prek.toml` config. If the project defines none, skip this step.

2. If the project checks in generated artefacts (GraphQL schemas, OpenAPI clients, generated SDK types, protobufs) and their sources were modified, regenerate them using the project's documented commands and include the regenerated files — CI commonly fails on stale generated artefacts.

3. Invoke the `commit` skill with the `push` argument: `/commit push`. The skill will:
   - Refuse to commit on protected or placeholder branches and, if needed, propose a conventional feature branch name (`feat/…`, `fix/…`, etc.) for user approval before creating it.
   - Stage changes safely (explicit paths, secret-pattern warnings).
   - Draft a conventional-commit message and confirm it with the user.
   - Run prek hooks (no `--no-verify`); fix violations and create a new commit on hook failure.
   - Push the branch upstream (`git push -u origin <branch>` on first push).

   Do not duplicate any of that logic inline here. If the user has additional commit-message guidance specific to this PR (e.g., spec or issue reference, conventional-commit scope), pass it along when invoking the skill.

4. After `/commit push` returns, confirm the working tree is clean and the branch is published before continuing to Phase 3.

### 3. Analyze All Branch Changes

Understand the FULL scope of changes in this branch — not just the latest commit, but everything since it diverged from the base branch. If there's a related spec or issue, use it to understand the business context.

1. Use the base branch determined in Phase 1 (referred to as `<base>` below).
2. View all commits in the branch:

   ```bash
   git log origin/<base>..HEAD --oneline
   ```

3. View the full diff of all changes:

   ```bash
   git diff origin/<base>...HEAD --stat
   git diff origin/<base>...HEAD
   ```

4. **Check for related planning context.** If the repository keeps specs, PRDs, or ADRs (e.g. a `specs/` directory, `docs/adr/`, or locations referenced from `AGENTS.md`/`CONTEXT.md`), look for one matching this branch — by branch name, by files touched, or by a linked issue. When one exists, read it to understand user scenarios, requirements, and success criteria; it is the primary source for framing the PR's business value. If the repo keeps no such context, skip this step.
5. Categorize changes by area (e.g. application code, tests, documentation, CI/CD, configuration) using the repository's own layout.

### 4. Documentation Review

Before opening the PR, ensure that the project's documentation reflects the changes being introduced. Stale docs are worse than no docs.

1. **Discover where this project keeps developer documentation.** Probe in this order, and use what actually exists:
   - Locations referenced from `AGENTS.md`/`CLAUDE.md`/`CONTEXT.md`/`CONTRIBUTING.md` (these often map code areas to docs).
   - Conventional directories: `dev/`, `docs/`, `doc/`, ADR directories (`docs/adr/`, `dev/adr/`).
   - The `README.md` for user-facing behaviour changes.

   If the project keeps no developer documentation, note that and skip to Phase 5 — do not invent a documentation structure.

2. Based on the changes identified in Phase 3, check the docs covering the touched areas:
   - Read each relevant doc and compare against the actual changes.
   - If a doc is outdated or missing coverage of new functionality, propose updates.
   - Present proposed doc changes to the user for approval.
3. Commit any approved doc updates to the branch (with a `docs:` conventional commit, following the repo's commit style).
4. Push if new commits were added.

### 5. Draft PR Description

Focus on business value — what problem does this solve, what capability does it add? The reviewer should understand WHY before they look at HOW. Reference the spec or issue if one exists.

**PR Title:** Short, conventional format (under 70 chars), mirroring the repo's existing PR/commit style. Examples:

- `feat: add environment backup and restore operations`
- `fix: resolve config drift during reconciliation`
- `refactor: migrate inline queries to dedicated files`

**PR Body Template** (adapt to the repository's PR template in `.github/PULL_REQUEST_TEMPLATE.md` if one exists — the repo template wins):

```markdown
## Summary
[1-3 sentences: what business problem this solves or what capability it adds.
Frame as outcomes for users/operators, not as code changes.]

## Key Changes
[Bulleted list of the most important changes, framed as outcomes:
- "Operators can now back up and restore environments" NOT "Added backup_service.py"
- "Queries are validated against the schema in CI" NOT "Moved queries to .graphql files"]

## Related Context
[If tied to a spec, PRD, ADR, or issue: link it and highlight the key
requirements addressed. Omit this section if none exists.]

## Documentation Updates
[List any docs that were added or updated as part of this PR.
Omit this section if no docs were changed.]

## Test Plan
[How to verify — test commands to run, manual verification steps, or CI checks to watch]
```

**No session-link footer — strip it if the harness added one.** Some harnesses append a trailer pointing at the private agent session after your body, typically a bare `https://claude.ai/code/session_…` URL (or a link wrapping one). Never include it: that URL is internal and usually unshareable, it lands in the project's permanent — often public — PR history, and it references session state no reviewer can open. If the harness inserts such a line, remove it before creating the PR, and never author one yourself. This mirrors the `commit` skill's step 4 rule for commit messages; legitimate attribution (e.g. a `Co-Authored-By` trailer or a generic "Generated with" credit) is unaffected.

**Labels:** Discover the repository's labels with `gh label list` and pick the ones that fit the change. Don't invent labels; if none fit, omit them.

### 6. User Validation & PR Creation

**IMPORTANT: Always present the full PR draft to the user for review BEFORE creating it.** Never create a PR without explicit user approval.

1. Present to the user:
   - PR title
   - PR body (rendered)
   - Target base branch
   - Labels
2. Wait for the user's explicit approval or requested changes.
3. After approval, create the PR using the GitHub interface available to the agent. First strip any harness-appended session-link footer from the body (see step 5). Examples:

   ```bash
   gh pr create --title "[TITLE]" --body "[BODY]" --base <base> --label "[LABELS]"
   ```

   Or, when using the GitHub MCP server, the equivalent `create_pull_request` call.
4. Return the PR URL to the user.

### 7. Hand Off to `monitoring-pull-requests` as a Background Agent

Don't just open the PR and walk away — but don't re-implement the CI babysitting loop here either, and don't sit blocked in the foreground waiting 30+ minutes for CI to finish. The `monitoring-pull-requests` skill owns the CI workflow (poll, classify, reproduce narrowly, fix, retry up to 5 times, revert on exhaustion), and CI watching is the textbook "long-running, independent of what the user does next" background task. Spawn it as a background agent so the parent conversation can return control to the user immediately.

1. Confirm the PR was created and you have the PR number / URL / branch name.
2. **Spawn `monitoring-pull-requests` as a background agent.** Use the runtime's agent-launching mechanism (Claude Code: the `Agent` tool with `run_in_background: true`; other runtimes: equivalent background-task primitive). The agent must run with a clean context — give it everything it needs in the prompt rather than relying on parent-conversation state.

   Recommended invocation (Claude Code, general-purpose subagent):

   ```text
   Agent(
     description: "Monitor PR #<N> CI",
     subagent_type: "general-purpose",
     run_in_background: true,
     prompt: "Invoke the monitoring-pull-requests skill and run its workflow against
              PR #<N> on branch <branch>. The PR was just opened by
              the /pr skill at commit <sha>; pass that commit as the
              expected baseline — monitoring-pull-requests re-captures and verifies
              the baseline_commit itself in its Phase 0. Follow every
              phase of the skill verbatim, including the narrow-
              reproduction-first discipline and the 5-iteration cap.
              Produce the skill's final report when you finish."
   )
   ```

   Adjust the prompt to match your runtime's agent contract, but always (a) name the `monitoring-pull-requests` skill as the source of truth, (b) pass the PR number, branch, and baseline commit, and (c) require the skill's final report on completion.

3. **Tell the user what just happened**, then return control:
   - PR URL.
   - That `monitoring-pull-requests` is now running in the background.
   - That CI feedback / fix attempts / a final report will arrive asynchronously when the agent completes.

   Do not poll or re-summarize CI here. The agent's final report is the closing status; surface it to the user when it lands.

If the runtime cannot spawn background agents, fall back to invoking `/monitoring-pull-requests <pr-number>` synchronously, or — as a last resort — poll `gh run list --branch <branch-name>` every 30–60 seconds and follow the same narrow-reproduction-first discipline `monitoring-pull-requests` enforces. Do not push speculative fixes when local reproduction is possible.

## Notes

**Branch Safety:**

- This skill will NEVER commit to the default branch, a long-standing integration branch, or a release branch — the canonical rules live in the `commit` skill's step 2.
- If uncommitted changes exist and `commit` was not passed, warn but do not commit.

**Business Value Focus:**

- PR descriptions should answer "why does this matter?" before "what changed?".
- When a spec, PRD, or issue exists, it is the primary framing device — reference user scenarios and success criteria.
- Technical implementation details belong in the diff, not the PR description.

**Documentation Discipline:**

- Stale docs are worse than no docs — always check before opening a PR.
- New features or changed behavior should be reflected wherever the project keeps its developer documentation.
- If the project keeps no developer documentation, don't invent a structure — note it and move on.

## Expected Outcome

A pull request that:

- Lives on a properly named feature branch (never a protected or long-lived branch).
- Has a business-value-focused description referencing specs or issues when available.
- Includes up-to-date documentation where the project keeps any.
- Has been reviewed and approved by the user before creation.
- Has been handed off to a backgrounded `monitoring-pull-requests` agent, which owns post-creation CI watching and fix-on-failure asynchronously.
