---
name: speckit-opsmill-retrospect
description: Run a session retrospective that surfaces context-management gaps and
  routes them to approved follow-up actions.
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: github-spec-kit
  source: opsmill:commands/retrospect.md
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). Treat it as optional scope guidance, such as a focus area, a pasted transcript summary, or a preferred disposition.

## Outline

Run a retrospective on the current agent session while the work is still fresh in context. The goal is to identify concrete improvements to the repository's context-management surface area: `AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`, `.agents/skills/`, `.agents/commands/`, `.specify/templates/`, `dev/knowledge/`, `dev/guides/`, `dev/guidelines/`, `dev/adr/`, and product or architecture decisions that caused avoidable friction.

This command closes the loop from "the agent struggled with X" to "X is captured as an approved repo improvement, dedicated PR, GitHub issue, or local-only note."

## Operating Constraints

- Stay read-only until the user approves the report and any disposition buckets. Do not edit files, commit, push, or create GitHub issues before approval.
- Present the full retrospective before taking action. Ask for explicit approval per disposition bucket: `fix-now`, `open-pr`, `github-issue`, and `local-only`.
- For `fix-now`, present a diff preview or precise patch plan before writing files. Apply only the approved changes.
- For `github-issue`, defer to the existing `creating-issues` skill when available; if it is unavailable, use `gh issue create` only after the user approves the exact issue content.
- Respect `AGENTS.md` guardrails. Ask First topics, including database migrations, GraphQL schema changes, new dependencies, CI/CD workflow changes, and authentication or authorization changes, are never auto-applied. Route them to `open-pr` or `github-issue`.
- Never edit generated files. If a finding points at generated output, identify the source template or generator instead.
- Do not treat personal preferences as repo policy. Use `local-only` for non-project-specific workflow preferences.

## Phase 1: Resolve Session Context

1. Identify the repository root and current branch:
   - Run `git rev-parse --show-toplevel`.
   - Run `git branch --show-current`.
   - Run `git status --short` to understand whether there are existing edits.
2. Determine whether the session is inside an active spec-kit feature:
   - Try `.specify/scripts/bash/check-prerequisites.sh --json --paths-only`.
   - If it succeeds, record `FEATURE_DIR` and use `FEATURE_DIR/retrospective.md` as the report path.
   - If it fails or the project is not on a spec-kit feature branch, continue as an ad-hoc session and use `.claude/retrospectives/YYYYMMDD-HHMMSS-<short-branch-or-session-slug>.md` as the report path.
3. Load only the context needed to classify findings:
   - Root `AGENTS.md` and any area-specific `AGENTS.md` touched this session.
   - `CLAUDE.md` and `.claude/settings.json` if present.
   - Relevant skill prompts in `.agents/skills/` and commands in `.agents/commands/`.
   - Relevant spec-kit templates in `.specify/templates/`.
   - Relevant `dev/knowledge/`, `dev/guides/`, `dev/guidelines/`, or `dev/adr/` pages.
   - Current diff and recent commands from the conversation context.

## Phase 2: Identify Findings

Review the current conversation and repository context for friction that was avoidable through better shared context. Organize findings into exactly these categories:

1. **Instructions / Configuration Gaps**
   - Missing, unclear, duplicated, or contradictory guidance in `AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`, skill prompts, commands, or spec-kit templates.
   - Required repo workflows that the agent had to infer or rediscover.
2. **Documentation Gaps**
   - Missing or stale content in `dev/knowledge/`, `dev/guides/`, `dev/guidelines/`, or `dev/adr/`.
   - Docs that contradicted current code or left out required verification steps.
3. **Architectural Friction**
   - Product, architecture, or code choices that forced repeated workarounds.
   - Candidates for ADRs, refactors, or product follow-up.
4. **Mistakes & Corrections**
   - Wrong turns taken during the session.
   - The guardrail, instruction, template change, or test that would have prevented the mistake.

Prefer concrete findings over broad observations. Each finding must cite the session event or repository location that motivated it.

## Phase 3: Assign Dispositions

For each finding, propose one disposition:

| Disposition | Use When | Action After Approval |
|-------------|----------|-----------------------|
| `fix-now` | Small, low-risk repo context updates that belong on the current branch and do not touch Ask First topics. | Show diff preview, then edit files only after approval. |
| `open-pr` | Context or harness changes that should be reviewed separately from the current feature branch, or anything touching Ask First topics. | Draft a branch/PR plan. Do not branch, commit, push, or open a PR unless explicitly approved. |
| `github-issue` | Larger work, ambiguous ownership, product/architecture debt, ADR candidates needing human authorship, or work outside current scope. | Use the `creating-issues` skill to draft each issue; create only after approval. |
| `local-only` | Personal workflow preferences or notes that should not become repo policy. | Record only in approved local .specify/memory/report locations supported by the runtime. |

Disposition rules:

- If a finding involves database schema or migration changes, GraphQL schema changes, new dependencies, CI/CD workflows, authentication, authorization, or generated files, do not assign `fix-now`.
- If a finding needs product or architecture ownership, prefer `github-issue` unless the user explicitly asks for a dedicated PR.
- If a finding is already fully covered by existing docs or instructions, do not include it as a finding; mention it only in a brief "No action" note if helpful.

## Phase 4: Produce Review Report

Before writing any files, present the retrospective in chat using this structure:

```markdown
## Session Retrospective

**Scope**: <current feature, branch, or ad-hoc session>
**Proposed report path**: <path>

### Findings

| ID | Category | Evidence | Improvement | Disposition |
|----|----------|----------|-------------|-------------|
| R1 | Instructions / Configuration Gaps | <specific session event or file path> | <concrete change> | fix-now |

### Disposition Buckets

#### fix-now

- R1: <target file and change summary>

#### open-pr

- R2: <branch or PR scope>

#### github-issue

- R3: <issue title>

#### local-only

- R4: <memory/report note>

### Approval Request

Reply with one or more approved buckets, for example:

- `approve report only`
- `approve fix-now`
- `approve github-issue R3`
- `approve all except open-pr`
```

The report must include concrete findings in all four categories. If a category genuinely has no findings, include the category with `None found` and a one-sentence reason.

## Phase 5: Save Report

Save the retrospective report only after the user approves `report only`, a disposition bucket, or `all`.

Report path:

- Active spec-kit feature: `specs/<current-feature>/retrospective.md`.
- Ad-hoc session: `.claude/retrospectives/YYYYMMDD-HHMMSS-<short-branch-or-session-slug>.md`.

If the report path already exists, append a numeric suffix rather than overwriting it.

## Phase 6: Execute Approved Dispositions

Process only the buckets the user approved.

### fix-now

1. Show a diff preview or exact patch plan for the approved findings.
2. Wait for confirmation if the preview changes the original scope.
3. Apply edits with normal repository editing rules.
4. Run relevant validation. For prompt, command, and Markdown-only changes, at minimum verify paths exist and the command can be discovered from the extension manifest and runtime command file. Run broader lint or tests when touched files are covered by existing automation.

### open-pr

1. Draft the proposed branch name, PR title, PR body summary, and changed file list.
2. Ask for explicit approval before creating a branch, committing, pushing, or opening a PR.
3. If approved, use the repository's normal PR workflow.

### github-issue

1. For each approved finding, invoke the `creating-issues` skill with the finding as source material.
2. Present the exact issue title/body/labels for approval.
3. Create issues only after approval.

### local-only

1. Record the note only in runtime-supported local memory or in the approved retrospective report.
2. Do not add local-only preferences to repo files unless the user explicitly reclassifies them as repo policy.

## Completion

After approved actions are complete, provide a brief summary:

- Report path
- Actions taken
- Validation run
- Any remaining unapproved buckets