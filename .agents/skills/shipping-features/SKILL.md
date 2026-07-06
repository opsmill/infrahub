---
name: shipping-features
description: >-
  Use when the user says "ship this feature", "run shipping-features", names a
  ticket/feature/bug and asks to drive it end to end, or asks "where am I / what's
  next" on in-progress work. Do not use for a single isolated step (just a spec,
  just a review, just a PR) — invoke that step's tool directly. Orchestrates a
  classified, manifest-driven, resumable pipeline that reuses existing tools.
argument-hint: "<ticket-id or short description> (empty resumes in-progress work)"
---

# Shipping Features

## User Input

```text
$ARGUMENTS
```

`$ARGUMENTS` is a ticket ID or short feature description. **If empty, do not ask
what to build yet — first run the resume scan** (see Manifest & resume): an
unfinished `ship.md` means the user is asking "where am I / what's next."

## What this does

End-to-end **conductor** for one unit of work — feature, bug, or chore — from idea
to merged-ready PR (and post-open CI watch). It **composes existing tools**: the
project's own commands, sibling `opsmill-software` skills, marketplace plugins
(superpowers, coderabbit, commit-commands) when present, and built-in agents as the
always-works fallback. It reimplements **nothing**.

Its only original contributions are four orchestration primitives:

1. **Classification** — every run opens by classifying the work (type × size + risk),
   which selects the lane and the depth. See [phases/classification.md](phases/classification.md).
2. **A durable manifest** (`ship.md`) — the single source of truth for "where am I",
   living in the speckit feature dir. See [phases/manifest.md](phases/manifest.md).
3. **A reliability model** — gates everywhere, parallel divergence at design forks,
   adversarial verification at correctness claims, stacked only on risk. See
   [phases/reliability.md](phases/reliability.md).
4. **Human checkpoints** between phases, so you can pause, redirect, and resume.

## Core principles

- **Reuse over reimplementation.** Every phase delegates to an existing tool. Reinvent nothing.
- **Classify first, then adapt.** An `S` bug and an `L` feature must not walk the same path.
- **The manifest is the source of truth.** No phase runs, completes, or resumes without
  reading and updating `ship.md`. The user should never have to ask "which step am I on."
- **Gate every phase.** A phase is `done` only when its exit-criteria pass — deterministically.
- **Reliability is layered, not just parallel.** Parallelism improves *quality* at forks;
  gates and adversarial verification produce *correctness*. Stack all three only on risk.
- **Stop at checkpoints.** The user approves between phases. Never chain phases unattended.
- **Degrade, never block.** A missing optional tool lowers quality; it never stops the flow.

## Recommended companion plugins (optional)

Built-in fallbacks cover every phase without these. Install from the official marketplace
with `claude plugin install <name>` (or the `/plugin` menu).

| Plugin | Powers | Tier |
|---|---|---|
| `opsmill-software` | sibling skills: grill-idea, create-issue, bug-*, commit, pr, pr-monitor, rebase, capturing-knowledge | **Recommended** |
| `superpowers` | planning, TDD, worktrees, parallel agents, review wrappers, verification | **Recommended** |
| `coderabbit` | AI correctness/security code review | **Recommended** |
| `commit-commands` | conventional commit, push, PR | Nice-to-have |
| `code-simplifier` | simplification pass on the diff | Nice-to-have |

## Preflight: check companions once (non-blocking)

Before phase 1, probe for the companions above **once**. If any are missing, print a single
consolidated note naming what's absent and the install command, then **proceed immediately**
with built-in fallbacks. Do not prompt, wait, re-suggest, or auto-install.

> **Sibling availability caveat:** `opsmill-software:pr` and `pr-monitor` resolve only after
> this branch is rebased onto `main` (imported in opsmill-software PR #27). Until then the
> `gh` / `commit-commands` fallbacks in the discovery table cover the PR and CI-watch rows.
> Probe as normal — they light up automatically once present.

## Discover available context (probe → reuse → fall back)

For each capability, use the first available source in priority order. Probe; never invent a
command the project lacks; surface ambiguity to the user.

| Capability | 1. Host repo command | 2. opsmill sibling | 3. Marketplace plugin | 4. Built-in fallback |
|---|---|---|---|---|
| Ticket/issue | — | `create-issue` | — | skip |
| Ticket→branch (Jira/JPD) | `/speckit-git-feature` | — | — | `git checkout -b` |
| Idea hardening | — | `grill-idea` | `superpowers:brainstorming` | ask 2–3 questions inline |
| Bug root-cause | — | `bug-analyze` | — | `Explore` agents on the failing surface |
| Spec (divergent) | — | — | — | `Explore` agents |
| Spec (formalize) | `/speckit-specify`, `/speckit-clarify` | — | — | keep the synthesized brief |
| Plan (divergent) | — | — | — | `Plan` agents |
| Plan (formalize) | `/speckit-plan`, `/speckit-tasks` | — | `superpowers:writing-plans` | inline ordered task list |
| Implement (bug, TDD) | — | `bug-tdd` → `bug-fix` | `superpowers:test-driven-development` | `general-purpose` agent, test-first |
| Implement (feature, TDD) | — | — | `superpowers:test-driven-development` | `general-purpose` agents, test-first |
| Worktree isolation | — | — | `superpowers:using-git-worktrees` | `isolation: "worktree"` on Agent calls |
| Parallel execution | — | — | `superpowers:subagent-driven-development` / `dispatching-parallel-agents` | parallel Agent calls in one message |
| Code review | — | — | `coderabbit:code-review`, `code-simplifier`, `superpowers:requesting-code-review` | `general-purpose` reviewers + `/security-review` |
| Knowledge capture | — | `capturing-knowledge` | — | skip |
| Branch update / rebase | — | `rebase` | — | `git rebase`/`git merge` base |
| CI gate / verify | `/pre-ci` | — | `superpowers:verification-before-completion` | run detected test + lint commands |
| Commit | `/git-commit` | `commit` | `commit-commands:commit` | `git commit` (conventional message) |
| PR | `/git-pr` | `pr` | `commit-commands:commit-push-pr`, `superpowers:finishing-a-development-branch` | `gh pr create` |
| Post-open CI watch | — | `pr-monitor` | — | `gh run watch` / skip |

## Reliability model (read before phase 1)

Three layers, applied per phase, scaled by size, stacked only on risk. Full rules and the
risk-triggered stacking table are in [phases/reliability.md](phases/reliability.md). In brief:

- **Gate (always):** every phase declares exit-criteria checked *before* its checkpoint. No
  green criteria → not `done` in `ship.md`.
- **Parallel divergence (design forks):** spec & plan on `M`/`L`. Multiple *framings*, then one
  synthesizer. Never on deterministic phases; never as N copies of the same prompt.
- **Adversarial verify (correctness claims):** after implement & review, a skeptic agent tries
  to *refute* the claim ("this doesn't fix it", "this finding is a false positive").
- **Stack all three** on a phase only when a **risk flag** (`irreversible | security | cross-team
  | crux-algorithm`) is set at classification — the user confirms it, the model does not guess it.

## Classification (phase 0 — opens every run)

Follow [phases/classification.md](phases/classification.md): propose `type` (bug / feature /
chore), `size` (S / M / L), and any `risk` flags from the ticket text and diff surface; the user
confirms or overrides at a checkpoint. Write the confirmed values to `ship.md`. **Never re-ask on
resume** — the manifest already holds them.

The lane and depth follow from the classification:

| Phase | `bug` | `feature` | `chore` |
|---|---|---|---|
| Ticket/branch | `create-issue` → `/speckit-git-feature` | same | same |
| Understand | `bug-analyze` → `analysis.md` | `grill-idea` → `/speckit-specify` → `spec.md` | short inline brief |
| Plan | skip on `S`, else light | `/speckit-plan` + `/speckit-tasks` → `plan.md`, `tasks.md` (`M`/`L`) | skip |
| Implement | `bug-tdd` → `bug-fix` | TDD agents (worktrees on `L`) | direct edit |
| Review | review tool → `review.md` + verify | same | same (lighter) |
| Knowledge | `capturing-knowledge` (conditional) | same | same |
| CI gate | `/pre-ci` | same | same |
| Commit | `commit` sibling | same | same |
| PR | `pr` sibling → split assessment | same | same (usually single PR) |
| CI watch | `pr-monitor` | same | same |

`S` runs its lane straight through (gate + one verify, no parallelism). `M`/`L` light up the
parallel front-end and, on a risk flag, the stacked verify.

## Manifest & resume

`ship.md` lives in the speckit feature dir (`specs/NNN-slug/`, located via `.specify/feature.json`).
It records classification, the selected phase list, per-phase status, and links to every artifact.
Follow [phases/manifest.md](phases/manifest.md) for its schema, the update contract, and the
**resume + reconcile** logic (re-invoking the skill scans for an unfinished `ship.md`, prints a
status board, reconciles claimed-`done` phases against reality, and continues at the first
unfinished phase).

## Phases

Each phase below: **delegates to** a discovered tool, **reads** the upstream artifacts named in
`ship.md`, **writes** its own artifact back, runs its **gate**, then **checkpoints**. Update
`ship.md` at every transition.

### Phase 0 — Classify
Per [phases/classification.md](phases/classification.md). Create `ship.md` (or resume an existing
one). **Checkpoint:** user confirms type / size / risk before any work.

### Phase 1 — Ticket & branch
If no ticket and the project tracks issues, offer `create-issue`. Create the feature branch via
`/speckit-git-feature` (validates Jira/JPD ref, names the branch) or `git checkout -b` fallback.
Record ticket + branch in `ship.md`. **Gate:** on a named branch, not the base branch.

### Phase 2 — Understand
- **bug:** `bug-analyze` → `analysis.md` (root cause + repro). **Gate:** a concrete repro exists.
- **feature:** harden with `grill-idea` if fuzzy; **diverge** (3 `Explore` framings: existing
  patterns / related entities & APIs / test-coverage gaps) → **synthesize** 1 brief; formalize
  with `/speckit-specify` (+`/speckit-clarify`) → `spec.md`. **Gate:** no unresolved
  `[NEEDS CLARIFICATION]`.
- **chore:** short inline brief. **Gate:** scope stated in one paragraph.
**Checkpoint:** show the artifact + open questions.

### Phase 3 — Plan (feature `M`/`L`; skipped otherwise)
**Diverge** (3 `Plan` framings: minimal / refactor-friendly / test-first) → **synthesize** one
ordered task list; formalize with `/speckit-plan` + `/speckit-tasks` → `plan.md`, `tasks.md`.
On a risk flag, add a skeptic pass on the synthesis (see reliability). **Gate:** every task
references files that exist; plan cites the spec. **Checkpoint:** merged plan + tradeoffs.

### Phase 4 — Implement
- **bug:** `bug-tdd` (failing test) → `bug-fix`.
- **feature/chore:** group `tasks.md` into independent units; run TDD agents (worktree isolation
  on `L`); independent units in parallel (one message), dependent units sequentially.
Verify the real diff, never the self-report. **Gate + adversarial verify:** a test that was red is
now green *and* a skeptic agent fails to refute "this actually implements the spec/fixes the bug."
**Checkpoint** only if a blocker surfaces or on `L`.

### Phase 5 — Review (pre-PR)
**Diverge** across available review tools in parallel (`coderabbit:code-review`, `code-simplifier`,
`/security-review`; fallback: 2–3 framed `general-purpose` reviewers) → **synthesize** a
severity-ranked fix list (blocker / nit / suggestion) → **adversarial verify** each finding is real
before acting. Wrap with `superpowers:requesting-code-review` / `receiving-code-review` when present.
Write `review.md`. **Gate:** zero unaddressed blockers. **Checkpoint:** ranked list, then fix pass
(small parallel agents per file group).

### Phase 6 — Knowledge capture (opportunistic)
Delegate to `capturing-knowledge` (no args). Skip silently if nothing genuinely new was learned —
empty captures are a feature. If docs change, they join this PR. **Checkpoint** only if it proposes
doc changes.

### Phase 7 — CI gate (must-pass before PR)
Run `/pre-ci` (or `superpowers:verification-before-completion`, or detected test+lint commands —
never invented). Red → loop back to the phase 5 fix pass. **Do not proceed with a red gate.**
**Checkpoint:** results.

### Phase 8 — Commit & PR
1. **Commit** any final drift with `/git-commit` → `commit` sibling → `commit-commands:commit` →
   `git commit`. By now work was committed iteratively in phase 4; do not auto-commit to satisfy a
   command — surface a dirty-tree refusal instead.
2. **Split assessment** (bias toward single PR) per [phases/pr-split.md](phases/pr-split.md).
   **Checkpoint:** user picks single / accepts split / proposes another. Never force a split.
3. **Open** each approved PR with `/git-pr` → `pr` sibling → `commit-commands:commit-push-pr` →
   `superpowers:finishing-a-development-branch` → `gh pr create`. For split PRs prepend
   `Depends on #<sibling>` and open in dependency order. Record PR URL(s) in `ship.md`.

### Phase 9 — Post-open CI watch
Delegate to `pr-monitor` (or `gh run watch`) to watch the opened PR's CI. On red, surface the
failure and loop back to phase 5's fix pass. Record final CI status in `ship.md`. Skip cleanly if
no watch tool resolves. **Terminal checkpoint:** green CI + PR URL(s) → done.

## Anti-patterns

- ❌ Asking "what should I build?" when `$ARGUMENTS` is empty — run the resume scan first.
- ❌ Running or completing a phase without reading/updating `ship.md`.
- ❌ Marking a phase `done` without its exit-criteria gate passing.
- ❌ Trusting a claimed-`done` phase on resume without reconciling it against the branch.
- ❌ Running the same lane for a bug and an L feature.
- ❌ Skipping the synthesizer between parallel agents; or feeding N framings into N implementers.
- ❌ Stacking all three reliability layers on a phase with no risk flag.
- ❌ Reimplementing anything in the discovery table, or inventing a command the project lacks.
- ❌ Blocking on a missing optional plugin, re-suggesting it every phase, or auto-installing it.
- ❌ Opening a PR with a red CI gate; forcing a PR split when the changes are coupled.
