# The `ship.md` index & resume logic

`ship.md` is a thin **index**, not a store. It answers *where am I, what's done, what's next* by
**pointing at the external homes** where each stage's real artifact lives (Jira, `specs/`, the
implement report, `dev/` docs, the PR). The content of record is always external; `ship.md` just
ties it together so the run is resumable and glanceable.

## Location

Inside the feature dir, next to the artifacts it points at:

```
specs/<feature>/
  ship.md                    ← this index (pointers + status only)
  spec.md · plan.md · tasks.md          (Prep, external content)
  opsmill-implement-report.md           (Implement, external content)
```

Locate the dir via `.specify/feature.json` (`{"feature_directory": "specs/<feature>"}`). For a
bug/chore that skips speckit, create `specs/<feature>/ship.md` from the branch slug and still write
`feature.json` so downstream speckit calls agree on the dir.

## Schema

Glanceable on purpose — the user opens it to orient, the model parses it to resume. **Pointers, not copies.**

```markdown
# Ship: <one-line title>

type: feature        # bug | feature | chore
size: L              # S | M | L
risk: [security]     # subset of: irreversible security cross-team crux-algorithm  (or none)
issue: INFP-460      # Jira/JPD or GitHub issue — the progress lives THERE
branch: user-auth-infp-460
base: develop
updated: 2026-07-15

## Stages
- [x] intake       → issue INFP-460 · branch user-auth-infp-460
- [x] prep         → specs/007-user-auth/ (spec·plan·tasks)
- [>] implement    → specs/007-user-auth/opsmill-implement-report.md (3/5 chunks)
- [ ] delivery     → pr: <url once open>
- [ ] extract      → dev/knowledge, dev/adr

## Notes
- 2026-07-15 reclassified M→L after auth surface turned out cross-cutting.
```

Markers: `[ ]` todo · `[>]` in-progress · `[x]` done · `[-]` skipped (reason in Notes).
Only list the stages the lane actually runs (a bug's light lane has fewer).

## Update contract

- **On entering a stage:** flip to `[>]`, bump `updated`.
- **On finishing a stage:** flip to `[x]` **only after its gate passes**; record the **pointer** to
  where the output landed (spec dir, report path, PR url) — not a copy of the content.
- **On skipping:** `[-]` with a one-line reason in Notes.
- **On a Jira transition:** record it here only after the user accepts it at the checkpoint.
- Never mark a stage `[x]` speculatively — the index must reflect reality, not intent.

## Resume + reconcile

When the skill is invoked with empty `$ARGUMENTS`, or on any re-entry:

1. **Scan** `specs/*/ship.md` for an unfinished index; prefer one whose `branch` matches the current git branch.
2. **None found** → new work; ask what to ship and start at Intake.
3. **Found** → print a **status board**: stages with markers, classification line, next action.
4. **Reconcile against the live sources before trusting** — the index can drift; the external homes
   always win:

   | Stage | Reconcile check (source of truth) |
   |---|---|
   | intake | branch exists & checked out; issue resolves (Jira/GitHub) |
   | prep | `spec.md`/`plan.md`/`tasks.md` exist and are non-empty in the spec dir |
   | implement | branch ahead of base; gate tests green; report has no open high-sev findings |
   | delivery | PR url resolves and is open; CI status on GitHub |
   | extract | referenced `dev/` docs exist |

   A failed check **re-opens** that stage (`[x]`→`[>]`) and everything downstream. Say so explicitly:
   *"implement was marked done but the gate test is red — re-opening implement + delivery."*
5. **Continue** at the first non-`[x]`/`[-]` stage, honoring the between-stage checkpoints.

## Rules

- The index is authoritative for *bookkeeping*; the external homes are authoritative for *truth* —
  reconcile bridges them, and the source always wins.
- One `ship.md` per unit of work (per feature dir / branch). Don't share one across branches.
- User overrides are first-class: "redo prep", "skip extract", "jump to delivery" just edit the
  markers (with reconciliation for anything jumped past) — no separate command needed.
