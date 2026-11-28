---
name: capturing-knowledge
description: >-
  Use when the user says "capture this", "document this", "we should write that
  down"; autonomously at the end of a feature when something non-obvious was
  learned; or when invoked by another skill (e.g. shipping-features) as its
  knowledge-capture step. Do not use when the fact is obvious from reading the
  code, is recent git history, is a one-off debugging recipe, or is already
  documented. Captures non-obvious facts into the project's knowledge,
  guidelines, or guides docs so future agents understand the code faster.
---

# Capturing Knowledge

## User Input

```text
$ARGUMENTS
```

Treat `$ARGUMENTS` as a short description of what to capture. If empty, scan the
current session for capture-worthy moments (see heuristics below).

## What this does

Grow a project's documentation **opportunistically** during real work, so each
session leaves the codebase easier for the next agent to understand. This skill
is project-agnostic: it discovers where a project keeps its docs, proposes the
smallest useful addition, and **never writes without confirmation**.

## When to use

- The user says "capture this", "document this", "we should write that down".
- Autonomously at the end of a feature when something non-obvious was learned.
- When invoked by another skill (e.g. `shipping-features`) as its knowledge-capture step.

Do **not** use this skill to record things that are obvious from the code, recent
git history, one-off debugging recipes, or facts already documented (see
"What NOT to capture").

## The three buckets

Most projects separate docs into three kinds. The names and exact paths vary, but
the distinction is stable:

| Bucket | What belongs here |
|---|---|
| **Knowledge** | How the system actually works. Architecture, contracts, data flow, non-obvious invariants. Descriptive. |
| **Guidelines** | How code should be written. Conventions, rules, "do this not that". Prescriptive. |
| **Guides** | Step-by-step recipes for a specific task (e.g. "writing a unit test"). Procedural. |

When in doubt: if removing the doc would make a future agent *misunderstand* the
system, it's **knowledge**. If it would make them *write inconsistent code*, it's
a **guideline**. If it would make them *unable to complete a specific task*, it's
a **guide**.

## Discover where docs live (read what exists, ask only if nothing is found)

Before drafting anything, locate the project's documentation home. This skill must
work in any repo, so probe — don't assume a fixed layout.

1. **Look for conventional bucket directories** (with or without a sub-domain like
   `frontend/`, `backend/`, `python/`):
   - Knowledge: `dev/knowledge/`, `docs/knowledge/`, `knowledge/`
   - Guidelines: `dev/guidelines/`, `docs/guidelines/`, `guidelines/`
   - Guides: `dev/guides/`, `docs/guides/`, `guides/`

   ```bash
   fd -t d 'knowledge|guidelines|guides' dev docs 2>/dev/null || \
     find dev docs -type d \( -name knowledge -o -name guidelines -o -name guides \) 2>/dev/null
   ```

2. **Look for pointers in `AGENTS.md` / `CLAUDE.md`.** Many projects list their doc
   layout there (under a "See Also" / "Guidelines" / "Knowledge" heading). If a
   pointer names a directory, use it.
3. **If buckets exist, use them.** Match the existing sub-domain when there is one
   (e.g. a frontend change → `dev/knowledge/frontend/`).
4. **If nothing is found, ask the user once:** state the 1–3 facts worth capturing
   and ask where captured learnings should go, or whether to skip. Never invent a
   location and never write to one the user has not confirmed.

Empty captures are a feature, not a failure: if nothing genuinely non-obvious was
learned, say so and skip — do not ask where to put nothing.

## What to capture

Capture only things that are:

- **Non-obvious from reading the code** — a hidden constraint, a subtle invariant,
  a "this looks wrong but it's correct because…", a deliberate choice that surprises.
- **Stable** — architecture, contracts between layers, naming conventions, ownership
  boundaries. NOT specific implementations that change every sprint.
- **Reusable** — applies to more than one file or future work.

## What NOT to capture

- ❌ Anything obvious from reading the file: function signatures, what a component
  renders, prop names.
- ❌ Recent changes / git history — `git log` and `git blame` are authoritative.
- ❌ Debugging fix recipes — the fix is in the code; the commit message has the context.
- ❌ Current-task state, in-progress work, who's doing what.
- ❌ Anything already covered in `CLAUDE.md`, `AGENTS.md`, or an existing doc.

## Workflow

### 1. Identify the candidate fact

If the user gave a description as `$ARGUMENTS`, use it. Otherwise, scan the current
session for moments where you (the agent) thought *"I wish this had been documented"*
— surprising patterns, repeated questions, hidden invariants. Surface 1–3 candidates.

### 2. Classify

For each candidate, decide bucket (knowledge / guideline / guide) using the table
above. State the classification and the reasoning in one sentence.

### 3. Discover the docs home

Run the discovery steps above. If no home exists, ask the user (or skip if there is
nothing worth capturing).

### 4. Check for duplication FIRST

Before writing anything new, search the discovered buckets:

```bash
grep -ri "<key phrase from the candidate>" <discovered knowledge/guideline/guide dirs>
```

- If a relevant doc already exists → **prefer updating it** with an Edit. Add the new
  fact in the right section.
- If multiple docs touch the topic → consolidate; do not scatter the same fact across files.
- Only create a new file when there is **no existing home** for the fact AND the topic
  is broad enough to warrant its own page.

### 5. Draft the change

Write the smallest possible addition. One paragraph, or a bullet under an existing
heading. Concrete examples beat abstract description — link to a real file path with
line numbers when relevant (`src/foo/bar.ts:42`).

If creating a new file, follow the structure of the most similar existing file in the
same bucket. Keep frontmatter (if any) consistent.

### 6. Confirm with user before writing

Show the user:

- The bucket + target file (existing or new)
- The exact diff (or new file contents)
- Why this is non-obvious / why it belongs

Wait for approval. **Do not silently write docs** — the user owns what enters the
canonical knowledge base.

### 7. Update the index entries

If the new doc is a new file and the project has an index (e.g. an `AGENTS.md`
"See Also" section that lists docs), add a one-line pointer there so it shows up in
the skill-discovery surface for future agents. Skip if the project has no such index.

## Heuristics for sniffing capture candidates during a session

- An exploration agent had to grep across multiple files to find a contract → capture that contract.
- The user corrected your understanding of how something works → capture the corrected mental model.
- A pattern was reused 3+ times without being named → name it as a guideline.
- A non-trivial decision was made ("we don't do X because Y") → capture as knowledge or guideline depending on framing.
- A workflow took >5 steps to figure out from scratch → consider a guide.

## Anti-patterns

- ❌ Writing docs that describe what code currently *does* (read the code instead).
- ❌ Long aspirational docs that don't reflect reality on the default branch.
- ❌ Creating a new file when an existing one has 80% of the same topic.
- ❌ Capturing without user confirmation.
- ❌ Inventing a docs location instead of asking when none is found.
- ❌ Capturing in-flight implementation details that will change next week.
