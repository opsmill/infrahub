---
name: creating-issues
description: >-
  Turns a single feature idea, improvement, or bug into ONE well-structured GitHub issue. TRIGGER
  when: the user wants to file/open/create an issue, turn a feature idea or improvement into a
  ticket, or capture something missing or broken as a ticket. DO NOT TRIGGER when: breaking work
  into multiple issues or planning a body of work → a planning skill; writing a full Product
  Requirements Document → creating-prd; the idea is still fuzzy and unhardened → grilling-ideas
  first.
argument-hint: Feature, improvement, or bug to turn into a GitHub issue
compatibility: Requires GitHub access (gh CLI authenticated, or an equivalent GitHub MCP/API tool) and write access to the target repository.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Create GitHub Issue

## User Input

```text
$ARGUMENTS
```

Treat `$ARGUMENTS` as the thing to file. If empty, ask the user what they want to capture before starting.

## What this does

Turn a feature idea, improvement, or bug into a single well-structured GitHub issue that matches the repository's own conventions. Keep it small and centred on **the need** — what is missing or broken, who it affects, and why it matters. **Do not propose a solution and do not write acceptance criteria for features** — leave the "how" to whoever picks the issue up. Always show the draft and get explicit approval before creating anything.

## Core principle

An issue states the need, not the answer. The person (or agent) who implements it decides the approach. For a feature or improvement that means no design, no task breakdown, no acceptance criteria — just a clear problem and its context. For a bug, the "need" is the misbehaviour itself, so reproduction details belong in the issue.

## Workflow

### 1. Learn the repository's conventions

Probe whatever context the repo actually provides — don't assume a fixed layout:

- [ ] Read context docs if present: `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, `README`, or a `dev/` directory.
- [ ] Check for issue templates in `.github/ISSUE_TEMPLATE/` and honour them if they exist.
- [ ] List the repo's labels (`gh label list`) and a few recent issues (`gh issue list`) to match title style, labels, and tone.

If the repo provides an issue template, honour its structure as-is — the fields are there deliberately. The only thing to hold back is *prescribing a solution*: fill the template's sections with the need and context, not with a design.

### 2. Classify

Decide whether this is a **feature / improvement** or a **bug**. When unsure, ask the user.

### 3. Draft (need-focused)

**Feature / improvement** — keep it lean:

```markdown
## Need

[What's missing or could be better, who it affects, and why it matters now.]

## Context

[Only what's needed to understand the need: relevant area of the product, links to related discussion, constraints. No design.]

## References

- Related issue: #[number]
- Documentation / discussion: [url]
```

**Bug** — capture the misbehaviour:

```markdown
## What happens

[Observed behaviour.]

## What should happen

[Expected behaviour.]

## Steps to reproduce

1. ...
2. ...

## Environment

[Version, OS, configuration, or other relevant context.]

## References

- Related issue: #[number]
- Logs / screenshots: [link or `<details>` block]
```

Draft a clear, searchable title using the repo's convention (e.g. `feat:`, `fix:`, or whatever recent issues use), and pick labels from the repo's existing set.

### 4. Get approval, then create

**By default, present the full draft (title, labels, body) to the user and wait for explicit approval before creating the issue** — even when you have permission to create it directly. The gate exists to stop *silent* creation from mere permission; it is not meant to override a direct instruction.

If the user has explicitly told you to file it without review (e.g. "just file it, don't ask"), honour that — but still echo the final title, labels, and body in your reply before (or as) you create it, so there's a record of what went out.

Create the issue with the available tooling, for example:

```bash
gh issue create --title "[TITLE]" --body "[BODY]" --label "[LABELS]"
```

`--label` takes a comma-separated list (`--label 'bug,enhancement'`) — a space-separated value is treated as a single label name.

Or the equivalent GitHub MCP call. Return the issue URL.

## Guardrails

- Prefer clarity over completeness — a short, sharp issue beats a padded one.
- Resist scope creep: one need per issue. If the input contains several, surface that and ask whether to split.
- Don't invent labels, milestones, or assignees that don't exist in the repo.
- Don't smuggle a solution into the "Need" or "Context" — if you catch yourself describing *how*, cut it.
