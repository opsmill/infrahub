---
description: Audit documentation completeness for a feature branch by scanning commits and cross-referencing existing docs
argument-hint: <commit-range or branch name>
---

# Documentation Audit

Audit documentation completeness after a feature branch. Scan commits, cross-reference against all documentation layers, and report gaps.

## Step 1: Gather Scope

If the user provided a commit range or branch name as an argument, use it. Otherwise ask:

1. **Commit range**: What commits should be audited? (default: current branch vs `stable`)

Then run `git log <range> --oneline --stat` to understand all changes.

## Step 2: Map Changes to Documentation Layers

For each changed area identified in the commits, check all 5 documentation layers:

| Layer | Location | Question |
|-------|----------|----------|
| Technical reference | `dev/knowledge/backend/` or `frontend/` | Does the knowledge doc explain how this works? |
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

### Branch / Commit Range
<!-- What was scanned -->

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
- Run `uv run invoke docs.lint` on any modified `.mdx` files.
