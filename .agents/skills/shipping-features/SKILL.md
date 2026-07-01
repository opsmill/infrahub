---
name: shipping-features
description: >-
  Use when the user says "ship this feature", "run shipping-features", or names
  a ticket or feature and asks to drive it end to end from spec to PR. Do not
  use when the user wants a single isolated step (just a spec, just a review,
  just a PR) — invoke that step's tool directly instead. Conducts a lean
  multi-phase pipeline that reuses existing tools, with human checkpoints
  between phases.
argument-hint: "<ticket-id or short description>"
---

# Shipping Features

## User Input

```text
$ARGUMENTS
```

Treat `$ARGUMENTS` as the ticket ID or short feature description. If empty, ask the
user what feature to ship before starting.

## What this does

End-to-end conductor for a single feature: spec → plan → implement → review → CI gate → PR.
It **composes existing tools** — the project's own commands, sibling opsmill-software skills,
recommended marketplace plugins (superpowers, coderabbit, commit-commands) when present, and
built-in agents as the always-works fallback. It does **not** reimplement spec, plan, TDD,
review, commit, or PR logic. Its only original contribution is the
**divergent-then-synthesize primitive** (parallel framings + a synthesizer at every judgment
point) and the human checkpoints between phases. Everything else is delegated to the best
available tool, discovered at runtime, with a built-in fallback so the flow works in any repo.

## Core principles

- **Reuse over reimplementation.** Every phase delegates to an existing tool. Reinvent nothing.
- **Parallel = divergent thinking** (specs, plans, reviews, assessments). Multiple agents
  with different framings, then one synthesizer to converge.
- **Sequential = convergent/deterministic** (CI checks, commit, PR).
- **Always synthesize before acting.** Never feed N parallel outputs directly into N
  implementation agents — one human-approved synthesis between phases.
- **Worktrees for implementation** so parallel implementers don't stomp each other.
- **Stop at checkpoints.** The user approves at the end of phases 1, 2, 4, 5, and 6a —
  plus phase 4.5 when knowledge capture proposes doc changes (conditional: skipped when
  there is nothing to capture). Do not chain phases unattended.
- **Degrade, never block.** A missing optional plugin lowers quality, it never stops the flow.

## Recommended companion plugins (optional)

These make each phase better. They are **optional** — built-in fallbacks cover every phase
without them. Install from the official marketplace with `claude plugin install <name>`
(or the `/plugin` menu).

| Plugin | Powers | Tier |
|---|---|---|
| `superpowers` | planning, TDD, worktrees, parallel agents, review wrappers, verification, branch finishing | **Recommended** |
| `coderabbit` | AI correctness/security code review | **Recommended** |
| `commit-commands` | conventional commit, push, PR | Nice-to-have |
| `code-simplifier` | simplification pass on the diff | Nice-to-have |

## Preflight: check companions once (non-blocking)

Before phase 1, probe for the companions above **once**. If any are missing, print a single
consolidated note naming what's absent and the install command, then **proceed immediately**
with built-in fallbacks. Do not prompt, do not wait, do not re-suggest in later phases, and
never auto-install. The user controls their own environment.

## Discover available context (probe → reuse → fall back)

For each capability, use the first available source in priority order. Probe; never invent a
command the project lacks; surface ambiguity to the user.

| Capability | 1. Host repo command | 2. opsmill sibling | 3. Marketplace plugin | 4. Built-in fallback |
|---|---|---|---|---|
| Ticket/issue (optional) | — | `create-issue` | — | skip |
| Idea hardening | — | `grill-idea` | `superpowers:brainstorming` | ask 2–3 questions inline |
| Spec (divergent) | — | — | — | `Explore` agents (always) |
| Spec (formalize) | `/speckit-specify`, `/speckit-clarify` | — | — | keep the synthesized brief |
| Plan (divergent) | — | — | — | `Plan` agents (always) |
| Plan (formalize) | `/speckit-plan`, `/speckit-tasks` | — | `superpowers:writing-plans` | inline ordered task list |
| Implement (TDD) | — | — | `superpowers:test-driven-development` | `general-purpose` agents following TDD |
| Worktree isolation | — | — | `superpowers:using-git-worktrees` | `isolation: "worktree"` on Agent calls |
| Parallel execution | — | — | `superpowers:subagent-driven-development` / `dispatching-parallel-agents` | parallel Agent calls in one message |
| Code review | — | — | `coderabbit:code-review`, `code-simplifier`, `superpowers:requesting-code-review` | `general-purpose` reviewers + `/security-review` |
| Knowledge capture | — | `capturing-knowledge` | — | skip |
| Branch update | — | `rebase` | — | `git rebase`/`git merge` base |
| CI gate / verify | `/pre-ci` | — | `superpowers:verification-before-completion` | run detected test + lint commands |
| Commit | `/git-commit` | — | `commit-commands:commit` | `git commit` (conventional message) |
| PR | `/git-pr` | — | `commit-commands:commit-push-pr`, `superpowers:finishing-a-development-branch` | `gh pr create` |

## The divergent-then-synthesize primitive

This is the single original pattern in this skill. **Any phase that involves judgment, opinion,
or design choice uses it.** Any deterministic phase (running tests, formatting) does not.

**Shape:**

1. **Diverge:** Spawn 2–4 agents *in parallel in a single message* (multiple tool calls in one
   assistant turn). Each gets a **different framing** of the same problem — not the same prompt N
   times. The framings are deliberate: minimal vs. refactor-friendly, security vs. simplicity,
   single-PR vs. split, etc.
2. **Synthesize:** Spawn **1** `general-purpose` agent that receives all N outputs and produces a
   single ranked recommendation. It must compare, dedup, and flag tradeoffs — not just concatenate.
3. **Checkpoint:** Surface the synthesis to the user with the open tradeoffs. User approves,
   redirects, or asks for another framing.

**Why it works:** One agent's first answer is often locally optimal but globally narrow. Diverse
framings surface options no single agent would explore. The synthesizer prevents drowning in N opinions.

**Where this primitive is used:**

| Phase | Diverge (parallel) | Synthesize |
|---|---|---|
| 1 — Specs | 3 `Explore` framings | 1 `general-purpose` |
| 2 — Plan | 3 `Plan` framings | 1 `general-purpose` |
| 4 — Review | the available review tools | 1 `general-purpose` |
| 6a — Split assessment | 3 `general-purpose` framings | 1 `general-purpose` |

Phase 3 (implement) is **also** parallel but is *not* divergent — each agent owns a different unit
of work, not a different framing of the same problem. Don't conflate the two.

> This primitive is documented inline on purpose. If a second orchestrator skill is added to
> `opsmill-software` and needs it, extract it to a shared non-invocable reference (the way
> `opsmill-presales` uses `presales-common`) rather than copying it.

## Phases

### Phase 1 — Specs

1. If the user provided a ticket ID or feature description, restate it in one sentence and confirm
   scope. If there is no ticket yet and the project tracks work as issues, offer to capture one
   first via `create-issue` — shipping-features otherwise assumes the feature is already defined.
2. If the idea is fuzzy, harden it: `grill-idea` (sibling) or `superpowers:brainstorming` if present;
   otherwise ask 2–3 clarifying questions inline.
3. **Diverge:** run **3 `Explore` agents in parallel** (single message, three tool calls), each with
   a different framing:
   - **Existing patterns** — prior art in the codebase for similar features.
   - **Related entities & APIs** — types, routes, components, or services this work intersects.
   - **Test coverage gaps** — what isn't tested today in the surface area that will change.
4. **Synthesize** with **1 `general-purpose` agent**: merge the findings into a draft spec brief
   (problem, constraints, affected files, open questions).
5. **Formalize** only if the project provides a spec command (`/speckit-specify`, `/speckit-clarify`).
   Otherwise keep the inline spec brief.
6. **Checkpoint:** show the spec summary, list open questions, wait for user approval.

### Phase 2 — Plan

1. **Diverge:** run **3 `Plan` agents in parallel** with deliberately different framings:
   - **Minimal change** — smallest viable diff.
   - **Refactor-friendly** — fix adjacent rough edges the change exposes.
   - **Test-first** — what tests would prove this works; what implementation makes them pass.
2. **Synthesize** with **1 `general-purpose` agent**: compare the plans, pick the best approach per
   step, flag tradeoffs. Output a single ordered task list.
3. **Formalize:** `/speckit-plan` + `/speckit-tasks` if present; else `superpowers:writing-plans`
   if present; else keep the inline task list.
4. **Checkpoint:** present the merged plan + tradeoffs, wait for user approval.

### Phase 3 — Implement

1. Group tasks into **independent units** (no shared file or sequential dependency).
2. For each unit, run an implementation agent that follows TDD in an isolated worktree:
   prefer `superpowers:test-driven-development` + `superpowers:using-git-worktrees`
   (orchestrated by `superpowers:subagent-driven-development` when present); otherwise spawn a
   `general-purpose` agent with `isolation: "worktree"` instructed to follow test-first discipline.
3. Send all independent units in a **single message with parallel tool calls**. Send dependent
   units sequentially.
4. As each agent reports back, verify the actual diff (not just the summary). Trust-but-verify.
5. If any agent reports a blocker, surface it to the user before continuing.

### Phase 4 — Review (pre-PR)

1. **Diverge:** run the available review tools in **parallel** in a single message:
   - `coderabbit:code-review` — broad correctness/security review.
   - `code-simplifier` — simplification pass on the diff.
   - `/security-review` — security pass.
   - Fallback when those are absent: 2–3 `general-purpose` reviewers framed for correctness,
     edge cases, and reuse against the project's discovered guidelines/knowledge docs.
   Wrap the round with `superpowers:requesting-code-review` if present.
2. **Synthesize** with **1 `general-purpose` agent**: dedup findings, rank by severity
   (blocker / nit / suggestion), output a fix list.
3. **Checkpoint:** show the ranked fix list, wait for user approval. Use
   `superpowers:receiving-code-review` discipline (verify before implementing) when triaging.
4. **Fix pass:** for approved fixes, spawn small parallel agents (one per independent file group).

### Phase 4.5 — Knowledge capture (opportunistic)

1. Delegate to the sibling `capturing-knowledge` skill with no arguments — it scans this session
   for non-obvious facts learned while building this feature and discovers where the project's docs
   live. If that skill is absent, skip this phase.
2. Common capture-worthy moments to flag:
   - An `Explore` agent in phase 1 had to hunt across files to reconstruct a contract → knowledge.
   - The synthesizer in phase 2 made a non-obvious tradeoff → a guideline or knowledge doc.
   - The review in phase 4 flagged the same pattern repeatedly → name it as a guideline.
3. **Checkpoint:** the capture skill confirms doc changes before writing. Skip silently if nothing
   genuinely new was learned — empty captures are a feature.
4. If docs change, they join the same PR (no separate docs PR unless the user asks).

### Phase 5 — CI gate (must-pass before PR)

1. Run the project's pre-flight checks: `/pre-ci` if present; else `superpowers:verification-before-completion`
   if present; else run the detected test + lint commands directly (from `package.json`, `Makefile`,
   `pyproject.toml`, or the CI config). Do not invent commands.
2. If anything fails, loop back to the phase 4 fix pass. **Do not proceed with a red CI gate.**
3. **Checkpoint:** show the results, wait for user approval before opening the PR.

### Phase 6 — PR

#### 6a. Split assessment (bias toward single PR)

Apply the **divergent-then-synthesize primitive** to the split decision: **3 `general-purpose`
agents in parallel** against the branch diff, each with a different framing (reviewer
ergonomics, risk isolation, coherence preservation), then **1 synthesizer** with a strong bias
toward a single PR. Follow [phases/pr-split.md](phases/pr-split.md) for the framings, the
split/no-split criteria, and the expected output format.

**Checkpoint:** show the synthesis to the user. User picks single PR, accepts the split, or proposes
a different split. Never force a split without approval.

#### 6b. Draft PR(s)

For **each** PR (one or many):

1. If splitting, create a branch from the base and cherry-pick the relevant commits onto it. Verify
   the branch builds (a fast CI pass at minimum on each split branch).
2. **1 `general-purpose` agent** drafts title (≤70 chars) and summary from the diff of *that* PR plus
   the spec brief from phase 1. For split PRs, note dependencies on sibling PRs.
3. Show draft(s) to the user.

#### 6c. Open

Open each approved PR with the first available tool: `/git-pr` (host) → `commit-commands:commit-push-pr`
→ `superpowers:finishing-a-development-branch` → plain `gh pr create`. Commit any final changes with
`/git-commit` (host) → `commit-commands:commit` → plain `git commit`.

Whichever tool is used, it should refuse on a dirty tree or a branch with no commits ahead of base —
surface that error rather than working around it. By this point the work was already committed
iteratively during phase 3; do not auto-commit drift to satisfy a PR command.

For split PRs with dependencies, prepend `Depends on #<sibling-PR>` to dependent bodies and open in
dependency order. Report the PR URL(s); for split PRs, note merge order.

## Iteration notes

This skill is intentionally lightweight — it composes existing tools rather than duplicating them.
To customize:

- Add new phase variants in this file.
- If a phase grows large, extract it to `phases/<phase>.md` next to this file and reference it.
- To add a custom sub-agent (e.g. a project-specific reviewer), create `.claude/agents/<name>.md`
  in the consuming project.

## Anti-patterns

- ❌ Skipping the synthesizer between parallel agents.
- ❌ Chaining all phases unattended — checkpoints exist so the user can redirect early.
- ❌ Opening a PR with a red CI gate.
- ❌ Reimplementing anything in the discovery table. Reuse the first available source; fall back generically.
- ❌ Inventing a command the project does not provide.
- ❌ Blocking the flow on a missing optional plugin, or re-suggesting it every phase, or auto-installing it.
- ❌ Forcing a PR split when the changes are coupled — split assessment is a *suggestion*. Single PR is the default.
