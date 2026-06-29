---
name: grilling-ideas
description: >-
  Stress-tests a fuzzy or vague feature idea before any PRD, spec, or ticket is written. TRIGGER
  when: the user has a fuzzy feature idea — one or two paragraphs, vague on users / scope /
  success — and wants to harden it, or says "grill / stress-test / pressure-test this idea." DO
  NOT TRIGGER when: the idea is already turned into a spec or PRD; bug fixes or refactors; the
  idea is hardened and you are ready to write the PRD → creating-prd.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Grill Idea

## User Input

```text
$ARGUMENTS
```

Treat `$ARGUMENTS` as the seed idea. If empty, ask the user for it once before starting the interview.

## What this does

Interview the user relentlessly about every aspect of a feature idea until it is sharp enough to hand off to whatever comes next (a PRD, a spec, a speckit run, or a ticket). Walk down each branch of the idea tree, resolving dependencies between decisions one-by-one. For each question, propose your recommended answer first, then wait for feedback before asking the next one. If a question can be answered by reading the codebase or the project's own documentation, do that instead of asking.

The output is a structured **idea brief** that lives in the conversation by default — no files are written. If the user asks for a written artefact, write it to a temporary path under the system temp directory (e.g. `$(mktemp -t idea-brief.XXXXXX.md)`) and report the path. **Do not write to `.specify/idea-brief.md`** — that location is reserved for a speckit-specific workflow and is out of scope for this skill.

## When to use

- The user has an idea expressed in one or two paragraphs and wants a sharper version.
- The idea is fuzzy on scope, users, success, or how it fits the existing system.
- The user explicitly says they want to grill / stress-test / pressure-test an idea before formalising it.

Do **not** use this skill for:

- A bug fix or refactor with no user-visible behaviour change — go straight to a regular PR or the project's bug pipeline.
- An idea the user has already turned into a spec or PRD — the grilling moment has passed; refine the existing artefact instead.

## Discover available context (read what exists, skip what doesn't)

Before the first question, probe the repository for project-level context files. Read whichever are present. **None of them are required** — the skill must work in a repo that has none of them.

| File | If present, use it for |
| --- | --- |
| `AGENTS.md` (or `CLAUDE.md` pointing at it) | Project-wide working agreements, governance gates ("ask first" areas), naming conventions. |
| `CONTEXT.md` | Project glossary — canonical names for domain concepts and synonyms to avoid. If present, prefer the canonical vocabulary in every turn and in the brief. |
| `dev/constitution.md` | Non-negotiable principles. Walked through under lens 7 (Governance gates and project rules). |
| `dev/knowledge/architecture.md` (or similar) | Descriptive system overview — helps you ground "how does this fit today?" questions in real code. |
| `dev/adr/` directory | Prior architectural decisions. Glance at titles; pull a specific ADR only when the idea touches the same area. |
| `specs/` directory | In-flight or shipped specs. Use to spot scope overlap or dependencies. |

Probe with a quick `ls`/`test -f` pass rather than reading the whole tree. Read in full only the files that genuinely matter for this idea.

If none of these exist, you fall back to plain interviewing — the lenses below still apply; you just don't have a project-specific frame to test against.

## How to interview

- **One question at a time.** Do not batch. Wait for an answer before the next question.
- **Lead with your recommendation.** Format each turn as: short context → question → your recommended answer with reasoning → invite confirmation or redirection.
- **Explore before asking.** If anything in the repo (the context files above, the codebase, ADRs, existing specs/issues) can answer the question, read and report rather than asking.
- **Cross-reference with code.** When the user asserts how something works today, verify against the relevant files. Surface contradictions immediately.
- **Sharpen fuzzy terms.** If `CONTEXT.md` exists, pin every domain term the user uses to a canonical entry. If it does not, still push back on synonyms drifting mid-conversation — pick one term and stick to it.
- **Use concrete scenarios.** When relationships are vague, invent a specific example ("imagine a user upgrades v1.2 → v1.3 mid-operation — what should happen?") and force a precise answer.
- **Capture clarifications inline in the conversation.** Update the in-session brief as decisions land. Don't batch at the end.

## Glossary drift (only when `CONTEXT.md` is present)

If `CONTEXT.md` exists, treat it as the project's living glossary and watch for drift during the interview. Surface — and offer to fix — any of:

1. A new domain concept the idea introduces that isn't in `CONTEXT.md` yet.
2. An existing concept used in the codebase but missing from the glossary.
3. A `CONTEXT.md` entry that is wrong, stale, or ambiguous given what the conversation reveals.
4. A new ambiguity between two terms.

For each, ask the user once whether to add/update the entry. **Do not silently edit `CONTEXT.md`** — propose the diff, get a yes, then apply it surgically (`**Term**: definition. _Avoid_: synonyms.`). If `CONTEXT.md` does not exist in the repo, skip this section entirely.

## Grilling lenses

Every idea should be exercised through these lenses, in this order. Skip a lens only if you can justify why it does not apply.

### 1. Users and value

- Who is the primary user? (a developer, an operator, an end-user of a deployed system, an internal stakeholder?)
- What can they not do today, or what is painful?
- What is the smallest observable change that would make them say "this is better"?

### 2. User journeys (P1/P2/P3)

Pin down at least one P1 journey before considering the idea grilled. Each journey must be a slice that could ship on its own and still deliver value.

- What is the P1 journey end-to-end? (single sentence)
- Is there a P2 / P3? If yes, can each be developed, tested, deployed, demoed independently?
- For each: write a **Given / When / Then** acceptance scenario before moving on.

### 3. Functional requirements

- What MUST the system do that it does not do today? Express as testable `System MUST …` statements.
- What MUST users be able to do? (`Users MUST be able to …`)
- For every "MUST", ask: how would you verify this in a test? If you cannot describe a test, the requirement is not yet testable — sharpen it.

### 4. Key entities and domain fit

- Which existing entities or concepts are touched? If `CONTEXT.md` exists, use the canonical names from it. Otherwise infer the vocabulary from the codebase or surrounding docs and stick to one name per concept.
- Are new entities required, or can the idea be expressed in terms of existing ones? Strongly prefer the latter.
- If a new entity is needed: what is its lifecycle, who owns it, what is its relationship to existing entities?

### 5. Edge cases

- Boundary conditions (empty, max, concurrent, partial).
- Failure modes (network, validation, permission, drift between desired and actual state).
- "What happens when … ?" — invent at least three scenarios and force an answer for each.

### 6. Success criteria

Push the user past vibes. Each criterion must be **measurable** and **technology-agnostic**:

- Replace "faster" with "in under N seconds".
- Replace "more reliable" with "P99 success rate ≥ X%".
- Replace "easier" with a task-completion metric or a reduction in support load.
- Reject criteria that name a framework, library, database, or response-time-in-ms (those are implementation, not user value).

### 7. Governance gates and project rules

The idea must respect whatever the project has already written down. Two sources to check:

- **Governance gates** — many `AGENTS.md` files list "ask first" areas (database / schema migrations, API or GraphQL changes, new external dependencies, CI/CD changes, auth changes). Read `AGENTS.md` if it exists and use whatever list it names. For each gate the idea crosses, name it in the brief under **Governance Gates Crossed** so it cannot be missed later.
- **Constitution principles** (only if `dev/constitution.md` is present) — walk its principles and flag any the idea pushes back on. A pushback may need to become an Assumption, a Governance Gate decision, or a reason to reshape the idea. Skip entirely if no constitution document exists.

### 8. Assumptions and out-of-scope

- What is being assumed about users, environment, data, or existing systems?
- What is explicitly **out of scope** for v1? (Carve scope aggressively — a small, sharp brief is better than a sprawling one.)
- What dependencies on other in-flight work exist?

## Capture format

Maintain the brief **in the conversation** as decisions land, using the structure below. Update sectionally during the session — when a decision lands, post only the affected section as an inline update (e.g. `**Updated Functional Requirements:** FR-003 …`). Re-paste the **full** brief only at the end of the session, on explicit user request, or when flipping `Status: Ready for next step` — re-pasting it every turn balloons the conversation over a 20-turn grilling.

```markdown
# Idea Brief: <short name>

**Status**: Grilling | Ready for next step
**Seed**: <one-paragraph original idea>

## Users and Value
<who, what pain, what better looks like>

## User Journeys
### P1 — <title>
- Journey: …
- Given / When / Then: …
### P2 — <title> (optional)
…

## Functional Requirements (draft)
- FR-001: System MUST …
- FR-002: Users MUST be able to …

## Key Entities
- <Entity>: <role, relationships> — existing | new

## Edge Cases
- …

## Success Criteria (draft)
- SC-001: <measurable, tech-agnostic>

## Constitution Alignment (only if dev/constitution.md exists)
- <principle>: <how the idea fits / where it pushes back>

## Governance Gates Crossed
- [ ] Database / schema change
- [ ] API change
- [ ] New dependency
- [ ] CI/CD change
- [ ] Auth change
- (Replace with the list from AGENTS.md if it names different gates.)

## Assumptions
- …

## Out of Scope (v1)
- …

## Open Questions
- [NEEDS CLARIFICATION: …]
```

Mark unresolved items as `[NEEDS CLARIFICATION: <specific question>]`. Keep grilling until at most three remain.

### Writing the brief to a file (only on explicit user request)

By default, the brief stays in the conversation. If — and only if — the user explicitly asks for a written copy:

1. Write it to a temporary path: `mktemp -t idea-brief.XXXXXX.md` (or the platform equivalent).
2. Report the absolute path to the user so they can pick it up.
3. Do **not** write to `.specify/idea-brief.md`, `docs/`, `dev/`, or any other tracked location — those choices belong to the user, not to this skill.

## Stop conditions

The brief is "Ready for next step" when **all** of the following hold:

1. At least one **P1 user journey** with a Given / When / Then acceptance scenario.
2. Functional requirements are testable — every "MUST" can be paired with a one-line verification idea.
3. Success criteria are measurable and technology-agnostic.
4. Every Governance Gate the idea crosses is explicitly checked or explicitly ruled out (using whatever list `AGENTS.md` defines, or the generic list above if none). If `dev/constitution.md` exists, principles the idea touches are addressed in the brief.
5. No more than three `[NEEDS CLARIFICATION]` markers remain.
6. If `CONTEXT.md` exists, every domain term in the brief is either present in it or was added to it during this session with the user's explicit confirmation.

When all of the applicable conditions hold, flip **Status** to `Ready for next step`, tell the user, and suggest the natural follow-up:

- If `.specify/templates/spec-template.md` exists (speckit is set up in this repo) → suggest `/speckit-specify` with the brief as input.
- Otherwise → suggest whichever the user prefers: opening an issue, drafting a PRD, or starting implementation directly.

## Anti-patterns

- **Do not grill into implementation.** Stack choices, schema column names, libraries, file paths — those belong in a later planning step. If a question can only be answered by picking an implementation, defer it.
- **Do not invent edge cases the user has not signalled care about.** Stress-test the boundaries the idea actually touches, not a generic checklist.
- **Do not stall on perfect requirements.** Three crisp testable FRs that ship is better than ten that don't.
- **Do not assume a project frame that isn't there.** If `dev/constitution.md` is missing, skip the constitution check inside lens 7 — don't invent principles. Same for `CONTEXT.md`, `AGENTS.md`, etc.
- **Do not write files unsolicited.** The brief lives in the conversation. Only write to a temp file when the user explicitly asks.
- **Do not write to `.specify/idea-brief.md`.** Even if speckit is set up in the repo, that file is the input to a different workflow and is not this skill's to manage.

### Rationalization table

When you catch yourself reaching for one of these excuses, stop:

| Excuse | Reality |
| --- | --- |
| "User seems impatient — let me batch the questions." | Batching collapses the dependency graph. One question, one recommended answer, then choose the next question based on what you just learned. |
| "The P1 journey is obvious — I can skip writing it." | If it's obvious, write it as one sentence. If you can't write it, it isn't obvious. |
| "Skip the success criteria — they'll emerge in the spec." | Success criteria force scope. Skipping them lets the spec scope drift; that's how this skill stops earning its tokens. |
| "User said `save it` — I'll write to `docs/` so it's easy to find." | The skill says temp file only. Honour the intent (save) using the path the skill names; the user can move it. |

### Red flags

You are about to violate the skill if you notice yourself:

- Queuing two or three questions in one turn.
- Flipping `Status: Ready for next step` with no P1 journey written.
- Reaching to write the brief into `.specify/idea-brief.md`, `docs/`, or `dev/` because the user said "save it".
- Skipping a lens "for time" without naming a reason it doesn't apply.

## Expected outcome

A sharpened idea brief in the conversation with `Status: Ready for next step`, with enough crisp content (P1 journey + acceptance scenario, testable FRs, measurable SCs, named governance gates, ≤3 open questions) that the user can confidently feed it into whatever comes next — a PRD, a spec, a speckit run, or a ticket — without another round of "what did you mean by …?".

---

*Inspired by [`grill-with-docs`](https://github.com/mattpocock/skills/blob/main/skills/engineering/grill-with-docs/SKILL.md) by Matt Pocock. Repositioned from sharpening a plan against existing docs to sharpening a raw idea against project context.*
