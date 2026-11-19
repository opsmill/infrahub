---
name: design-jam
description: >-
  Takes one piece of Infrahub frontend UI from a rough idea to a design the team can
  approve, before any implementation starts. Seven phases, each writing one file: frame,
  inventory (what @infrahub/ui already covers), explore (3-4 directions behind a switcher),
  refine, review, hand off (a published design doc and a draft PR), improve (fixes to this
  skill and the docs). Progress lives in `.design/<slug>/`, so a run can resume after a
  crash, a `/clear` or a week away. TRIGGER when: the user wants to design a screen, flow
  or component before building it; says "design jam", "let's design this", "what should
  this look like"; or asks to resume a design-jam run. DO NOT TRIGGER when: the design is
  settled and only needs coding; the user wants one isolated step (only a prototype, only
  a review), so invoke that skill directly; or the work is backend, docs or a bug fix.
---

# Design Jam

Design one piece of Infrahub frontend UI until someone who is not a designer can show it
to the team and get a decision, before anyone implements it.

## User input

```text
$ARGUMENTS
```

## Setup, once per machine

design-jam is designed to run with the paid skills, and falls back to public skills when
a paid one is not installed. Install both sets before the first run:

- **Public skills**, needed in every run: `prototype`, `emil-design-eng` and `break-ui`,
  from [`emilkowalski/skills`](https://github.com/emilkowalski/skills) (MIT).
  `grilling-ideas` ships with this repo. The run blocks until these are installed.
- **Paid skills**, the other `emil-*` skills from
  [aiforui.dev](https://aiforui.dev/learn/skills). With them, phase 0 adds product
  framing, phase 2 uses `emil-prototype`, and phase 4 runs the full review. OpsMill team
  members: follow the internal setup page in Notion. People outside OpsMill can run the
  public fallback without them.

Keep any access token out of this checkout, design-jam files, commits and PRs. Do not copy
the paid skills into `.agents/skills/`: their licence does not allow it, and this repo is
public.

## Start of every invocation

1. Run `bash <this skill's folder>/reference/preflight.sh` and show the result. If a
   required skill is missing, stop and name it. Do not run its phase from memory: the
   output would look like a design-jam run with the important pass missing. Say which
   skill set preflight reports (paid or public fallback), which passes will be skipped and
   which skills only the user can start. If it reports the public fallback, tell the user
   once that OpsMill team members get the full run by installing the paid skills, then
   continue. Run it on resumed runs too.
2. Run `ls .design/` from the repo root. If a directory matches the request, read
   `STATE.md`, then the `.design/` files it points to and the current phase's file in
   `reference/`. Say the phase, round and revision you
   are resuming and what `next:` says, before doing anything else. If the user says
   "gather" or pastes a *Copy all notes* block, resume at the *Gather* step of a round.
   When `STATE.md` is missing or disagrees with `git log --oneline -- .design/<slug>/`,
   trust git and say so.
3. Otherwise, pick a slug (`branch-diff-summary`, `schema-kind-picker`), create the design
   branch, then `.design/<slug>/`.

Create the branch before any file, because every checkpoint commits. Name it
`<your-prefix>-design/<slug>` and base it on `develop`. Use `stable` only when the user
asks (`--base stable`). Write the base as `base:` in `STATE.md`: the design PR and the
implementation branch read it from there. Never take the base from `origin/HEAD`, which is
`stable` in this repo.

Commit `.design/`. It is the record someone reads months later to learn why the UI works
the way it does.

## Phases

Each phase reads named files, invokes the named skills, writes one file and stops at a
checkpoint. Read the phase's file when the phase starts, not before.

| # | Phase | Skills | Details | Writes |
|---|-------|--------|---------|--------|
| 0 | Frame | `emil-product-thinking` (paid, optional), then `grilling-ideas` | [phase-0-frame.md](reference/phase-0-frame.md) | `00-brief.md` |
| 1 | Inventory | none, reads the repo | [phase-1-inventory.md](reference/phase-1-inventory.md) | `01-system.md` |
| 2 | Explore | `emil-prototype`, public fallback `prototype` | [phase-2-explore.md](reference/phase-2-explore.md) | prototype route, `02-directions.md`, draft design PR |
| 3 | Refine | `emil-design-eng` | [phase-3-refine.md](reference/phase-3-refine.md) | new revisions, `03-decisions.md` |
| 4 | Review | reduced: `break-ui`, `emil-design-eng`, a checklist; full: four paid review skills | [phase-4-review.md](reference/phase-4-review.md) | `04-review.md` |
| 5 | Hand off | none, publishes an Artifact | [phase-5-hand-off.md](reference/phase-5-hand-off.md) | `05-handoff.md`, `05-implement.md` |
| 6 | Improve | none, reads the run | [phase-6-improve.md](reference/phase-6-improve.md) | `06-improvements.md` |

Invoke skills in the order shown, with the Skill tool. Do not work from your memory of a
skill: its current rules must shape the output. Use the paid alternative when it is
installed. Each phase file names its conditional skills; use them only when their condition
holds, and use no other skills.

Preflight marks some skills "you type": they set `disable-model-invocation`, so the Skill
tool refuses them. When a phase needs one, ask the user to type its command (for example
`/emil-product-thinking`) with the input it should work on, wait for its result, and
continue the phase from it. Do not read its `SKILL.md` and do the work yourself.

## Rules for every phase

- **No code before `00-brief.md` exists.** A prototype looks finished, so people assume
  the decisions behind it were made.
- **Use `@infrahub/ui` first.** Every component built from scratch gets a line in
  `01-system.md` that says why.
- **Render worst-case Infrahub data.** Long schema kind names, a branch with 300 changed
  nodes, deep relationships, a node with no display label, permission denied, an empty
  result. No lorem, no three tidy rows.
- **Reject in writing.** "We rejected the split pane because the diff needs full width at
  1280px" can be reviewed. "We tried other things" cannot.

## Checkpoints

At the end of every phase:

1. Rewrite `STATE.md`.
2. Commit `.design/<slug>/` and the prototype changes together, for example
   `design(<slug>): phase 2, three directions for the change summary` or
   `design(<slug>): rev 3, filters moved into the header`. Use one plain `git` command per
   step, never `-i`. If a hook blocks the commit, use `/usr/bin/git`. Never amend or squash
   a design commit: superseded decisions must stay readable.
3. Print the file path and short SHA, the two or three decisions someone could disagree
   with, the next step in one line, and any question only the user can answer.
4. Stop. Do not start the next phase in the same turn. The checkpoint is where the user's
   judgement enters the run.

## `STATE.md`

The phase files record decisions, not where the run is. `STATE.md` records where it is:

```md
# branch-details-repos

phase: 3 — Refine
round: 2
base: develop
branch: <your-prefix>-design/branch-details-repos
pr: https://github.com/opsmill/infrahub/pull/1234 (draft)
live: dj.variant=consistent&dj.rev=3
preview: <preview URL>/_proto/branch-details?dj.variant=consistent&dj.rev=3
status: awaiting feedback since 2026-09-23
notes: 4 open · 3 addressed · 1 declined · 0 deferred
gathered: PR comments up to 2026-09-24 14:02 (feedback/round-2.md)
last: rev 3 — filters moved into the header (a1b2c3d)
next: gather notes, triage, then rev 4
blocked on: —
```

`status` is one of `working`, `awaiting feedback since <date>`, `awaiting approval`,
`gate clean` or `handed off`, so a resumed session knows whether to act or to ask. Write
`next` as a sentence.
