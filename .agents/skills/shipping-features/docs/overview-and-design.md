# Shipping Features — overview & design

> A short brief for discussing the `shipping-features` skill with the team.
> Companion to the skill itself (`../SKILL.md`) and its phase references (`../phases/`).

## The problem it solves

Shipping a change end to end means touching many tools — Jira, spec, plan, code, tests,
review, CI, PR — and today that means the developer (and the agent) constantly asks:

> *"Where am I? Which step is done? Which skill do I run next?"*

`shipping-features` exists to make that question disappear. It is a **conductor**: it doesn't
re-implement spec/plan/review/PR logic, it **orchestrates the tools we already have** and keeps a
durable record of where the work stands so anyone — or any session — can pick it up.

## Three ideas, in one paragraph each

**1. Classify first.** Every run opens by classifying the work along three axes — **type**
(bug / feature / chore), **size** (S / M / L), and optional **risk flags** (irreversible,
security, cross-team, crux-algorithm). The agent proposes a classification; the user confirms it
at a checkpoint. This picks the *lane* (a bug goes `bug-analyze → bug-tdd → bug-fix`; a feature
goes `grilling-ideas → spec → plan → implement`) and the *depth* (an S fix skips specs entirely; an L
feature gets the full treatment). One workflow, shaped to the work.

**2. A durable manifest (`ship.md`).** Each unit of work gets a `ship.md` inside its speckit
feature dir (`specs/NNN-slug/`) — the single source of truth. It records the classification, the
selected phase list with per-phase status (`todo / in-progress / done / skipped`), and links to
every artifact (`spec.md`, `plan.md`, `review.md`, the PR URL). Re-running the skill scans for an
unfinished `ship.md`, prints a **status board**, and resumes at the first unfinished phase — so
pause/resume/redirect is free, and survives across sessions and machines. Before trusting a
`done` phase on resume it **reconciles** the manifest against the repo (branch state, artifacts,
tests) so it never ships stale state.

**3. A layered reliability model.** Parallelism alone doesn't make results *reliable* — it makes
them *better at design forks*. Reliability comes from three independent layers:
- **Gate** — every phase has deterministic exit-criteria; it can't be marked `done` until they pass.
- **Parallel divergence** — multiple framings + a synthesizer, but only at genuine design forks
  (spec, plan) and only on M/L.
- **Adversarial verify** — a skeptic agent tries to *refute* a correctness claim (implement, review).

These sit at opposite ends of the pipeline (divergence before work exists; verification after a
claim exists), so they rarely stack on one phase. All three stack **only** when a risk flag makes
the extra cost worth it — because parallel agents share priors and can share a blind spot, and a
skeptic breaks that correlated error. The user confirms the risk flag; the model doesn't guess it.

## Artifacts as the interface between steps

Every phase **reads** the upstream artifacts named in `ship.md` and **writes** its own artifact
back. Nothing is re-derived from scratch. This makes the flow inspectable (open the feature dir and
read the story), shareable (hand someone the dir), and resumable (the artifacts + `ship.md` are the
whole state).

```
specs/001-user-auth/
  ship.md        ← manifest: classification, phase status, artifact links
  spec.md        ← phase 2 (feature)  |  analysis.md ← phase 2 (bug)
  plan.md
  tasks.md
  review.md      ← phase 5
  retrospective.md ← phase 6
  → PR URL recorded in ship.md (phase 8), CI status (phase 9)
```

## Reuse over reimplementation

The skill's core rule. Each capability resolves through a priority chain
(**in-repo skill/command → marketplace plugin → built-in fallback**), so it works in any repo and
gets better as more tools are installed. These all ship in-repo under `.agents/`:
`creating-issues`, `creating-prd`, `grilling-ideas`, `/bug-analyze`·`/bug-tdd`·`/bug-fix`, the
`speckit-*` suite (including `speckit-review-{code,tests,types,errors,comments,simplify}` and
`speckit-critique-run`), `pruning-residues` (post-implement cleanup of dead code, debug logs, and
redundant comments), `capturing-knowledge`, `learning-from-review` (distills review lessons),
`/audit-docs`·`/add-docs` (docs-consistency audit), `rebase`, `commit`, `pr`,
`monitoring-pull-requests` (post-open CI watch), and `speckit-opsmill-retrospect` (retrospective,
run at the knowledge step).

## The pipeline at a glance

| # | Phase | Delegates to | Reliability layers |
|---|---|---|---|
| 0 | Classify | (this skill) | checkpoint |
| 1 | Ticket & branch | `creating-issues`, `/speckit-git-feature` | gate |
| 2 | Understand | `/bug-analyze` / `grilling-ideas`+`/speckit-specify` | gate (+ parallel on feature M/L) |
| 3 | Plan | `/speckit-plan`+`/speckit-tasks` | gate + parallel (+ skeptic on risk) |
| 4 | Implement | `/bug-tdd`+`/bug-fix` / TDD agents · prune residues | gate + adversarial verify |
| 5 | Review | `speckit-review-run`, `coderabbit`, `/security-review` | gate + parallel + verify |
| 6 | Knowledge, learning & retrospective | `capturing-knowledge` + `learning-from-review` + `speckit-opsmill-retrospect` + `/audit-docs`→`/add-docs` | conditional |
| 7 | CI gate | `/pre-ci` | gate |
| 8 | Commit & PR | `commit`, `pr`, split assessment | parallel (split) |
| 9 | CI watch | `monitoring-pull-requests` | gate |

Checkpoints sit between phases; the user can pause, redirect, reclassify, or jump at any of them.
**Two cleanups keep it consistent:** code residues + stale comments at phase 4 (`pruning-residues`),
docs & knowledge at phase 6 (`capturing-knowledge` + `/audit-docs`).

## Open questions for the team

- Is `specs/NNN-slug/` the right home for `ship.md`, or should bug/chore work (which may skip
  speckit) use a lighter location?
- Which risk flags actually earn stacked verification in our codebase? Are four too many/few?
- Should phase 9 (CI watch) block the "done" state, or just report?
- What's the right default size→depth mapping — is `L` too eager to spin up worktrees + 3–4 agents?

## Status

Draft skill on branch `ple-test-shipping-features-skill`, rebased onto latest `develop` so every
in-repo tool it delegates to resolves today. A first **pressure-test pass** held: fresh agents kept
the rules — resume-scan on empty input, classify-don't-over-engineer under time pressure, refuse a
red CI gate, and never mark a phase done without its gate — under "we're late, skip it" pressure.
A fuller RED→GREEN→REFACTOR pass is still worthwhile before heavy use.
