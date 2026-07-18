---
name: creating-prd
description: >-
  Synthesises the current conversation context into a Product Requirements Document and publishes
  it to GitHub (as a comment on a referenced issue, or a new issue). Synthesises from context;
  does not interview. TRIGGER when: the conversation has produced enough understanding of a
  feature and the user wants it captured as a PRD. DO NOT TRIGGER when: a single small issue is
  enough → creating-issues; the idea has not been stress-tested yet → grilling-ideas first; bug
  reports.
argument-hint: Optional — extra instructions, scope hints, or an explicit issue number/URL to target
compatibility: Requires GitHub access (gh CLI authenticated, or an equivalent GitHub MCP/API tool) and write access to the target repository. Reads project context (AGENTS.md, CONTEXT.md, dev/constitution.md, ADRs, specs) when present and falls back gracefully when absent.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Create PRD

## User Input

```text
$ARGUMENTS
```

Treat `$ARGUMENTS` as optional scope hints or an explicit issue target. The PRD's content comes from the conversation context, not from arguments.

## What this does

Take the current conversation context plus codebase understanding and produce a **Product Requirements Document**. Publish it to GitHub:

- If an issue was referenced at the start of the conversation → post the PRD as a **comment** on that issue.
- If no issue was referenced → create a **new issue** with the PRD as the body.

Always show the draft to the user and wait for explicit approval before publishing.

**Do NOT interview the user.** This skill synthesises what you already know. If the context is too thin to write a PRD, say so and recommend `/grilling-ideas` first.

## When to use

- The conversation has produced enough understanding to articulate a feature, and the user now wants it captured as a PRD on GitHub.
- The user explicitly asks for a PRD, a spec writeup, or an issue body.
- A previous `/grilling-ideas` session produced a sharpened idea brief and the user wants it turned into a PRD on the tracker.

Do **not** use this skill for:

- Bug reports → use `/creating-issues` or the bug-pipeline skills.
- Capturing an idea you have *not* yet stress-tested — run `/grilling-ideas` first.
- Writing the actual implementation spec — that is a downstream spec workflow's job (e.g. `/speckit-specify`). The PRD produced here is the **input** to that step.

## Phase 0 — Discover available context (read what exists, skip what doesn't)

Before drafting, probe the repository for project-level context. Read whichever are present. **None of them are required** — the skill must work in a repo that has none of them. Skip a probe only if the answer is already in the conversation.

| Source | If present, use it for |
| --- | --- |
| `AGENTS.md` / `CLAUDE.md` (root and per-component) | Working agreements, governance gates ("ask first" areas), naming conventions, which components the feature touches. |
| `CONTEXT.md` | Project glossary — canonical names for domain concepts and synonyms to avoid. If present, use this vocabulary in the PRD and never introduce synonyms. |
| `dev/constitution.md` (or `.specify/memory/constitution.md`) | Non-negotiable principles. The PRD must call out which ones the feature touches. |
| `dev/adr/` (or `docs/adr/`) | Prior decisions in the area the feature touches. Honour them; if the feature contradicts one, surface it as an open question rather than overriding silently. |
| `specs/` | In-flight or recent work on the same surface. Cross-reference relevant ones. |
| `.specify/templates/spec-template.md` | The downstream spec template. If present, mirror its section structure so the spec workflow can lift sections wholesale. |
| Existing repo labels (`gh label list --limit 100`) | The labels that actually exist, for triage. Run once. |

Probe with a quick `ls`/`test -f` pass rather than reading the whole tree. Read in full only what genuinely matters for this feature. If none of these exist, fall back to a plain PRD grounded in the conversation and whatever the codebase reveals.

## Phase 1 — Detect the target issue

Before drafting, decide where the PRD will land. Scan the conversation, **starting from the very first user message**, for any of:

1. A full GitHub issue URL — e.g. `https://github.com/<owner>/<repo>/issues/<N>`.
2. A `#<N>` reference followed by language suggesting it is an issue (not a PR).
3. An explicit phrase like "issue 123", "GH-123", or "the linked issue".

Resolve the candidate:

```bash
gh issue view <N> --json number,title,state,url,labels
```

Decision tree:

- **Exactly one candidate, exists, state = OPEN** → that is the target. Post as a comment.
- **Multiple candidates** → list them to the user with title + state and ask which one.
- **Candidate exists but state = CLOSED** → ask the user whether to reopen + comment, or create a new issue instead.
- **No candidate, or candidate does not exist** → target is a **new issue**. Move on to title/label drafting in Phase 5.

Record the decision before drafting; do not switch targets mid-draft.

## Phase 2 — Sketch the modules (deep, testable)

Before writing the PRD, list the modules you expect to build or modify. Actively look for opportunities to extract **deep modules** — units that encapsulate substantial functionality behind a small, stable, testable interface that rarely changes. Shallow modules (one-method wrappers, pass-throughs) are anti-patterns.

For each module note:

- Its layer or component, using the project's own vocabulary (infer it from the context files and codebase — e.g. API/schema, service, repository, frontend component, CLI command, SDK binding, worker). Do not assume a layering the project doesn't use.
- Whether it is **new** or an **extension** of an existing module.
- The one-sentence responsibility.
- Whether it deserves its own unit-test suite, or is covered by an existing one.

Present the module sketch to the user and confirm:

1. Do these modules match your mental model?
2. Which ones do you want unit-tested in their own right? (The rest still go through whatever integration/E2E coverage the project requires.)

Wait for confirmation before drafting the PRD body. This is the only point where input is *always* required from the user (beyond final approval); Phase 1 also asks when the target issue is ambiguous.

## Phase 3 — Draft the PRD

Use the template below. Drop any section that does not apply to this project (e.g. "Constitution Alignment" when there is no constitution document) rather than padding it. Keep the prose tight — a clear three-line section beats a sprawling one.

Apply these rules while drafting:

- **No file paths or code snippets** describing implementation — those rot fast and belong in the planning step. Exception: if a prior prototype produced a tight artefact that encodes a decision more precisely than prose (a state machine, a schema shape, an API fragment, a reducer), inline the decision-rich parts and note that it came from a prototype. Trim hard.
- **Use the project's domain terms.** If `CONTEXT.md` exists, use its canonical names; otherwise infer the vocabulary from the codebase and stick to one term per concept. No "the thing that does X" when the project has a name for it.
- **Make every "MUST" testable.** If a sentence cannot be paired with a single-sentence verification idea, sharpen it.
- **Success Criteria are user-facing and measurable.** No framework names, no millisecond response times — translate to user value ("results in under 1 second", "operator can recover in under 5 minutes").
- **Mirror `.specify/templates/spec-template.md` structure** where it exists, so the downstream spec workflow can lift sections wholesale.

### PRD template

```markdown
# PRD: <short feature name>

## Problem Statement

<The problem the user faces, from the user's perspective. Two to four sentences. No solutions yet.>

## Solution Overview

<The proposed solution, from the user's perspective. What changes for them, in plain language. Not how it is built.>

## User Stories

<A long, numbered list. Format: "As a <role>, I want <capability>, so that <benefit>."
Cover every aspect of the feature including admin / failure / observability paths.
Use the actor vocabulary the project actually uses — infer the relevant roles from the
domain (e.g. developer, operator, admin, end-user) rather than inventing a generic cast.>

1. As a <role>, I want …, so that …
2. As a <role>, I want …, so that …
3. …

## User Journeys (prioritised)

<Each journey must be an independently shippable slice. Mirror the spec template's
priority structure if one exists.>

### P1 — <title>
- Journey: <one sentence end-to-end>
- Acceptance: **Given** <state>, **When** <action>, **Then** <outcome>

### P2 — <title> (optional)
…

### P3 — <title> (optional)
…

## Functional Requirements

- **FR-001**: System MUST …
- **FR-002**: Users MUST be able to …
- **FR-003**: …

## Key Entities

<Map each new or affected concept to an existing project entity, using CONTEXT.md
vocabulary when present. Flag genuinely new entities explicitly.>

- **<Existing entity>**: <how the feature affects it>
- **<NewEntity>** *(new)*: <lifecycle, ownership, relationships> — call out for governance review

## Edge Cases

- <Boundary / failure / concurrency / partial-state scenarios — at least three.>

## Success Criteria

- **SC-001**: <measurable, technology-agnostic outcome>
- **SC-002**: …

## Implementation Decisions

<Module-level decisions, schema shapes, API contracts, interaction patterns. NO file paths,
NO code unless a prototype encodes a decision more precisely than prose can. If inlining,
trim to the decision-rich parts only. Include only the sub-bullets relevant to this project's
architecture — drop the ones that don't apply.>

- Modules to build / modify (from Phase 2 sketch):
  - `<Module name>` (`<layer/component>`, new|extends): <one-sentence responsibility>
  - …
- API / interface surface: <new endpoints, fields, arguments, commands, or "none">
- Error handling: <new error types / codes the feature introduces, or "none">
- Data / persistence: <schema or migration changes, or "none">
- Frontend surface: <new routes, operations, or UI components, or "none">
- SDK / CLI surface: <new methods or commands, or "none">

## Testing Decisions

- **What makes a good test here.** <Test external behaviour, not implementation details. One or two sentences scoping the principle for this feature.>
- **Unit tests** (per Phase 2, agreed with user): <list of modules>
- **Integration / contract tests**: <list, or "N/A" — include any project-specific gate, e.g. API-to-DB propagation tests, only if the project requires it>
- **E2E scenario**: <one-sentence description of the user-visible flow that will be exercised end-to-end>
- **Prior art**: <links / paths to existing similar tests in the codebase, if any>

## Constitution Alignment

<Include this section only if the project has a constitution (dev/constitution.md or
.specify/memory/constitution.md). Walk the principles the feature touches and state how it
fits or where it pushes back. Drop the section entirely if there is no constitution.>

- **<Principle>**: <how this fits / where it pushes back>
- …

## Governance Gates Crossed

<Tick every gate this PRD crosses. If AGENTS.md names its own "ask first" list, use that list
instead of the generic one below. A ticked box requires explicit discussion before implementation.>

- [ ] Database schema or migration change
- [ ] API / public interface change
- [ ] New dependency
- [ ] CI/CD workflow change
- [ ] Authentication / authorization change

## Assumptions

- <Assumption about users, environment, data, or existing systems>
- …

## Out of Scope

- <Explicit non-goals for v1 — carve aggressively>
- …

## Open Questions

- [NEEDS CLARIFICATION: …]

<Cap at three. If more remain, the PRD is not ready — recommend /grilling-ideas before publishing.>

## Further Notes

- Related specs: <`specs/NNN-…` cross-references, if any>
- Related ADRs: <`dev/adr/…` cross-references, if any>
- Source of this PRD: <conversation summary in one or two sentences>
```

## Phase 4 — Show the draft and get approval

**Never publish without explicit user approval.** Present the full draft inline, then ask:

- Does the module sketch still match? (If they changed their mind, loop back to Phase 2.)
- Is anything missing, wrong, or scope-creeping?
- Approve to publish?

If the draft has more than three `[NEEDS CLARIFICATION]` markers, do not offer to publish — recommend `/grilling-ideas` to resolve them first.

## Phase 5 — Publish

Write the approved draft to a temporary file (e.g. `$(mktemp -t prd-draft.XXXXXX.md)`) and publish from there.

### Path A — Comment on the referenced issue

```bash
gh issue comment <N> --body-file <draft-path>
```

After posting, fetch the comment URL and report it. If the issue does not already carry an appropriate triage label, suggest one to the user but do **not** apply it automatically — commenting on someone else's issue should not re-triage it.

### Path B — Create a new issue

Pick the title and labels from project conventions surfaced earlier.

- **Title**: conventional-commit-style prefix when the project uses it (`feat:`, `chore:`, `docs:` …). Keep under 70 characters.
- **Labels**: choose only from labels that exist (`gh label list`). Typical candidates: a type label (`enhancement` / `feature`), a scope/component label, and a triage label if the project has a "ready-for-agent" or equivalent. Confirm — do not invent labels.

```bash
gh issue create \
  --title "<title>" \
  --body-file <draft-path> \
  --label "<label1>" --label "<label2>"
```

Report the new issue URL.

## Phase 6 — Hand off to the spec step

After publishing, tell the user what to run next:

- If the project has a spec workflow (e.g. `.specify/` is set up) → suggest feeding the PRD into it: `/speckit-specify "$(gh issue view <N> --json body -q .body)"`, or paste the PRD body manually if the runtime cannot interpolate.
- Otherwise → suggest whichever the user prefers: starting a plan, breaking the PRD into issues, or implementing directly.

The PRD's structure (User Journeys, FRs, Key Entities, Edge Cases, Success Criteria, Assumptions) maps directly onto a typical spec template, so the spec step should produce a strong first draft with minimal `[NEEDS CLARIFICATION]` markers.

## Anti-patterns

- **Do not interview.** Synthesise from context. If you cannot, stop and recommend `/grilling-ideas`.
- **Do not invent labels.** `gh label list` first.
- **Do not auto-re-triage someone else's issue.** Commenting must not silently change labels or state.
- **Do not embed file paths or code snippets** in Implementation Decisions, except the prototype-snippet exception. Those rot. Save them for the planning step.
- **Do not write the spec.** This skill produces a PRD; the spec is the downstream workflow's output.
- **Do not assume a project frame that isn't there.** No constitution → drop Constitution Alignment. No `CONTEXT.md` → infer vocabulary from the codebase. No GraphQL/driver/etc. → don't mention them. Skip gates the project doesn't have.
- **Do not publish without user approval.** Even if you have permissions.

## Expected outcome

A PRD published to GitHub at a known URL (comment on the referenced issue, or a new issue), with:

- All applicable template sections completed and inapplicable ones dropped.
- Domain vocabulary consistent with `CONTEXT.md` (when present).
- Constitution alignment explicit (when the project has a constitution).
- Governance Gates marked, using the project's own list when it defines one.
- ≤ 3 `[NEEDS CLARIFICATION]` markers.
- A named E2E / acceptance scenario.
- A clear next step pointing to the project's spec or planning workflow.

---

*Inspired by [`to-prd`](https://github.com/mattpocock/skills/blob/main/skills/engineering/to-prd/SKILL.md) by Matt Pocock. Adapted from a Styrmin-specific skill into a project-agnostic one for the opsmill-dev plugin; pairs with `/grilling-ideas`.*
