---
name: design-jam
description: >-
  Takes one piece of Infrahub frontend UI from a rough idea to a design other people can
  argue with, before any implementation starts. Seven phases, each writing one file: frame
  (is it worth building, then grill it), inventory (what @infrahub/ui already covers),
  explore (3-4 real directions behind a switcher), refine, review, hand off (a published,
  shareable design doc), improve (fixes to this skill and the docs the run surfaced). Progress lives in `.design/<slug>/`, so a run resumes after a
  crash, a `/clear`, or a week away. Everything is built from the existing design system.
  TRIGGER when: the user wants to design a screen, flow, or component before building it;
  says "design jam", "let's design this", "what should this look like"; or asks to resume a
  design-jam run. DO NOT TRIGGER when: the design is already settled and only needs coding;
  the user wants a single isolated step (just a prototype, just a review) — invoke that
  skill directly; or the work is backend, docs, or a bug fix.
---

# Design Jam

Design a piece of Infrahub frontend UI to the point where a non-designer can put it in
front of the team and get a real decision out of them — before anyone implements it.

## User input

```text
$ARGUMENTS
```

## Setup, once per machine

Design-jam invokes skills that are not in this repo, and the preflight below blocks a run
until the required ones are installed.

- `grilling-ideas` ships with this repo.
- `emil-design-eng` and the other public skills install from
  [`emilkowalski/skills`](https://github.com/emilkowalski/skills) (MIT).
- Every other `emil-*` skill is paid and installs from
  [aiforui.dev](https://aiforui.dev/learn/skills) with a personal access token. Ask
  @pa-lem for the token.

Keep the token out of the repo. Put it in an environment variable or your home `~/.npmrc`,
never in a file under this checkout, and never paste it into a design-jam file, a commit
or a PR. Do not copy the paid skills into `.agents/skills/` either: their licence does not
allow redistribution, and this repo is public.

## First action, every invocation

0. Run `bash <this skill's folder>/reference/preflight.sh` and show the user the result.

   A missing skill does not announce itself. The agent quietly falls back to its own
   judgement and produces something that looks like a design-jam run but skipped the pass
   that mattered — and nobody finds out until the review gate, or later. If a **required**
   skill is missing, stop and say which one; do not run the phase without it and do not
   approximate it from memory. Conditional skills that are absent are fine: say which ones,
   and say that those passes will be skipped.

   Re-run it on a resumed run too. Plugins get uninstalled between sessions.

1. `ls .design/` from the repo root. If a directory matches what the user named, read
   **`STATE.md` first** — it says the phase, the round, the live revision, and what is
   being waited on — then the phase files it points at. Say which phase, revision and
   round you are resuming at, and what the state says is next, before doing anything else.
   If the user says "gather", or pastes a *Copy all notes* block, you are resuming at the
   *Gather* step of a round (see § Rounds): gather or read the paste before the files.

   `git log --oneline -- .design/<slug>/` is the backstop when `STATE.md` is missing or
   stale — it tells you what was approved and when, including in sessions you have no
   memory of. If the two disagree, trust git and say so.
2. Otherwise slug the request (`branch-diff-summary`, `schema-kind-picker`), create the
   design branch, then `.design/<slug>/`.

   **The branch comes first, before any file.** Checkpoints commit, and a commit on
   `develop` or `stable` is the one mistake this skill must never make. Branch
   `<your-prefix>-design/<slug>` off **`develop`** — design work is ongoing-topic work and
   that is where it lives. The user can say `--base stable` (or just "base it on stable")
   when the design targets a release; honour it, and record whichever it was as `base:` in
   `STATE.md`, because the design PR (opened in phase 2) and the implementation branch both read
   it from there. Never guess a base from `origin/HEAD`; in this repo that resolves to
   `stable`, which is the wrong default for design work.

`.design/` is committed, not ignored. The record is the point — it is what someone reads
six weeks later when they ask why the UI works this way.

## The contract

Seven phases. Each reads named files, invokes at most one named skill (phases 0 and 4
invoke a sequence), writes one named file, and stops at a checkpoint.

| # | Phase | Skill to invoke | Writes |
|---|-------|-----------------|--------|
| 0 | Frame | `emil-product-thinking`, then `grilling-ideas` *(both skippable)* | `00-brief.md` |
| 1 | Inventory | — (reads the repo) | `01-system.md` |
| 2 | Explore | `emil-prototype` | prototype route, `02-directions.md`, the draft design PR |
| 3 | Refine | `emil-design-eng` | refined route, `03-decisions.md` |
| 4 | Review | `emil-ui-polish` → `emil-surfaces` → `emil-ui-review` → `emil-prep-for-prod` | `04-review.md` |
| 5 | Hand off | — (publishes an Artifact) | `05-handoff.md`, `05-implement.md`, a URL |
| 6 | Improve | — (reads the run) | `06-improvements.md`, a PR off `develop` if approved |

Phases 0 and 4 each invoke two skills, in the order given. In phase 0 that order matters:
`emil-product-thinking` decides whether this is the right thing to build, `grilling-ideas`
then attacks the answer. Framing first, then pressure — the reverse just argues about
details of something nobody checked was worth doing.

Four conditional skills, and only these four:

- `emil-animations` — in phase 2 or 3, only when motion carries meaning (something enters,
  transitions between states, or responds to a drag). Not for hover colour changes.
- `emil-mobile-native` — in phase 3 and again in phase 4, only when `00-brief.md` says
  people use this on a phone or tablet, or the user asks. "It should be responsive" is not
  the trigger — that's layout, and phase 3 covers it. The trigger is touch: taps, sheets,
  swipes, the software keyboard, the notch. Infrahub is used at a desk, so most runs skip
  this, and a run that loads it without a reason in the brief is doing so wrongly.
- `emil-get-creative` — in phase 2, only when the thing has no precedent anywhere in the
  app and no precedent in the products people already use. Almost never true for Infrahub
  screens, which are lists, detail views, diffs and forms.
- `emil-design-foundations` — in phase 4, only when the tidy pass keeps surfacing rhythm
  and hierarchy problems rather than local ones, which means the spacing system is the
  fault and not the screen.

Reach for no other skill. A run that pulls in five more skills produces five more opinions
and no decision.

Invoke each skill with the Skill tool. Do not paraphrase what you remember it saying — the
point of naming it here is that its rules, not your recollection of them, shape the output.

## Four rules that make the output trustworthy

**No code before `00-brief.md` exists.** A prototype looks finished, so people assume the
decisions behind it were made. If they weren't, the prototype launders a guess into a
plan. The brief is what makes the guess visible.

**Nothing gets drawn that `@infrahub/ui` already covers.** Every component you build from
scratch is a line in `01-system.md` with a written justification. An invented component is
a second design system, and the second one always loses.

**Every direction renders worst-case Infrahub data.** Long schema kind names, a branch with
300 changed nodes, deeply nested relationships, a node with no display label, a
permission-denied response, an empty result. Not lorem, not three tidy rows. Finding out it
breaks here costs minutes; finding out in review costs the review.

**Rejected directions are rejected in writing.** "We tried other things" is not reviewable.
"We rejected the split-pane because the diff needs full width at 1280px" is.

## Checkpoints

At the end of every phase, **commit first, then stop**.

Commit `.design/<slug>/` together with whatever prototype code changed, as one commit:

```text
design(<slug>): phase 2 — three directions for the change summary
design(<slug>): rev 3 — filters moved into the header
```

Use plain single `git` commands, one per step, and never `-i`. (If a hook blocks the write,
fall back to `/usr/bin/git`.) Never amend or squash a design commit — the point of the
history is that superseded thinking stays readable, and an amend deletes exactly the thing
someone will want to look back at.

Before committing, rewrite `STATE.md` (format below). It goes in the same commit.

Then print:

- the file you wrote, by path, and the commit's short SHA
- the two or three decisions in it that someone could disagree with
- what comes next, in one line
- any question only the user can answer

Then wait. Do not start the next phase in the same turn. The checkpoints are where a
non-designer's judgement enters the process; skipping them turns this into a slot machine.

## `STATE.md` — where the run is, in twelve lines

Rewritten at every checkpoint, committed with it. It exists because the phase files record
what was decided, not where you are — and a run that spans days of waiting for feedback
cannot be resumed from decisions alone.

```md
# branch-details-repos

phase: 3 — Refine
round: 2
base: develop
branch: <your-prefix>-design/branch-details-repos
pr: https://github.com/opsmill/infrahub/pull/1234 (draft, opened at end of phase 2)
live: dj.variant=consistent&dj.rev=3
preview: <preview URL>/_proto/branch-details?dj.variant=consistent&dj.rev=3
status: awaiting feedback since 2026-09-23
notes: 4 open · 3 addressed · 1 declined · 0 deferred
gathered: PR comments up to 2026-09-24 14:02 (feedback/round-2.md)
last: rev 3 — filters moved into the header (a1b2c3d)
next: gather notes, triage, then rev 4
blocked on: —
```

Two lines matter most. `status` is one of `working`, `awaiting feedback since <date>`,
`awaiting approval`, `gate clean`, `handed off` — it tells a resumed session whether to act
or to ask. `next` is written as the sentence you would want to read first, not a phase
number.

## History — two axes, both kept

Every param the panel owns is namespaced `dj.*`, and knobs are `dj.k.<key>`. The prototype
route lives inside the real app and shares its URL, so a bare `variant`, `rev` or `compare`
is exactly the kind of name a page already uses — and the collision is silent in both
directions: the app reads our value, or we overwrite theirs. Writes start from the live
search string, so params outside the namespace survive untouched.

Nothing in a design-jam run is deleted. Two different questions need two different answers:

- **`dj.variant`** — the parallel directions from phase 2. *Which of these should we do?*
- **`dj.rev`** — the successive iterations from phase 3 onward. *Did that change make it
  better?* Revisions start at `dj.rev=1` when a direction is picked, and increment on every
  round of changes the user approves.

Keep every variant and every revision reachable in the route. Two URLs open side by side
is how you actually answer "is this better than what we had", and a screenshot in Slack
never answers it. The route stays this way until phase 5; trimming it is the user's call,
not yours, and they make it after the design is approved.

`git log -p .design/<slug>/` is the reasoning over time; `git diff <sha1>..<sha2>` on the
prototype path is the change as code. Both work because of the commit rule above — say so
in the handoff doc so the next person knows the history is there.

## The history panel and notes

Both axes are driven from one control bar. Copy `reference/design-history-panel.tsx` into
the prototype route and adapt it; do not invent a different one, because a panel that
behaves differently on every run is a panel nobody learns. Read
[`reference/history-panel.md`](reference/history-panel.md) before you copy it: it says what
the panel must do, how knobs and pinned notes work, and where notes are stored.

On the way in, run `pnpm biome:fix` on the copies, because the reference files are not
formatted to this repo's line width, and pass `frame` so the shell fills the app's content
area rather than the whole window.

**At the start of every phase-3 round, gather notes first** (the *Gather* step of
§ Rounds). The gathered notes are the user's actual instructions for this revision,
written while they were looking at the thing. Asking anyone to re-describe what they
already pinned is the failure this whole mechanism exists to prevent.

### Revisions are frozen copies

Each revision is its own file — `rev-01.tsx`, `rev-02.tsx` — created by copying the
previous one and editing the copy. Never refactor a shared piece out of an old revision:
the moment `rev-02` imports a component that `rev-04` later changes, rev 2 silently stops
being what it was, and the history is worthless.

This duplicates code on purpose. These files are thrown away after the design is approved,
they are never imported by the app, and a prototype that carries four copies of a screen is
cheaper than a review argued from memory.

One consequence to state in the handoff doc: old revisions drift if design tokens change
under them. That is acceptable, and it is why the screenshots in the handoff doc are taken
at the moment each revision is current.

---

## Phase 0 — Frame

Both passes in this phase are skippable. `00-brief.md` is not — everything downstream reads
it, and phase 3 decides whether to load `emil-mobile-native` from a line in it. Skipping a
skill means the user answers its questions directly; it never means the file goes unwritten.

Record every skip in `00-brief.md` as its own line — *"product framing skipped at the user's
request"* — and repeat it at the checkpoint. A skip that is written down is a decision
someone can revisit; a skip that is silent looks like an oversight six weeks later.

### Skipping

| The user says | Effect |
|---|---|
| `--no-product`, "skip the product thinking", "I know why we're building this" | Skip `emil-product-thinking` |
| `--no-grill`, "don't grill me", "just build it" | Skip `grilling-ideas` |
| `--fast`, "straight to prototypes" | Skip both; ask the four questions once, in one message, and accept whatever comes back |

Honour it the first time it is asked. Do not re-offer the skipped pass at the next
checkpoint, and do not smuggle it back in as "a few quick questions" — being talked out of a
skip is worse than never offering it.

One thing is not skippable: if the answer to **where it's used** is still missing after the
skips, ask that single question. Phase 3 branches on it, and guessing wrong means either a
touch pass nobody wanted or a phone screen nobody checked.

### The passes

Invoke `emil-product-thinking` first, on the user's request as written.

Its job is the question that comes before any design one: is this the right thing to build?
What problem does it actually solve, for whom, and what happens if we build nothing? A
screen that is beautifully designed and solves a problem nobody has is the most expensive
thing this skill can produce.

Then invoke `grilling-ideas` on what came back — **unless the idea is already hardened**.

Skip it when any of these is true, and say in the checkpoint that you skipped it and why:

- there is already a spec, PRD, `.specify/` run, or a written ticket for this
- a previous `design-jam` run left a `00-brief.md` that still holds
- the user answers the four questions below without pushback, in one reply

That skill's own trigger conditions rule it out once an idea is formalised — grilling
something already specced re-litigates a decision the team has made. In that case, carry the existing spec's answers into
`00-brief.md` yourself and name the source.

`grilling-ideas` writes no file — its output is an idea brief that lives in the
conversation. Capturing it into `00-brief.md` is your job, not its.

Its job is to attack that framing, not to help you write it up. Push until you have, in the
user's own words:

- **Done looks like:** one sentence describing the state of the screen when it works.
- **Who hits this, and what they were doing before they got here.**
- **The riskiest assumption** in the request — the one that, if wrong, makes the whole
  screen pointless.
- **Out of scope:** what this is explicitly not.
- **Where it's used:** desk, phone, or both. This one line decides whether
  `emil-mobile-native` runs later, so don't leave it implied.

If the user's answer to any of these is vague, say which one and ask again. One round of
real pushback beats four polite questions.

Write `00-brief.md`. Nothing else in this phase.

## Phase 1 — Inventory

No skill. Read the repo. Claude Code already loads the frontend's own instructions and the
guideline and knowledge docs they point at — use those, don't ask the user for paths.

Produce `01-system.md` with three lists:

- **Covered** — the `@infrahub/ui` components, tokens, CVA variants and existing page
  patterns that this screen is made of. Name them.
- **Close** — something exists but doesn't quite fit. Say what's missing from it.
- **Missing** — nothing covers this. One line each on what it would take.

Do not build anything to fill a gap yet. A gap named in phase 1 and still unfilled in phase
5 is a finding worth more than the screen.

## Phase 2 — Explore

Invoke `emil-prototype`.

Build **3 to 4 structurally different answers** to the brief — different information
architecture, different sequence, different place the work happens. Four restyles of one
layout is not exploration, and you will know you've done it when the variants differ only
in spacing and colour.

Requirements on the prototype:

- One route in the running app, reachable at a URL you can paste into Slack. Find where the
  app's routes live; if there's no sensible home for a prototype route, create one and
  record that as a gap in `01-system.md`.
- **Decide where it mounts, and write the decision in `01-system.md`.** If every direction
  changes only what sits inside the content area, mount inside the app layout and pass the
  panel `frame` so the real sidebar and header stay. If any direction touches the shell —
  navigation, header, a global banner, the page frame itself — mount at a top-level route
  with no layout and have each revision render its own copy of the shell. Compare mode
  shows two complete documents, so it will faithfully show whatever each revision renders;
  a shell change that the revision cannot render is a shell change nobody will ever see.
- The history panel from this skill's `reference/` folder, driving `dj.variant` so a link
  opens on the variant you meant. In phase 2 every direction is `dj.rev=1`; the revision
  controls start doing real work in phase 3.
- Built from `@infrahub/ui` and existing components. Anything new is justified in
  `01-system.md` first.
- Worst-case data in every variant, per the rule above.
- Any value you'd otherwise re-prompt to change — a width, a threshold, a delay, a column
  count — declared as a knob on the panel, so the user finds the right number by dragging
  instead of by asking you. See *Knobs* in `reference/history-panel.md` for how sparing to be.

Write `02-directions.md`: one section per direction — what it bets on, what it costs, who
it's best for. Do not recommend one yet. Let them see it first.

**Before the checkpoint, open the draft design PR** (see `reference/design-pr.md`). Reviewers can only
comment on a prototype they can open, and the preview that PR builds is the first link
anyone else can open; waiting until phase 5 means every refine round runs on localhost
with nobody but the owner looking. Then pass the PR URL to the panel as `prUrl`, commit,
and push, so the preview is built with *Post to PR* already on it.

Checkpoint: the user picks a direction, or picks parts of several.

## Phase 3 — Refine

Invoke `emil-design-eng`.

Take the chosen direction from "the idea reads" to "this is the real thing": hierarchy,
spacing, states, the copy, keyboard behaviour, and every state the screen can actually be
in — loading, empty, error, permission-denied, too much data.

If motion carries meaning here, invoke `emil-animations` as well. If it doesn't, don't.

If `00-brief.md` says people use this on a phone or tablet, invoke `emil-mobile-native` as
well, and apply it to the real touch surfaces — tap targets, sheets, the software keyboard,
safe areas. If the brief says desk, skip it and say you skipped it.

Do not delete the other variants. The chosen one becomes `dj.variant=<pick>&dj.rev=1`, the
others stay reachable, and every approved round of changes after that increments `rev`
while leaving the previous revision working — a new `rev-NN.tsx` copied from the last one,
per the rule above.

That is what makes "did that change make it better" answerable: you open `dj.rev=1` and
`dj.rev=4` side by side and look. Overwriting the old revision destroys the only evidence
that would settle the argument.

### Rounds

Refining is not one pass; it is a loop, and the loop usually spans days, because the
feedback comes from people who open the link when they get to it. Name the loop so the run
can be resumed at any point in it. One round is:

1. **Build** `rev N`, commit, and push. The push rebuilds the preview.
2. **Share** — post one comment on the design PR: what changed in `rev N`, its preview
   link, and "pin notes, then press *Post to PR*". Record the date and `awaiting feedback`
   in `STATE.md`. GitHub notifies everyone on the PR; the owner can paste the same link
   into Slack.
3. **Collect** — nothing for you to do. Reviewers pin notes and post them to the PR.
4. **Gather** — when the owner says "gather", read the PR's comments yourself:
   `gh pr view <number> --comments`, or `gh api repos/{owner}/{repo}/issues/<number>/comments`
   for timestamps. Keep the ones whose body starts with `<!-- design-jam:<slug> -->` and
   that are newer than `gathered:` in `STATE.md`. Write them, verbatim and with author and
   date, to `.design/<slug>/feedback/round-<N>.md`, and update `gathered:`. That file is
   committed with the round's checkpoint, so feedback stays in the repo's history. If
   `gh` cannot reach the PR, ask the owner to paste the comments, or a *Copy all notes*
   block, instead.
5. **Triage** every open note, with the owner, into exactly one of:
   - `addressed` → it changes in `rev N+1`; say what.
   - `declined` → it doesn't, and the reason goes in `03-decisions.md`. "Declined" without a
     reason is not a decision; it is a note someone will re-raise.
   - `deferred` → it waits, and the round or condition it waits for is written down.
   Reply on the PR to each block with its outcome, one line per note, so reviewers see
   what happened to what they wrote. The reasons live in `03-decisions.md`, which is the
   durable record. Feedback is subject to the same rule as
   directions: rejected in writing, or not rejected.
6. **Checkpoint**, then `rev N+1` starts round two.

A round with zero notes after a reasonable wait is a finding too — write it down, because
"nobody objected" and "nobody looked" are different things and the owner should say which.

Do not start `rev N+1` with open notes untriaged. Fixing what you noticed while ignoring
what others pinned is how a design drifts away from its reviewers while looking like it is
improving.

Write `03-decisions.md`: every non-obvious choice, one line each, each with its reason. A
decision without a reason can't be argued with, which means it can't be approved either.
Record every knob's settled value as a number there too — a knob left unresolved becomes a
slider someone ships.

## Phase 4 — Review

Four passes, in this order, each against the running prototype. The order is the point:
tidy the obvious mess before asking anyone to judge the design, because a critique spent on
misaligned padding never reaches the actual question.

**4a — Tidy.** `emil-ui-polish`, then `emil-surfaces`.

Together these are the "is it knit" pass, and they cover exactly what makes a screen look
unfinished up close: spacing that doesn't sit on one scale, elements that don't share a
baseline or an edge, hit areas smaller than the thing they belong to, hover/focus/active
states that were never defined, text that truncates badly, numbers that jump because
they're not tabular, layout shift on load — and then borders versus shadows, harsh
dividers, nested radii that don't sit concentrically, elevation that doesn't mean anything,
and surfaces that fall apart in dark mode.

Repeated things get checked as one object: cards in a row, rows in a list, badges on
siblings — same inner padding, same edges, same baselines, each from the last. Inconsistency
between siblings reads as carelessness faster than any single wrong value does.

If either pass keeps surfacing hierarchy or rhythm problems rather than local ones, the
spacing system itself is the problem: invoke `emil-design-foundations` once and fix it
there. Do not do this reflexively — only when the findings say so.

**4b — Critique.** `emil-ui-review`. Does this read, does the hierarchy hold, is the copy
right. The design question, now that nothing obvious is in the way of it.

**4c — Readiness.** `emil-prep-for-prod`. The sweep that catches what a critique doesn't
look for: blank empty and error states, a dark mode nobody opened, removed focus rings,
div-buttons, layout shift, leftover `console.log` and lorem. Two of its lanes do not apply
to an internal Infrahub screen — marketing and SEO — so ignore those and say you did.
Everything else applies, because this prototype gets demoed live, and a demo is a launch
with a smaller audience.

**4d — By hand.** The four below, which no skill checks for you.

For each finding from any pass: fix it, or write down why you're accepting it. No third
option.

Then check these yourself, because they are the ones that embarrass a demo:

- Tab from the top. Is the order sane and the focus ring visible?
- Dark mode. Actually look, don't assume.
- Phone width. No sideways scroll. If the brief said phone, re-run `emil-mobile-native`
  here against the finished screen and check it on real hardware, not device emulation —
  emulation does not reproduce tap latency, the keyboard, or how a thumb actually reaches.
- Every state from phase 3 still renders.

Write `04-review.md`: findings, fixed or accepted, with reasons, grouped by pass.

### The gate

**Phase 5 does not start while a finding is unresolved.** Every one is fixed, or accepted
with a reason someone else could disagree with — "accepted: the empty state is out of scope
for this design, tracked as a gap" is a decision; silence is not.

Say the gate is clean, in those words, at the checkpoint. The lift sheet in phase 5 tells
someone to copy this code into production; a screen that goes through that door with known
mess in it spends the mess forever, because nobody re-reviews code that arrived approved.

## Phase 5 — Hand off

Only after the phase-4 gate is clean. If it isn't, go back — do not publish a design doc
that says "ready to implement" over a screen with open findings.

Publish a design doc as an Artifact — a private page with a URL the user can share. This is
the deliverable. It is what gets discussed, argued with, and approved before anyone opens
an implementation ticket.

It contains, in this order:

1. **What and why** — the brief, in the user's words.
2. **The proposal** — the chosen direction, with screenshots of each real state, and the
   live prototype URL.
3. **What we rejected, and why** — one paragraph per direction from `02-directions.md`.
   This is the section people actually respond to.
4. **Decisions** — from `03-decisions.md`, so reviewers argue with reasons, not taste.
5. **Open questions** — what the user still has to decide, listed as questions.
6. **System gaps** — the `Missing` list from `01-system.md`, as the work this design
   creates beyond itself.
7. **How it got here** — the rejected variants and every earlier revision, as live
   `dj.variant` / `dj.rev` links, plus the one-line `git log` command that shows the
   reasoning over time. A reviewer who wants to know why it stopped looking like rev 2 can
   go and look instead of asking.

Write the **whole document** to `05-handoff.md` first, then publish that content as the
Artifact and add the URL at the top of the file. The published page is the convenient way
to read it; the markdown in the repo is the copy that survives. A link can rot, sit behind
an org boundary, or outlive the account that made it, and a handoff whose substance exists
only outside the repo is a handoff the repo cannot answer questions from later.

Save the screenshots into `.design/<slug>/shots/` rather than only embedding them. They are
what the visual record reduces to once the prototype route is gone.

Then give the user the link and the single sentence they should paste above it.

### The design PR — opened in phase 2, approved in phase 5

Open a **draft** PR at the end of phase 2, so reviewers have a preview link and a place to
post notes. At phase 5, replace its body with `05-handoff.md`, set `status: awaiting
approval` in `STATE.md`, and stop. The design PR is never merged: approval on it is the
decision to implement. Base, title, labels, the draft check and the preview link are in
[`reference/design-pr.md`](reference/design-pr.md).

### `05-implement.md` — the lift sheet

Write `05-implement.md` so implementation starts by copying the approved revision to its
real home, not by rebuilding it from a description. Its four lists, the implementation
branch and the teardown checklist are in
[`reference/implementation.md`](reference/implementation.md).

## Phase 6 — Improve the skill and the docs

Run this after the phase-5 checkpoint, and again at teardown if the implementation turned
up more. Every run finds something that slowed it down, and if nobody writes it down the
next run hits it too.

Go through `STATE.md`, the `feedback/` files, `git log .design/<slug>/` and this
conversation, and list each place where the run had to work around something. Put each one
in exactly one bucket:

- **This skill** — a rule that was wrong, missing or ignored; a panel or notes-store bug; a
  preflight check that should have caught something. Fix target: `.agents/skills/design-jam/`.
- **A skill it invokes** — a pass that gave advice that did not fit Infrahub. Record it only;
  the `emil-*` skills are not in this repo.
- **Internal docs** — a frontend fact the run had to discover from code because
  `frontend/app/AGENTS.md`, `dev/guidelines/frontend/` or `dev/knowledge/` did not say it.
  Follow `dev/guidelines/documentation.md` for where it goes.
- **`@infrahub/ui`** — already in the `Missing` list of `01-system.md`; link it, do not repeat it.

Write `06-improvements.md`: one line per finding, its bucket, and the edit you propose.
Show it to the user and apply only what they approve. Make the edits on a new branch off
`develop`, never on the design branch, because the design PR is never merged and anything
committed to it is lost. Open that PR with the repo's `pr` skill and add its URL to
`06-improvements.md`.

A run with no findings writes that in one line. "Nothing to improve" and "nobody checked"
are different things.
