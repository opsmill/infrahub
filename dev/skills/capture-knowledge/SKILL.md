---
name: "capture-knowledge"
description: "Capture non-obvious facts learned while working into dev/knowledge/, dev/guidelines/, or dev/guides/ so future agents understand the code faster. Trigger when the user says 'capture this', 'document this', 'we should write that down', or autonomously at the end of a feature when something non-obvious was learned."
argument-hint: "<short description of what to capture, or omit to let the skill scan the current session>"
user-invocable: true
disable-model-invocation: false
---

# Capture Knowledge

Grow the frontend docs **opportunistically** during real work, so each session leaves the codebase easier for the next agent to understand.

## Where things go

Three buckets in `dev/`:

| Bucket | Path | What belongs here |
|---|---|---|
| **Knowledge** | `dev/knowledge/frontend/` | How the system actually works. Architecture, contracts, data flow, non-obvious invariants. Descriptive. |
| **Guidelines** | `dev/guidelines/frontend/` | How code should be written. Conventions, rules, "do this not that". Prescriptive. |
| **Guides** | `dev/guides/frontend/` | Step-by-step recipes for a specific task (e.g. "writing a unit test"). Procedural. |

When in doubt: if removing the doc would make a future agent *misunderstand* the system, it's **knowledge**. If it would make them *write inconsistent code*, it's a **guideline**. If it would make them *unable to complete a specific task*, it's a **guide**.

## What to capture

Capture only things that are:

- **Non-obvious from reading the code** — a hidden constraint, a subtle invariant, a "this looks wrong but it's correct because…", a deliberate choice that surprises.
- **Stable** — architecture, contracts between layers, naming conventions, ownership boundaries. NOT specific implementations that change every sprint.
- **Reusable** — applies to more than one file or future work.

## What NOT to capture

(Mirrors the rules for auto-memory.)

- ❌ Anything obvious from reading the file: function signatures, what a component renders, prop names.
- ❌ Recent changes / git history — `git log` and `git blame` are authoritative.
- ❌ Debugging fix recipes — the fix is in the code; the commit message has the context.
- ❌ Current-task state, in-progress work, who's doing what.
- ❌ Anything already covered in CLAUDE.md, AGENTS.md, or an existing doc in the three buckets.

## Workflow

### 1. Identify the candidate fact

If the user gave a description as `$ARGUMENTS`, use it. Otherwise, scan the current session for moments where you (the agent) thought *"I wish this had been documented"* — surprising patterns, repeated questions, hidden invariants. Surface 1-3 candidates.

### 2. Classify

For each candidate, decide bucket (knowledge / guideline / guide) using the table above. State the classification and the reasoning in one sentence.

### 3. Check for duplication FIRST

Before writing anything new:

```bash
grep -ri "<key phrase from the candidate>" dev/knowledge/frontend/ dev/guidelines/frontend/ dev/guides/frontend/
```

- If a relevant doc already exists → **prefer updating it** with an Edit. Add the new fact in the right section.
- If multiple docs touch the topic → consolidate; do not scatter the same fact across files.
- Only create a new file when there is **no existing home** for the fact AND the topic is broad enough to warrant its own page.

### 4. Draft the change

Write the smallest possible addition. One paragraph, or a bullet under an existing heading. Concrete examples beat abstract description — link to a real file path with line numbers when relevant (`src/foo/bar.ts:42`).

If creating a new file, follow the structure of the most similar existing file in the same bucket. Keep frontmatter (if any) consistent.

### 5. Confirm with user before writing

Show the user:

- The bucket + target file (existing or new)
- The exact diff (or new file contents)
- Why this is non-obvious / why it belongs

Wait for approval. **Do not silently write docs** — the user owns what enters the canonical knowledge base.

### 6. Update the index entries

If the new doc is a new file, add a one-line pointer in the relevant `AGENTS.md` (`frontend/app/AGENTS.md` under "See Also") so it shows up in the skill-discovery surface for future agents.

## Heuristics for sniffing capture candidates during a session

- An `Explore` agent had to grep across multiple files to find a contract → capture that contract.
- The user corrected your understanding of how something works → capture the corrected mental model.
- A pattern was reused 3+ times without being named → name it as a guideline.
- A non-trivial decision was made ("we don't do X because Y") → capture as knowledge or guideline depending on framing.
- A workflow took >5 steps to figure out from scratch → consider a guide.

## Anti-patterns

- ❌ Writing docs that describe what code currently *does* (read the code instead).
- ❌ Long aspirational docs that don't reflect reality on `develop`.
- ❌ Creating a new file when an existing one has 80% of the same topic.
- ❌ Capturing without user confirmation.
- ❌ Capturing in-flight implementation details that will change next week.
