# Shipping Features — overview & design

> A short brief for discussing the `shipping-features` skill with the team.
> Companion to the skill itself (`../SKILL.md`) and its phase references (`../phases/`).

## The problem it solves

Shipping a change end to end means touching many tools — Jira, spec, plan, code, review, CI, PR —
and today the developer (and the agent) constantly asks:

> *"Where am I? Which step is done? Which command do I run next?"*

`shipping-features` makes that question disappear. It is a **conductor**: it does not reimplement the
delivery pipeline, it **orchestrates the OpsMill 5-stage framework we already have** and keeps the
state in the artifacts' natural homes so anyone — or any session — can pick it up.

## The five stages (framework) + the orchestration layer (this skill)

The stages and their tools already exist. This skill adds a thin **orchestration layer** on top.

| # | Stage | Canonical tools | Output → home | Orchestration at the seam |
|---|---|---|---|---|
| 1 | **Intake** | `creating-issues` · `grilling-ideas` · `creating-prd` | issue + PRD → **GitHub / Jira** | classify type×size×risk; open `ship.md` index; gate: clear scope; checkpoint → propose Jira *In design* |
| 2 | **Prep** | `/speckit-opsmill-prep` (specify→plan→critique→tasks) *or granular on M/L* | spec·plan·tasks → **`specs/<feature>/`** | parallel framings on `L`; gate: tasks + alignment clean; checkpoint per decision |
| 3 | **Implement** | `/speckit-opsmill-implement` (preflight→clean-context subagents→review-run→report) *· bug: `/bug-tdd`→`/bug-fix`* | code + `opsmill-implement-report.md` | verify: adversarial skeptic on the report; gate: tests green; checkpoint: fixes accepted |
| 4 | **Delivery** | `/pre-ci` · `/pr` · `/pr-monitor` · `/qa` | PR + CI → **GitHub PR** | gate: CI green before PR; parallel split assessment; checkpoint → propose Jira *In review* |
| 5 | **Extract** *(manual)* | `/speckit-opsmill-extract` (+ `capturing-knowledge`, `retrospect`) | knowledge·guidelines·ADR → **`dev/…`** | manual gate: review report first; checkpoint on doc changes → propose Jira *Done* |

## Five orchestration ideas

**1. Single entry point.** One skill to run. It classifies the work, tells you where you are, and
offers the next command — so you never juggle which tool comes next.

**2. Classify first, adapt depth.** Every run opens by classifying `type × size × risk`. Type picks
the lane (a **bug takes a lighter lane** — `bug-analyze → bug-tdd → bug-fix`, skipping heavy Prep); size
picks the depth. **The `speckit-opsmill-*` meta-commands run hands-off internally**, so we use them
whole on size `S` (fast path) but drive the **granular** speckit skills on `M`/`L` so the user
checkpoints each decision.

**3. Checkpoints = verify & accept.** The point of the seams is that *you* approve each meaningful
decision before the next stage. It never runs a whole stage unattended unless you pick the `S` fast-path.

**4. Reliability is layered, not just parallel.**
- **gate** — deterministic exit-criteria on every stage; can't be `done` until they pass.
- **parallel** — several framings + a synthesizer, only at design forks (specify/plan) on `M`/`L`.
- **verify** — a skeptic tries to *refute* a correctness claim (after implement & review).
All three stack on one stage **only** under a risk flag (security, irreversible, …) — the user confirms it.

**5. External single source of truth.** Inputs/outputs live in their **natural homes** — progress in
**Jira**, design in **`specs/`**, the build in the **implement report**, knowledge in **`dev/` docs**,
delivery in the **PR**. `ship.md` is a thin **index** of pointers + per-stage status, not a copy.
Resume reads the index and **reconciles against the live sources** (Jira status, PR state, files) —
the source always wins. Jira transitions are **proposed at the checkpoint and applied only on accept**,
never automatically.

## What this replaces

The earlier draft had its own 10-phase pipeline that partly re-derived what the framework already
consolidated. This version **collapses onto the 5 framework stages** and delegates the heavy lifting to
the `speckit-opsmill-*` meta-commands, keeping only the orchestration (classify · gate · parallel ·
verify · checkpoints · index) as its own contribution.

## Open questions for the team

- Is `specs/<feature>/` the right home for the `ship.md` index, or should bug/chore work use a lighter spot?
- Which risk flags actually earn stacked verification in our codebase?
- How far should Jira automation go — propose-on-accept only, or auto-transition on trusted stages?
- Is the size→depth split right — is `S` too eager to go hands-off via the meta-commands?

## Status

Draft skill on branch `ple-test-shipping-features-skill` (PR #9873), rebased onto latest `develop` so
the framework tools it delegates to resolve today. `harvesting-review` is **merged in `stable`** in PR
#9922; this skill references it as an optional Extract-stage step and degrades cleanly when it's absent.
A first pressure-test pass held (resume on empty input, classify-don't-over-engineer under time
pressure, refuse a red CI gate); a fuller RED→GREEN→REFACTOR pass is still worthwhile before heavy use.
