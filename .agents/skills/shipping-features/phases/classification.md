# Phase 1 — Classification

The first thing every `shipping-features` run does. Classification selects the **lane** (which
sibling skills run) and the **depth** (how much divergence/verification), so an `S` bug and an
`L` feature never walk the same path. The model **proposes**; the user **confirms** at a checkpoint.

## What to classify

Three axes. Write all three to `ship.md`.

### 1. Type — routes the lane

| Type | Signals | Lane head |
|---|---|---|
| `bug` | "broken", "regression", stack trace, failing test, "used to work" | `/bug-analyze` → `/bug-tdd` → `/bug-fix` |
| `feature` | new capability, user story, "add", "support", "allow users to…" | `grilling-ideas` → `/speckit-specify` → plan → implement |
| `chore` | refactor, dependency bump, rename, config, docs-only, cleanup | inline brief → direct edit |

When ambiguous (a "bug" that's really a missing feature), state the ambiguity and let the user pick.

### 2. Size — sets the depth

| Size | Heuristic (any one qualifies) | Depth |
|---|---|---|
| `S` | one file / a few lines; obvious fix; no design choice | skip specs & plan; 1 agent; gate + one verify; no parallelism |
| `M` | a few files; one clear approach; minor design choice | light spec; 2 agents; parallel spec only if a real fork exists |
| `L` | many files / cross-cutting; genuine design forks; new surface area | full spec → plan → split; 3–4 parallel framings; worktrees |

Size is about **decision complexity**, not raw line count. A 500-line mechanical rename is `S`;
a 40-line change to auth logic is `L`.

### 3. Risk flags — trigger stacked verification

Zero or more. Each one turns on the third reliability layer for the phases it touches
(see [reliability.md](reliability.md)).

| Flag | Set when | Effect |
|---|---|---|
| `irreversible` | data migration, schema change, deletion, public API change | skeptic pass on the plan synthesis |
| `security` | auth, permissions, secrets, input handling, crypto | `/security-review` mandatory; skeptic on review findings |
| `cross-team` | touches contracts other teams depend on; needs >1 reviewer | plan skeptic + note reviewers in PR |
| `crux-algorithm` | one genuinely hard algorithmic unit | twin independent implementations of that unit, gated + refuted |

## How to propose

1. Read `$ARGUMENTS` (ticket text / description) and, if a branch already has changes, the diff surface.
2. Emit a one-line guess: *"Looks like a **medium bug fix**, no risk flags — lane: analyze → tdd → fix → review → PR."*
3. **Checkpoint (AskUserQuestion or inline):** user confirms or overrides type / size / risk.
4. Write the confirmed values to `ship.md` and derive the phase list from them.

## Rules

- **Confirm before working.** Classification is a hard checkpoint — never skip it, even when "obvious".
- **Never re-ask on resume.** If `ship.md` already holds a classification, use it; only re-classify
  if the user explicitly asks to reclassify (record the change in `ship.md`).
- **Reclassification is allowed mid-flight.** If the work turns out bigger than thought, bump the
  size, note it in `ship.md`, and add the phases the new size requires. Don't silently keep the old lane.
- **Don't guess risk flags to look thorough.** A flag you can't justify from the ticket/diff is noise
  that just burns tokens on stacked verification. When unsure, leave it off and say so.
