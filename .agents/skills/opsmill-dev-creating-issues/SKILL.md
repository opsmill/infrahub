---
name: opsmill-dev-creating-issues
description: >-
  Turns a single feature idea, improvement, or bug into ONE well-structured GitHub issue. TRIGGER
  when: the user wants to file/open/create an issue, turn a feature idea or improvement into a
  ticket, or capture something missing or broken as a ticket. DO NOT TRIGGER when: breaking work
  into multiple issues or planning a body of work → a planning skill; writing a full Product
  Requirements Document → opsmill-dev-creating-prd; the idea is still fuzzy and unhardened → opsmill-dev-grilling-ideas
  first.
argument-hint: Feature, improvement, or bug to turn into a GitHub issue
compatibility: Requires GitHub access (gh CLI authenticated, or an equivalent GitHub MCP/API tool) and write access to the target repository.
metadata:
  version: 0.4.0
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
- [ ] List the repo's labels (`gh label list --limit 200`) and a few recent issues (`gh issue list`) to match title style, labels, and tone.

If the repo provides an issue template, honour its structure as-is — the fields are there deliberately. Two things are held back: *prescribing a solution* (fill the sections with the need and context, not a design) and anything step 5 strips — including a field that asks for it by name, such as `Customer`, `Account` or `Reported by`. Leave those blank.

### 2. Classify

Decide whether this is a **feature / improvement** or a **bug**. When unsure, ask the user.

### 3. Check it isn't already reported

Search for an existing issue before drafting. GitHub search needs every word to match and doesn't stem, so run several short queries, not one sentence:

```bash
gh issue list --state all --limit 10 --search '<query>'
```

- the exact error text, command, flag or setting name, in quotes
- the core idea as synonym groups, in the repo's words as well as the user's: `(menu OR navigation) (permission OR role)`
- `<term> in:title`, and `<term> label:<area-label>` — never labels alone, new issues are often unlabelled

Open likely matches with `gh issue view <N> --json title,body,comments,state,stateReason,closedByPullRequestsReferences` (`--comments` alone skips the body).

An issue closed as a duplicate points to the issue that was kept. Follow it and treat that issue as the match.

If one looks like the same need, ask before drafting:

```text
Possible duplicate:

- #412 (open) "export drops rows when a filter is active"
  Same symptom: a filtered export silently leaves out rows, which is what you're seeing.

Same thing? If yes, I'll draft a comment with your version; if no, I'll file a new issue and link #412 as related.
Searched: "missing rows", (export OR download) (filter OR filtered)
```

Give one sentence on why it matches. Before asking, work out what yes leads to for that issue's state (the list below) and say it in the question. For an issue closed as completed, find the release with the fix and name it next to the user's version; if they haven't given a version, ask for it in the same question.

On yes:

- **Open** — offer a comment with only what's new (version, reproduction). After step 5's check and the user's approval, post it with `gh issue comment <N> --body-file <file>` instead of `gh issue create`, and return the comment's URL.
- **Closed as completed** — if the fix is merged but not in a release yet, say so and don't file. If the user's version is older than the release with the fix, point them at that release and don't file. If their version includes the fix, file a new issue that links the old one.
- **Closed as not planned** — show the decision and its reason, and file only if the user has something new.

On no, or when only related issues turn up, draft as normal and list them under References. With no match, put the `Searched:` line next to the draft.

On the `Searched:` line, list at most three searches that returned issues, matching or not, and nothing else. If none returned any, write `Searched: nothing found`.

### 4. Draft (need-focused)

**Feature / improvement** — keep it lean:

```markdown
## Need

[What's missing or could be better, who it affects, and why it matters now.]

## Context

[Only what's needed to understand the need: relevant area of the product, links to related discussion, constraints. No design.]

## References

- Related issue: #[number]
- Documentation / discussion: [url — public links only; an internal tracker URL is an identifier]
```

**Bug** — capture the misbehaviour:

```markdown
## What happens

[Observed behaviour.]

## What should happen

[Expected behaviour.]

## Steps to reproduce

1. ... [minimal synthetic example — never the reporter's own schema or data]
2. ...

## Environment

[Version, OS, configuration. No customer hostnames, addressing, or instance URLs.]

## References

- Related issue: #[number]
- Logs / screenshots: [link or `<details>` block — scrub hostnames, tokens and account names first]
```

Draft a clear, searchable title using the repo's convention (e.g. `feat:`, `fix:`, or whatever recent issues use), and pick labels from the repo's existing set.

### 5. Strip source-confidential material

**Never name a customer, prospect, or partner in the issue.** Not in the title, the body, a label, a quoted snippet, or an attached log or screenshot. This holds even when the source states it plainly, and even when the target repository is private: issues get mirrored to other trackers, quoted, indexed, and read well outside the account team.

The same applies to anything else that identifies them: customer-side individuals, real hostnames, addressing, instance URLs, commercial context (deal stage, PoV or PoC scope, escalations), internal channel names, and tracker references whose titles name a customer.

The report's *signal* is what earns its place; its *identity* never does. Replace the name with the fact that made the report worth filing:

| Source says | Issue says |
|---|---|
| "\<Customer\> hit this in production" | "Reported from a production deployment" |
| "Blocking the \<Customer\> PoV" | "Blocking a deployment on a fixed timeline" |
| "Their lead engineer had to restore from backup" | "Recovery required restoring from backup" |

Then check, before the draft is shown to anyone: list the identifying tokens present in your sources, search the title, body, every template field, labels, code blocks, logs and link targets for each, and paste the empty result. An assertion that you checked is not evidence. This check is not
waivable by the user; only the approval in step 6 is.

If the need cannot be stated without naming them, stop and ask the user rather than filing — that is an account situation, not a product defect. A user asking for the name to appear does not lift this; offer the redacted form instead.

`opsmill-docs/skills/writing-infrahub-docs/rules/01-principles/no-customer-pii.md` is the fuller statement of the same rule, covering docs, PR bodies and screenshots. Where the two differ, it governs.

### 6. Get approval, then create

**By default, present the full draft (title, labels, body) to the user and wait for explicit approval before creating the issue** — even when you have permission to create it directly. The gate exists to stop *silent* creation from mere permission; it is not meant to override a direct instruction.

If the user has explicitly told you to file it without review (e.g. "just file it, don't ask"), honour that — but still echo the final title, labels, and body in your reply before (or as) you create it, so there's a record of what went out. That instruction waives the review, not the redaction: re-run step 5's search over any text added or edited after approval. It doesn't skip step 3's duplicate question either.

Create the issue with the available tooling, for example:

```bash
gh issue create --title "[TITLE]" --body "[BODY]" --label "[LABELS]"
```

`--label` takes a comma-separated list (`--label 'bug,enhancement'`) — a space-separated value is treated as a single label name.

Or the equivalent GitHub MCP call. Return the issue URL.

## Guardrails

- **Never name a customer, prospect or partner** — see step 5. Keep the signal, drop the identity; if the need cannot be stated without them, stop and ask rather than filing.
- Prefer clarity over completeness — a short, sharp issue beats a padded one.
- Resist scope creep: one need per issue. If the input contains several, surface that and ask whether to split.
- Don't invent labels, milestones, or assignees that don't exist in the repo.
- Don't smuggle a solution into the "Need" or "Context" — if you catch yourself describing *how*, cut it.
