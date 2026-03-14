---
description: Audit documentation completeness for a feature branch, subject, or set of existing docs
argument-hint: <commit-range, branch name, subject, or doc paths to audit>
---

# Documentation Audit

Audit documentation completeness after a feature branch. Scan commits, cross-reference against all documentation layers, and report gaps.

## Step 1: Gather Scope

The user may provide one of the following as an argument:

- A **commit range or branch name** — audit all changes in that range.
- A **subject** (e.g., "webhooks", "computed attributes", "IPAM") — audit documentation for that topic across the codebase, regardless of branch. Search `dev/knowledge/`, `docs/docs/`, `dev/specs/`, `backend/AGENTS.md`, `frontend/app/AGENTS.md`, and the code itself to assess coverage.
- A **set of doc paths** (e.g., `docs/docs/guides/installation.mdx dev/knowledge/backend/templates.md`) — audit only those specific documents. Read each file, identify what feature/topic it covers, then assess completeness, accuracy, and cross-references. Also check whether the code it documents has drifted from what the doc describes.

If no argument is provided, ask:

1. **What to audit**: A commit range, branch name, subject, or list of doc paths? (default: current branch vs `stable`)

For commit-based audits, run `git log <range> --oneline --stat` to understand all changes.
For subject-based audits, use Grep/Glob to find all code and docs related to the subject.
For doc-path audits, read each provided file, extract its topic/feature scope, then search the codebase for the corresponding implementation to verify the docs are current and complete.

## Step 2: Map Changes to Documentation Layers

For each changed area identified in the commits, check all 5 documentation layers:

| Layer | Location | Question |
|-------|----------|----------|
| Technical reference | `dev/knowledge/backend/` or `dev/knowledge/frontend/` | Does the knowledge doc explain how this works? |
| User-facing docs | `docs/docs/topics/` or `docs/docs/guides/` | Can users understand and use this feature? |
| Feature spec | `dev/specs/` | Is there a spec, and does it match what was built? |
| Changelog | `changelog/` | Is there a changelog fragment for user-visible changes? |
| Cross-references | All docs | Do related docs link back in both directions? |

Also check these secondary locations when relevant:

- `dev/knowledge/backend/architecture.md` — Component map if new directories were created.
- `dev/knowledge/backend/testing.md` — If new test patterns were introduced.
- `dev/knowledge/backend/schema-definitions.md` — If new schema types were added.
- `backend/AGENTS.md` or `frontend/app/AGENTS.md` — If new top-level modules were created.

## Step 3: Generate Audit Report

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

## Step 4: Apply Fixes

Ask the user which fixes to apply:

1. **Apply all** — Edit or create all proposed documentation.
2. **Cherry-pick** — Let the user select which changes to apply.
3. **None** — Keep the report as reference only.

For approved fixes:

- Prefer editing existing files over creating new ones.
- Check cross-references in both directions (A links to B and B links to A).
- Run `uv run invoke docs.lint` to perform global Markdown/MDX linting across the repo.
