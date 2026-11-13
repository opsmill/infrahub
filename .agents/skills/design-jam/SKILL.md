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

The run blocks until the required skills are installed.

- `grilling-ideas` ships with this repo.
- `emil-design-eng` installs from [`emilkowalski/skills`](https://github.com/emilkowalski/skills) (MIT).
- The other `emil-*` skills are paid and install from
  [aiforui.dev](https://aiforui.dev/learn/skills) with a personal token. Ask @pa-lem for it.

Keep the token in an environment variable or in `~/.npmrc` in your home folder. Never put
it in a file in this checkout, a design-jam file, a commit or a PR. Do not copy the paid
skills into `.agents/skills/`: their licence does not allow it, and this repo is public.

## Start of every invocation

1. Run `bash <this skill's folder>/reference/preflight.sh` and show the result. If a
   required skill is missing, stop and name it. Do not run its phase from memory: the
   output would look like a design-jam run with the important pass missing. A missing
   conditional skill is fine; say which passes will be skipped. Run it on resumed runs too.
2. Run `ls .design/` from the repo root. If a directory matches the request, read
   `STATE.md`, then the phase files it points to. Say the phase, round and revision you
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
checkpoint.

| # | Phase | Skills | Writes |
|---|-------|--------|--------|
| 0 | Frame | `emil-product-thinking`, then `grilling-ideas` (both skippable) | `00-brief.md` |
| 1 | Inventory | none, reads the repo | `01-system.md` |
| 2 | Explore | `emil-prototype` | prototype route, `02-directions.md`, draft design PR |
| 3 | Refine | `emil-design-eng` | new revisions, `03-decisions.md` |
| 4 | Review | `emil-ui-polish`, `emil-surfaces`, `emil-ui-review`, `emil-prep-for-prod` | `04-review.md` |
| 5 | Hand off | none, publishes an Artifact | `05-handoff.md`, `05-implement.md` |
| 6 | Improve | none, reads the run | `06-improvements.md` |

Invoke skills in the order shown, with the Skill tool. Do not work from your memory of a
skill: its current rules must shape the output.

Use these conditional skills only when their condition holds, and no other skills:

- `emil-animations`, in phase 2 or 3, when motion carries meaning: something enters,
  changes state or follows a drag. Hover colours do not count.
- `emil-mobile-native`, in phases 3 and 4, when `00-brief.md` says people use the screen
  on a phone or tablet. "Responsive" is layout, not touch, and phase 3 covers it.
- `emil-get-creative`, in phase 2, when nothing in Infrahub or in common products is like
  the thing. Lists, detail views, diffs and forms never qualify.
- `emil-design-foundations`, in phase 4, when the tidy pass keeps finding spacing and
  hierarchy problems across the screen rather than in one place.

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

## Variants and revisions

The prototype keeps every direction and every revision reachable, so two of them can be
opened side by side:

- `dj.variant` selects a direction from phase 2.
- `dj.rev` selects a revision of the chosen direction. It starts at 1 when a direction is
  picked and goes up with every round the user approves.

All URL parameters the panel owns start with `dj.`, and knobs use `dj.k.<key>`. The
prototype shares the app's URL, so a bare `variant` or `rev` could collide with a
parameter the page already reads. Parameters outside `dj.` are left as they are.

Each revision is its own file, `rev-01.tsx`, `rev-02.tsx` and so on, copied from the
previous one and then edited. Never extract shared code from an old revision: if `rev-02`
imports something `rev-04` changes, rev 2 no longer shows what was reviewed. The
duplication is deliberate, and the files are deleted after implementation. Old revisions
do change if design tokens change, which is why the handoff screenshots are taken while
each revision is current.

Copy `reference/design-history-panel.tsx` into the prototype route rather than writing a
different panel, run `pnpm biome:fix` on the copy, and read
[`reference/history-panel.md`](reference/history-panel.md) first. It covers the panel,
knobs and pinned notes.

---

## Phase 0: Frame

Write `00-brief.md` even when both skills are skipped; later phases read it. Record each
skip as its own line in the brief ("product framing skipped at the user's request") and
repeat it at the checkpoint.

| The user says | Skip |
|---|---|
| `--no-product`, "skip the product thinking", "I know why we're building this" | `emil-product-thinking` |
| `--no-grill`, "don't grill me", "just build it" | `grilling-ideas` |
| `--fast`, "straight to prototypes" | both; ask the five questions below once, in one message |

Honour a skip the first time. Do not offer the skipped pass again or bring it back as "a
few quick questions".

1. Invoke `emil-product-thinking` on the request as written. It answers whether this is
   worth building: what problem it solves, for whom, and what happens if nothing is built.
2. Invoke `grilling-ideas` on the result, unless the idea is already settled: a spec, PRD,
   `.specify/` run or written ticket exists, an earlier `00-brief.md` still holds, or the
   user answers the questions below in one reply without pushback. Then copy the answers
   from that source into the brief, name the source, and say at the checkpoint why you
   skipped.

`grilling-ideas` writes no file, so copy its result into `00-brief.md` yourself. The brief
holds five answers in the user's words:

- **Done looks like**: one sentence on the screen when it works.
- **Who**: who reaches this screen, and what they were doing just before.
- **Riskiest assumption**: the one that makes the screen pointless if it is wrong.
- **Out of scope**: what this is not.
- **Where it's used**: desk, phone or both. Always ask this one if it is still missing
  after the skips, because phases 3 and 4 depend on it.

If an answer is vague, say which one and ask again.

## Phase 1: Inventory

Read the repo. The frontend's `AGENTS.md` and the docs it links to are already loaded; do
not ask the user for paths. Write `01-system.md` with three lists:

- **Covered**: the `@infrahub/ui` components, tokens, CVA variants and page patterns this
  screen uses, by name.
- **Close**: something exists but does not fit. Say what it lacks.
- **Missing**: nothing exists. One line each on what it would take.

Do not build anything to fill a gap yet.

## Phase 2: Explore

Invoke `emil-prototype`. Build 3 or 4 directions that differ in structure: information
architecture, order of steps, or where the work happens. If they differ only in spacing
and colour, they are one direction.

- Put the prototype on one route in the running app, with a URL you can paste into Slack.
  If the app has no good place for it, create one and record that in `01-system.md`.
- Decide where it mounts and record it in `01-system.md`. If every direction changes only
  the content area, mount inside the app layout and pass the panel `frame`. If any
  direction changes the shell (navigation, header, a global banner), mount at a top-level
  route without layout and have each revision render its own shell.
- Add the history panel, driving `dj.variant`. Every direction is `dj.rev=1` in this phase.
- Build from `@infrahub/ui`; justify anything new in `01-system.md` first.
- Mark every prototype-only file, and every line added to shared config, with a
  `PROTOTYPE design-jam <slug>` comment when you create it. Teardown searches for it.
- Use worst-case data in every direction.
- Put any value you would otherwise be asked to change (a width, a threshold, a column
  count) on a knob. Keep knobs few: each one says "not decided yet".

Write `02-directions.md`: one section per direction, saying what it bets on, what it costs
and who it suits. Do not recommend one yet.

Before the checkpoint, open the draft design PR (see
[`reference/design-pr.md`](reference/design-pr.md)), pass its URL to the panel as
`prUrl`, then commit and push. The PR's preview is the first link other reviewers can open.

At the checkpoint the user picks a direction, or parts of several.

## Phase 3: Refine

Invoke `emil-design-eng`. Take the chosen direction to a finished screen: hierarchy,
spacing, copy, keyboard behaviour, and every state it can be in, including loading,
empty, error, permission denied and too much data. Add `emil-animations` or
`emil-mobile-native` only under their conditions; when the brief says desk, say you
skipped `emil-mobile-native`.

The chosen direction becomes `dj.variant=<pick>&dj.rev=1`. Keep the other directions
reachable, and create each new revision as a copy of the last.

### Rounds

Feedback arrives over days, so refining runs in rounds that can be resumed at any step:

1. **Build** rev N, commit and push. The push rebuilds the preview.
2. **Share**: post one comment on the design PR with what changed, the preview link and
   "pin notes, then press *Post to PR*". Set `status: awaiting feedback since <date>`.
3. **Collect**: reviewers pin notes and post them to the PR. Nothing to do.
4. **Gather**: when the owner says "gather", read the PR comments with
   `gh pr view <number> --comments` (or `gh api repos/{owner}/{repo}/issues/<number>/comments`
   for timestamps). Keep the comments that start with `<!-- design-jam:<slug> -->` and are
   newer than `gathered:`. Copy them word for word, with author and date, to
   `.design/<slug>/feedback/round-<N>.md`, and update `gathered:`. If `gh` cannot reach the
   PR, ask the owner to paste the comments or a *Copy all notes* block.
5. **Triage** every open note with the owner as one of:
   - `addressed`: it changes in rev N+1; say how.
   - `declined`: it does not change; write the reason in `03-decisions.md`.
   - `deferred`: write down what it waits for.

   Reply on the PR with one line per note, so reviewers see what happened to it.
6. **Checkpoint**, then start rev N+1.

Do not start rev N+1 while notes are untriaged. If a round gets no notes, write that down
and ask the owner whether nobody objected or nobody looked.

Write `03-decisions.md`: every choice that is not obvious, one line each, with its reason.
Record each knob's final value as a number.

## Phase 4: Review

Run four passes on the running prototype, in this order. Tidy first, so the critique is
about the design and not the padding.

1. **Tidy**: `emil-ui-polish`, then `emil-surfaces`. Check repeated items (cards in a row,
   rows in a list) as one object: same padding, edges and baselines. If the findings keep
   pointing at spacing or hierarchy across the screen, invoke `emil-design-foundations`
   once.
2. **Critique**: `emil-ui-review`. Does it read, does the hierarchy hold, is the copy right.
3. **Readiness**: `emil-prep-for-prod`. Skip its marketing and SEO checks and say so.
4. **By hand**: no skill checks these.
   - Tab from the top: the order makes sense and the focus ring shows.
   - Look at dark mode.
   - At phone width there is no sideways scroll. If the brief says phone, run
     `emil-mobile-native` again and test on a real device, not emulation.
   - Every state from phase 3 still renders.

Fix each finding or accept it with a reason. Write `04-review.md`: findings by pass, each
fixed or accepted, with reasons.

**Gate**: phase 5 does not start while a finding is unresolved. "Accepted: the empty state
is out of scope, recorded as a gap" resolves one; silence does not. At the checkpoint, say
"the gate is clean" in those words. The code is copied into production next, and nobody
reviews again code that arrived approved.

## Phase 5: Hand off

Write the design doc to `05-handoff.md`, publish it as an Artifact, and add the URL at the
top of the file. The repo copy is the one that lasts; links can break or sit behind
access rules. The doc has these sections, in order:

1. **What and why**: the brief, in the user's words.
2. **Proposal**: the chosen direction, a screenshot of each state, and the prototype URL.
3. **Rejected directions**: one paragraph per direction from `02-directions.md`, with the
   reason.
4. **Decisions**: from `03-decisions.md`.
5. **Open questions**: what the user still has to decide.
6. **System gaps**: the `Missing` list from `01-system.md`.
7. **History**: `dj.variant` and `dj.rev` links to every direction and revision, and the
   `git log -p .design/<slug>/` command. Say that old revisions change if design tokens
   change.

Save the screenshots in `.design/<slug>/shots/`. Give the user the link and one sentence
to post above it.

Replace the design PR body with `05-handoff.md`, set `status: awaiting approval`, and
stop. The design PR is never merged; approving it is the decision to implement. Details
are in [`reference/design-pr.md`](reference/design-pr.md).

Write `05-implement.md`, so implementation starts by copying the approved revision rather
than rebuilding it. Its lists, the implementation branch and the teardown checklist are in
[`reference/implementation.md`](reference/implementation.md).

## Phase 6: Improve the skill and the docs

Run this after the phase-5 checkpoint, and again at teardown if implementation found more.

Read `STATE.md`, the `feedback/` files, `git log .design/<slug>/` and the conversation.
List each place where the run had to work around something, in one of these groups:

- **This skill**: a rule that was wrong, missing or ignored, a panel or notes bug, or a
  check the preflight missed. Fix it in `.agents/skills/design-jam/`.
- **A skill it invokes**: advice that did not fit Infrahub. Record it only; the `emil-*`
  skills are not in this repo.
- **Internal docs**: a frontend fact the run had to find in code because
  `frontend/app/AGENTS.md`, `dev/guidelines/frontend/` or `dev/knowledge/` does not say it.
  Follow `dev/guidelines/documentation.md` for where it goes.
- **`@infrahub/ui`**: already in the `Missing` list of `01-system.md`. Link it.

Write `06-improvements.md`: one line per finding, with its group and the proposed edit.
Apply only what the user approves, on a new branch from `develop`. The design branch is
never merged, so edits made there are lost. Open the PR with the repo's `pr` skill and add
its URL to the file. If there are no findings, write that in one line.
