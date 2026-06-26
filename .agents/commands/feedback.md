---
description: Analyze this conversation and identify missing or incorrect documentation to improve future sessions
---

# Session Feedback

Analyze this conversation and identify what documentation or context was missing, incomplete, or incorrect. The goal is to continuously improve the project's knowledge base so future conversations are more efficient.

## Step 1: Session Analysis

Reflect on the work done in this conversation. For each area, identify friction points:

1. **Exploration overhead**: What parts of the codebase did you have to discover by searching that should have been documented? (e.g., patterns, conventions, module responsibilities)
2. **Wrong assumptions**: Did you make incorrect assumptions due to missing or misleading documentation?
3. **Repeated patterns**: Did you discover recurring patterns or conventions that aren't documented anywhere?
4. **Missing context**: What background knowledge would have helped you start faster? (e.g., architecture decisions, data flow, naming conventions)
5. **Tooling gaps**: Were there commands, scripts, or workflows that you had to figure out?

## Step 2: Documentation Audit

For each friction point identified, determine the appropriate fix. Check the existing documentation to avoid duplicating what's already there:

- `AGENTS.md` — Top-level project instructions and component map
- `CLAUDE.md` — Entry point referencing AGENTS.md
- `backend/AGENTS.md` — Backend component map and conventions
- `frontend/app/AGENTS.md` — Frontend component map and conventions
- `docs/AGENTS.md` — Documentation site guide
- `dev/knowledge/backend/` — Backend architecture knowledge base
- `dev/knowledge/frontend/` — Frontend architecture knowledge base
- `dev/guidelines/` — Coding standards and workflow guidelines
- `dev/adr/` — Architecture Decision Records
- `dev/commands/` — Claude Code slash commands
- `dev/guides/` — How-to guides
- `dev/specs/` — Feature specifications

Read the relevant existing files to understand what's already documented before proposing changes.

## Step 3: Generate Report

Present the feedback as a structured report with the following sections. Only include sections that have content — skip empty sections.

### Format

```markdown
## Session Feedback Report

### What I Was Working On
<!-- Brief summary of the task(s) performed in this conversation -->

### Documentation Gaps
<!-- Things that should be documented but aren't -->

For each gap:

- **Topic**: What's missing
- **Where**: Which file should contain this (existing file to update, or new file to create)
- **Why**: How this would have helped during this conversation
- **Suggested content**: A draft of what should be added (be specific and actionable)

### Documentation Corrections
<!-- Things that are documented but wrong or misleading -->

For each correction:

- **File**: Path to the file
- **Issue**: What's wrong or misleading
- **Fix**: What it should say instead

### Discovered Patterns
<!-- Conventions or patterns found in the code that aren't documented -->

For each pattern:

- **Pattern**: Description of the convention
- **Evidence**: Where in the code this pattern is used (file paths)
- **Where to document**: Which AGENTS.md, knowledge doc, or guideline file should capture this

### Memory Updates
<!-- Propose additions/changes to MEMORY.md for cross-session persistence -->

For each update:

- **Action**: Add / Update / Remove
- **Content**: What to write
- **Reason**: Why this is worth remembering across sessions
```

## Step 4: Apply Changes

After presenting the report, ask the user which changes they want to apply. Present the options:

1. **Apply all** — Create/update all proposed documentation files and memory
2. **Cherry-pick** — Let the user select which changes to apply
3. **None** — Just keep the report as reference, don't modify any files

For approved changes:

- Edit existing files when updating documentation
- Create new files only when no appropriate existing file exists
- Update `MEMORY.md` with approved memory changes
- Keep all changes minimal and focused — don't over-document
