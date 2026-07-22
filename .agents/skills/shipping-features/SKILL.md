---
name: shipping-features
description: >-
  Use when the user says "ship this feature", "run shipping-features", names a
  ticket/feature/bug and asks to drive it end to end, or asks "where am I / what's
  next" on in-progress work. Do not use for a single isolated step (just a spec,
  just a review, just a PR) — invoke that step's tool directly. Orchestrates the
  OpsMill 5-stage delivery framework with classification, gates, and human checkpoints.
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

**Single entry point** for delivering one unit of work — feature, bug, or chore — across the
**OpsMill 5-stage framework**: **Intake → Prep → Implement → Delivery → Extract**. It is a
**conductor**, not a new pipeline: the five stages and their tools already exist; this skill adds
the **orchestration layer** on top so you never have to ask *"where am I, which command runs next?"*

It reimplements **nothing**. The orchestration layer contributes exactly five things:

1. **Classification** — every run opens by classifying `type × size × risk`, which picks the *lane*
   and the *depth* (how many steps, how many checkpoints). See [phases/classification.md](phases/classification.md).
2. **Reliability at the seams** — **gate** (every stage), **parallel** (design forks), **verify**
   (correctness claims), stacked only on risk. See [phases/reliability.md](phases/reliability.md).
3. **Human checkpoints** — you **verify and accept** each meaningful decision. It never runs a whole
   stage unattended unless you opt into the hands-off fast-path.
4. **External single source of truth** — inputs and outputs live in their **natural homes** (Jira,
   `specs/`, the implement report, `dev/` docs, the PR), not inside the skill. `ship.md` is a thin
   **index** pointing at them. See [phases/manifest.md](phases/manifest.md).
5. **Next-step help** — at each checkpoint it tells you (and offers to run) the next stage's command.

## Core principles

- **Reuse over reimplementation.** Every stage delegates to an existing skill/command. Reinvent nothing.
- **Classify first, then adapt.** An `S` bug and an `L` feature must not walk the same path.
- **Single source of truth is external.** Each artifact has one canonical home; `ship.md` only points.
  No phase runs, completes, or resumes without reading/updating that index.
- **Checkpoints mean verify & accept.** Stop between stages so the user approves decisions. Never
  chain a whole stage unattended — except the size-`S` hands-off fast-path, chosen explicitly.
- **Gate every stage.** A stage is `done` only when its exit-criteria pass — deterministically.
- **Reliability is layered, not just parallel.** Parallelism improves *quality* at forks; gates and
  adversarial verification produce *correctness*. Stack all three only on a risk flag.
- **Degrade, never block.** A missing optional tool lowers quality; it never stops the flow.

## The five stages

Framework vocabulary on top; canonical tools do the work; the orchestration column is what this
skill adds **at the seam** between stages.

| # | Stage | Canonical tools (do the work) | Output → external home | Orchestration added at the seam |
|---|---|---|---|---|
| 1 | **Intake** | `creating-issues`/`/create-issue` · `grilling-ideas`/`/grill-idea` · `creating-prd`/`/create-prd` | issue + PRD → **GitHub / Jira (JPD)** | **classify** type×size×risk; open `ship.md` index; **gate:** issue w/ clear scope; **checkpoint:** scope accepted → propose Jira *In design* |
| 2 | **Prep** | `/speckit-opsmill-prep` = specify → plan → critique-run → tasks + alignment check *(or the granular skills on M/L)* | spec · plan · tasks → **`specs/<feature>/`** | **parallel** framings into specify/plan on `L`; **gate:** `tasks.md` exists, alignment clean, no `[NEEDS CLARIFICATION]`; **checkpoint** after each design decision |
| 3 | **Implement** | `/speckit-opsmill-implement` = preflight → implement (↻ clean-context subagents) → review-run → report *(bug lane: `/bug-tdd` → `/bug-fix`)* | code + `opsmill-implement-report.md` → **`specs/<feature>/`** + git | **verify:** adversarial skeptic on the report + high-sev findings; **gate:** report clean + tests green; **checkpoint:** findings & fixes accepted |
| 4 | **Delivery** | `/pre-ci` · `/pr` · `/pr-monitor` · review (spec & code) · `/qa` | PR + CI → **GitHub PR** | **gate:** CI green before PR; **parallel** split assessment ([phases/pr-split.md](phases/pr-split.md)); **checkpoint:** PR plan accepted → propose Jira *In review*; monitor loops back on red |
| 5 | **Extract** *(manual)* | `/speckit-opsmill-extract` (+ `harvesting-review`¹, triggered from the Stage 4 review loop) | knowledge · guidelines · ADR → **`dev/…`**; archive spec | **manual gate:** you review the report first; session-bound tools (`speckit-opsmill-retrospect`, `capturing-knowledge`) run at the Stage 4 checkpoint, not here; **checkpoint** on doc changes → propose Jira *Done* |

¹ `harvesting-review` is merged in `stable` (PR #9922); use it when present, skip cleanly when absent.

## Orchestration layer

### Classification (opens every run)
Follow [phases/classification.md](phases/classification.md): propose `type` (bug / feature / chore),
`size` (S / M / L), and any `risk` flags; the user confirms at a checkpoint. Written to `ship.md`.
**Never re-ask on resume.** Classification picks both the **lane** and the **depth**:

| | Intake | Prep | Implement | Delivery | Extract |
|---|---|---|---|---|---|
| **bug** *(light lane)* | issue | `/bug-analyze` → ✓ root cause | `/bug-tdd` → `/bug-fix` (gate red→green + verify) | CI → `/pr` → `/pr-monitor` | usually skip |
| **S** | quick | `/speckit-opsmill-prep` hands-off → 1 ✓ | `/speckit-opsmill-implement` hands-off → verify report | CI → PR | manual, light |
| **M** | issue + scope ✓ | specify ✓ · plan + tasks ✓ | implement → review + verify ✓ | CI ✓ · PR ✓ | extract ✓ |
| **L** | issue + PRD ✓ | specify ✓ · plan ✓ · **parallel** critique · tasks ✓ | chunked implement (clean-context) · verify ✓ | CI ✓ · **split** assess ✓ · PR · monitor | extract + retrospect ✓ |

✓ = human checkpoint. **The meta-commands run hands-off internally** — use them whole on `S` (or when
the user says "just run it"); on `M`/`L` drive the **granular** skills so the user checkpoints each
decision. Bugs take the lightest lane; `L` gets the most stops plus parallel/verify.

### Reliability (gate · parallel · verify)
Per [phases/reliability.md](phases/reliability.md), applied per stage, scaled by size, stacked only on risk:
- **Gate (always):** exit-criteria checked *before* the checkpoint. No green → not `done` in `ship.md`.
- **Parallel (design forks):** specify/plan on `M`/`L` — multiple framings, one synthesizer. Never on
  deterministic steps; never N copies of one prompt.
- **Verify (correctness claims):** after implement & review, a skeptic tries to *refute* the result.
- **Stack all three** on a stage only under a **risk flag** (`irreversible | security | cross-team |
  crux-algorithm`) — the user confirms it; the model never guesses it.

### Jira / progress (propose-on-accept)
When a Jira/JPD ticket is linked and Atlassian tools are available, at each stage checkpoint **propose**
the status transition (and a PR/artifact link comment) and **apply it only when the user accepts** —
never auto-transition. If Jira is absent, record status in the `ship.md` index only.

## Per-stage detail

### Stage 1 — Intake
Restate the ask in one sentence; classify (checkpoint). If no ticket and the project tracks work,
offer `creating-issues` / `/create-issue`; harden a fuzzy idea with `grilling-ideas` / `creating-prd`.
**Pick the base branch deliberately:** before cutting, verify the code the ticket references
actually exists on the intended base (`git ls-tree <base> -- <path>`) — follow-up tickets often
reference modules that only exist on the integration branch (e.g. `develop`), not the default
branch. Then cut via `/speckit-git-feature` (validates Jira/JPD ref) or `git checkout -b`. Open the
`ship.md` index (feature id, issue, branch). **Gate:** issue with clear scope, on a named branch
whose base contains the referenced code. **Checkpoint:** scope accepted → propose Jira *In design*.

### Stage 2 — Prep
- **S (or opt-in):** `/speckit-opsmill-prep` hands-off → one checkpoint on the resulting `tasks.md`.
- **M/L:** drive the granular skills with a checkpoint after each decision — `/speckit-specify` → ✓,
  `/speckit-plan` → ✓ (on `L`, **parallel** framings feed it), `speckit-critique-run` (gate),
  `/speckit-tasks` → ✓. Outputs land in `specs/<feature>/`.
**Gate:** `tasks.md` exists, alignment check clean, no unresolved `[NEEDS CLARIFICATION]`.

### Stage 3 — Implement
- **bug:** `/bug-tdd` (failing test) → `/bug-fix`.
- **feature/chore:** `/speckit-opsmill-implement` — preflight, then the tasks loop in **clean-context
  subagents**, then `review-run`, then the final report. (Clean-context subagents + residue-free diffs
  are built into this command; do not re-run a separate prune/review pipeline.)
Verify the real diff, never the self-report. **Gate + verify:** tests that were red are green *and* a
skeptic fails to refute "this implements the spec / fixes the bug"; the `opsmill-implement-report.md`
has no unaddressed high-severity findings. **Checkpoint:** findings & fixes accepted (on `L`, per milestone).

### Stage 4 — Delivery
1. **CI gate:** `/pre-ci` (or detected test+lint). Red → loop back to the Stage 3 fix pass. **Never
   proceed with a red gate.**
2. **Split assessment** (bias toward single PR) per [phases/pr-split.md](phases/pr-split.md).
   **Checkpoint:** user picks single / accepts split. Never force a split.
3. **Open** the PR with `pr` → `/git-pr` → `gh pr create`. Record PR URL in `ship.md`; propose Jira
   *In review*. Then `/pr-monitor` (or `gh run watch`) follows CI; red loops back to the Stage 3 fix pass.
4. **Review feedback:** when processing review comments, fetch **all** unresolved threads — every
   author, review bots included — never only the reviewer the user named; assess each (fix, or
   answer on the thread with evidence). **Re-fetch the threads after every push**: bots re-review
   the new diff and their newest findings are otherwise invisible. After resolving a round of
   feedback, run `harvesting-review` on the threads just processed and update the `harvest` marker
   in `ship.md` — the fix loop already holds every thread and its landed correction, which makes it
   the cheapest and most complete moment to harvest.
5. **Session-bound extraction (every lane):** once the PR is open and its CI is green, run
   `speckit-opsmill-retrospect` and `capturing-knowledge` at this checkpoint — even on lanes that
   skip Stage 5. Their raw material is the session itself (friction, wrong turns, tooling gaps) and
   it decays when the session ends; deferring them to Extract loses it.
Optional `/qa` and spec-&-code review where the project defines them.

### Stage 5 — Extract *(manual)*
Extract keeps only the **artifact-bound** work — inputs that outlive the session (the spec dir, the
implement report, the PR threads). The **session-bound** tools (`speckit-opsmill-retrospect`,
`capturing-knowledge`) already ran at the Stage 4 checkpoint; do not defer or re-run them here.

**Manual gate:** the user reviews `opsmill-implement-report.md` first. Then `/speckit-opsmill-extract`
distils durable knowledge into `dev/knowledge` · `dev/guidelines` · `dev/adr` and archives the spec.

**`harvesting-review` is triggered by review activity, not by this stage or the lane.** Review
feedback arrives after the shipping session ends, so the harvest cannot run on a schedule — it
anchors to the moments the PR pulls you back:
- the Stage 4 review-fix loop harvests each round of feedback right after processing it;
- on any resume, reconcile compares the PR's review threads against the `harvest` marker in
  `ship.md` — unharvested threads re-open the step;
- when reconcile detects the PR merged, propose a final harvest before proposing Jira *Done*.

Doc changes join **this** PR unless the user asks otherwise. **Checkpoint** only if a step proposes
changes → propose Jira *Done*.

## Manifest & resume

`ship.md` lives in the feature dir (`specs/<feature>/`, located via `.specify/feature.json`) and is a
thin **index**, not a store: feature id · issue/JPD · branch · spec dir · report path · PR url ·
per-stage checkpoint status + pointers. The real content lives in the external homes above.
Follow [phases/manifest.md](phases/manifest.md) for the schema and the **resume + reconcile** logic:
re-invoking the skill reads the index, prints a status board, **reconciles claimed-`done` stages
against the live sources** (Jira status, PR state, files on disk — the sources always win), and
continues at the first unfinished stage.

## Discover available context (probe → reuse → fall back)

Use the first available source per capability. Probe; never invent a command the repo lacks.

| Capability | 1. In-repo skill/command | 2. Marketplace plugin | 3. Built-in fallback |
|---|---|---|---|
| Ticket / issue | `creating-issues`, `/create-jira-tickets` | — | skip |
| Ticket → branch | `/speckit-git-feature` | — | `git checkout -b` |
| Idea / PRD | `grilling-ideas`, `creating-prd` | `superpowers:brainstorming` | ask 2–3 questions inline |
| Prep (design→tasks) | `/speckit-opsmill-prep`, or `/speckit-specify`·`/speckit-plan`·`speckit-critique-run`·`/speckit-tasks` | `superpowers:writing-plans` | `Explore`/`Plan` agents + inline task list |
| Bug root-cause | `/bug-analyze` | — | `Explore` agents on the failing surface |
| Implement (feature) | `/speckit-opsmill-implement` | `superpowers:subagent-driven-development` + `test-driven-development` | `general-purpose` agents, test-first, clean-context |
| Implement (bug) | `/bug-tdd` → `/bug-fix` | `superpowers:test-driven-development` | `general-purpose` agent, test-first |
| Review (in-command) | (inside `/speckit-opsmill-implement`) `speckit-review-run` | `coderabbit:code-review`, `code-simplifier` | `general-purpose` reviewers + `/security-review` |
| CI gate | `/pre-ci` | `superpowers:verification-before-completion` | detected test + lint commands |
| Commit | `commit`, `/git-commit` | `commit-commands:commit` | `git commit` (conventional) |
| PR | `pr`, `/git-pr` | `commit-commands:commit-push-pr`, `superpowers:finishing-a-development-branch` | `gh pr create` |
| Post-open CI watch | `monitoring-pull-requests` | — | `gh run watch` / skip |
| Extract knowledge | `/speckit-opsmill-extract`, `capturing-knowledge`, `audit-docs`/`/audit-docs` → `add-docs` | — | edit `dev/` docs directly |
| Learn from review | `harvesting-review` *(PR #9922, in `stable`)* | — | skip |
| Retrospective | `speckit-opsmill-retrospect` (`/speckit.opsmill.retrospect`) | — | skip |
| Jira progress | Atlassian MCP (`transitionJiraIssue`, `addCommentToJiraIssue`) | — | record status in `ship.md` only |
| Branch update / rebase | `rebase`, `/rebase-current-branch` | — | `git rebase`/`git merge` base |

## Anti-patterns

- ❌ Asking "what should I build?" when `$ARGUMENTS` is empty — run the resume scan first.
- ❌ Treating `ship.md` as the store of record — it only indexes the external homes; reconcile against them.
- ❌ Running a whole stage unattended on `M`/`L` — checkpoints exist so the user verifies & accepts.
- ❌ Auto-transitioning Jira — always propose at the checkpoint, apply on accept.
- ❌ Re-running a separate prune/review pipeline after `/speckit-opsmill-implement` — it already does clean-context + review-run.
- ❌ Running the same lane for a bug and an `L` feature.
- ❌ Marking a stage `done` without its gate passing, or trusting a claimed-`done` stage on resume without reconciling.
- ❌ Stacking all three reliability layers on a stage with no risk flag.
- ❌ Reimplementing anything in the discovery table, or inventing a command the repo lacks.
- ❌ Opening a PR with a red CI gate; forcing a PR split when the changes are coupled.
