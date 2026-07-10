---
name: audit-docs
description: >-
  Audits documentation completeness for a feature branch, subject, or set of existing docs — maps
  changes across Infrahub's documentation layers, reports gaps, and optionally applies the fixes.
  TRIGGER when: the user wants to audit or check documentation coverage, find doc gaps after a
  feature branch, or verify docs are still current for a subject or specific files.
  DO NOT TRIGGER when: authoring new documentation from scratch → use the add-docs flow; only
  linting/formatting Markdown → run `uv run invoke docs.lint`.
argument-hint: <commit-range, branch name, subject, or doc paths to audit>
compatibility: Requires the Infrahub repository checked out. Commit-range and branch audits additionally require Git history.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Documentation Audit

## User Input

```text
$ARGUMENTS
```

## What this does

Audit documentation completeness — after a feature branch, for a subject, or across a set of existing docs. Scan the relevant changes, cross-reference them against every Infrahub documentation layer, and report the gaps. Then, only with the user's approval, apply the fixes. The goal is coverage without over-documentation: a gap is only a gap if a reader is actually left without something they need.

## Workflow

### 1. Gather scope

Treat `$ARGUMENTS` as what to audit. It will be one of:

- A **commit range or branch name** — audit all changes in that range. Run `git log <range> --oneline --stat` to understand every change.
- A **subject** (e.g. "webhooks", "computed attributes", "IPAM") — audit documentation for that topic across the codebase, regardless of branch. Use Grep/Glob to find all related code and docs, then assess coverage against `dev/knowledge/`, `docs/docs/`, `dev/specs/`, `backend/AGENTS.md`, `frontend/app/AGENTS.md`, and the code itself.
- A **set of doc paths** (e.g. `docs/docs/guides/installation.mdx dev/knowledge/backend/templates.md`) — audit only those files. Read each one, identify the feature/topic it covers, then search the codebase for the corresponding implementation to confirm the doc is current and complete, and check whether the code has drifted from what the doc describes.

If `$ARGUMENTS` is empty, ask what to audit — a commit range, branch name, subject, or list of doc paths (default: current branch vs `stable`).

### 2. Map changes to documentation layers

For each changed area, check all five documentation layers:

| Layer | Location | Question |
|-------|----------|----------|
| Technical reference | `dev/knowledge/backend/` or `dev/knowledge/frontend/` | Does the knowledge doc explain how this works? |
| User-facing docs | `docs/docs/topics/` or `docs/docs/guides/` | Can users understand and use this feature? |
| Feature spec | `dev/specs/` | Is there a spec, and does it match what was built? |
| Changelog | `changelog/` | Is there a changelog fragment for user-visible changes? |
| Cross-references | All docs | Do related docs link back in both directions? |

Also check these secondary locations when relevant:

- `dev/knowledge/backend/architecture.md` — component map, if new directories were created.
- `dev/knowledge/backend/testing.md` — if new test patterns were introduced.
- `dev/knowledge/backend/schema-definitions.md` — if new schema types were added.
- `backend/AGENTS.md` or `frontend/app/AGENTS.md` — if new top-level modules were created.

### 3. Generate the audit report

Present findings in this format:

```markdown
## Documentation Audit Report

### Scope
<!-- What was scanned: branch/range, subject, or list of doc files -->

### Changes Summary
<!-- Grouped by area: schema, logic, tests, etc. -->

### Documentation Status

For each document checked:

- **File**: path
- **Status**: Current / Outdated / Missing / N/A
- **Details**: What is good, what is missing

### Gaps Found

For each gap:

- **What is missing**: Description
- **Where**: Which file to update or create
- **Severity**: High / Medium / Low
- **Suggested fix**: Concrete content or edit

### Not Gaps (By Design)

Things that look like gaps but are intentionally absent. This section prevents over-documentation.

Common reasons something is not a gap:

- Feature uses standard mechanisms (GraphQL mutations, UI forms) that do not need a dedicated guide.
- Entity is fully documented within a parent feature's knowledge doc.
- An ADR is unnecessary when the spec already captures design decisions.
```

### 4. Apply fixes

Ask the user which fixes to apply before editing anything:

1. **Apply all** — edit or create all proposed documentation.
2. **Cherry-pick** — let the user select which changes to apply.
3. **None** — keep the report as reference only.

For approved fixes:

- Prefer editing existing files over creating new ones.
- Check cross-references in both directions (A links to B and B links to A).
- Run `uv run invoke docs.lint` to perform global Markdown/MDX linting across the repo.

## Guardrails

- **Never edit docs before the user has approved specific fixes** — the report comes first; writing is a separate, opt-in step (Step 4).
- **Report the "Not Gaps" honestly** — an audit that flags everything as missing is as useless as one that misses real gaps. Justify why intentional absences are fine.
- **Ground every gap in a concrete reader need** — say who is left without what, and point to the exact file to change. No vague "could use more docs".
- **Prefer editing over creating** — a new file is only justified when no existing doc is the right home for the content.
