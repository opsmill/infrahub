# The `ship.md` manifest & resume logic

`ship.md` is the **single source of truth** for a unit of work in flight. It answers the three
questions this skill exists to eliminate: *where am I, what's done, what's next.* Every phase reads
it and updates it; resume relies on it entirely.

## Location

Inside the speckit feature dir, alongside the artifacts it indexes:

```
specs/NNN-slug/
  ship.md          ← this manifest
  spec.md          (feature)
  analysis.md      (bug)
  plan.md tasks.md (feature M/L)
  review.md
```

Locate the dir via `.specify/feature.json` (`{"feature_directory": "specs/NNN-slug"}`). If speckit
isn't initialized yet (bug/chore that skips speckit), create `specs/NNN-slug/ship.md` directly using
the branch slug, and still write `feature.json` so downstream speckit calls agree on the dir.

## Schema

Human-readable and glanceable on purpose — the user opens it to orient, and the model parses it to resume.

```markdown
# Ship: <one-line title>

type: feature        # bug | feature | chore
size: L              # S | M | L
risk: [security]     # subset of: irreversible security cross-team crux-algorithm  (or none)
ticket: INFP-460     # or none
branch: user-auth-infp-460
base: develop
updated: 2026-07-06

## Phases
- [x] classify              → (this file)
- [x] ticket-branch         → branch user-auth-infp-460
- [x] understand            → spec.md
- [x] plan                  → plan.md, tasks.md
- [>] implement             → 3/5 tasks; worktrees wt-a, wt-b
- [ ] review                →
- [ ] knowledge             →
- [ ] ci                    →
- [ ] commit-pr             →
- [ ] ci-watch              →

## Artifacts
- spec.md, plan.md, tasks.md
- pr: <url once open>

## Notes
- 2026-07-06 reclassified M→L after auth surface turned out cross-cutting.
```

Status markers: `[ ]` todo · `[>]` in-progress · `[x]` done · `[-]` skipped (with a reason in Notes).
The phase list is **derived from the classification** — only list phases the lane actually runs.

## Update contract

- **On entering a phase:** flip it to `[>]`, bump `updated`.
- **On finishing a phase:** flip to `[x]` **only after its exit-criteria gate passes**; record the
  artifact it produced on the same line.
- **On skipping a phase:** `[-]` with a one-line reason in Notes (e.g. knowledge capture found nothing).
- **On reclassification:** update the axes, add/remove phases, append a dated Note.
- Never mark a phase `[x]` speculatively. The manifest must reflect reality, not intent.

## Resume + reconcile

When the skill is invoked with empty `$ARGUMENTS`, or on any re-entry:

1. **Scan** for an unfinished `ship.md` (search `specs/*/ship.md` with an incomplete phase list;
   prefer one whose `branch` matches the current git branch).
2. **None found** → this is new work; ask what to ship and start at phase 1.
3. **Found** → print a **status board**: the phase list with markers, the classification line, and
   the next action. This is the "where am I" answer.
4. **Reconcile before trusting** — the manifest can drift from reality (a branch was reset, a
   worktree removed, tests now fail). For each `[x]` phase, cheaply verify its claim still holds:

   | Phase | Reconcile check |
   |---|---|
   | ticket-branch | branch exists and is checked out |
   | understand/plan | the named artifact file exists and is non-empty |
   | implement | branch is ahead of base; the phase-5 gate test is still green |
   | ci | re-run is fast? if not, trust the recorded result but flag its age |
   | commit-pr | the PR URL still resolves and is open |

   A failed check **re-opens** that phase (`[x]`→`[>]`) and everything downstream of it. Say so
   explicitly: *"implement was marked done but the gate test is red — re-opening implement + review."*
5. **Continue** at the first non-`[x]`/`[-]` phase, honoring the between-phase checkpoints.

## Rules

- The manifest is authoritative for *bookkeeping*, the repo is authoritative for *truth* — reconcile
  reconciles the two, and the repo always wins.
- One `ship.md` per unit of work (per feature dir / branch). Don't share one across branches.
- User overrides are first-class: "redo review", "skip knowledge", "jump to PR" just edit the markers
  (with reconciliation for anything they jump past) — no separate command needed.
