---
name: "feature-flow"
description: "Multi-phase orchestrator for a feature: spec → plan → implement → review → CI gate → PR. Uses parallel agents for divergent thinking and a single synthesizer between phases. Trigger when the user says 'start the feature flow', 'run feature-flow', or names a ticket and asks to drive it end to end."
argument-hint: "<ticket-id or short description>"
user-invocable: true
disable-model-invocation: false
---

# Feature Flow

End-to-end orchestrator for a single feature. Reuses existing skills (`/speckit-*`, `/pre-ci`, `/capture-knowledge`, `/commit-commands:commit-push-pr`) — does **not** reimplement them.

## Core principles

- **Parallel = divergent thinking** (specs, plans, reviews). Multiple agents with different framings, then one synthesizer to converge.
- **Sequential = convergent/deterministic** (CI checks, commit, PR).
- **Always synthesize before acting.** Never feed N parallel outputs directly into N implementation agents — one human-approved synthesis between phases.
- **Worktrees for implementation** so parallel implementers don't stomp each other (`isolation: "worktree"` on Agent calls).
- **Stop at checkpoints.** The user approves at the end of phases 1, 2, 4, and 5. Do not chain phases unattended.

## Phases

### Phase 1 — Specs

1. If the user provided a ticket ID or feature description, restate it in one sentence and confirm scope.
2. Run **3 `Explore` agents in parallel** (single message, three tool calls), each with a different framing:
   - **Existing patterns** — find prior art in the codebase for similar features.
   - **Related entities & APIs** — what GraphQL types, routes, components, or backend services intersect this work.
   - **Test coverage gaps** — what isn't tested today in the surface area that will change.
3. **Synthesize** with **1 `general-purpose` agent**: merge the three findings into a draft spec brief (problem, constraints, affected files, open questions).
4. Invoke `/speckit-specify` to formalize the spec, then `/speckit-clarify` to surface gaps.
5. **Checkpoint:** show the spec summary, list open questions, wait for user approval.

### Phase 2 — Plan

1. Run **3 `Plan` agents in parallel** with deliberately different framings:
   - **Minimal change** — smallest viable diff.
   - **Refactor-friendly** — fix adjacent rough edges that the change exposes.
   - **Test-first** — what tests would prove this works; what's the implementation that makes them pass.
2. **Synthesize** with **1 `general-purpose` agent**: compare the three plans, pick the best approach per step, flag tradeoffs. Output as a single ordered task list.
3. Invoke `/speckit-plan` then `/speckit-tasks` to formalize.
4. Optionally run `/speckit-analyze` for cross-artifact consistency.
5. **Checkpoint:** present the merged plan + tradeoffs, wait for user approval.

### Phase 3 — Implement

1. Group tasks into **independent units** (no shared file or sequential dependency).
2. For each unit, spawn a `general-purpose` agent with `isolation: "worktree"`, instructed to follow the `superpowers:test-driven-development` skill.
3. Send all independent units in a **single message with parallel tool calls**. Send dependent units sequentially.
4. As each agent reports back, verify the actual diff (not just the summary). Trust-but-verify per the global rule.
5. If any agent reports a blocker, surface it to the user before continuing.

### Phase 4 — Review (pre-PR)

1. Run in **parallel** in a single message:
   - `coderabbit:code-reviewer` — broad correctness/security review.
   - `code-simplifier` — simplification pass on the diff.
   - `general-purpose` — custom prompt: "review for security, edge cases, and reuse against `dev/knowledge/frontend/shared-components.md`".
2. **Synthesize** with **1 `general-purpose` agent**: dedup findings, rank by severity (blocker / nit / suggestion), output a fix list.
3. **Checkpoint:** show the ranked fix list, wait for user approval.
4. **Fix pass:** for approved fixes, spawn small parallel agents (one per independent file group) to apply.

### Phase 4.5 — Knowledge capture (opportunistic)

1. Invoke `/capture-knowledge` with no arguments — it will scan this session for non-obvious facts learned while building this feature.
2. Common capture-worthy moments to flag to the skill:
   - An `Explore` agent in Phase 1 had to hunt across multiple files to reconstruct a contract → that contract belongs in `dev/knowledge/frontend/`.
   - The synthesizer in Phase 2 had to make a non-obvious tradeoff → the reasoning belongs in `dev/guidelines/frontend/` or a relevant knowledge doc.
   - The review in Phase 4 flagged the same pattern multiple times → name it as a guideline.
3. **Checkpoint:** user approves doc changes before they are written. Skip silently if nothing genuinely new was learned — empty captures are a feature, not a failure.
4. If docs change, they become part of the same PR (no separate PR for docs unless the user asks).

### Phase 5 — CI gate (must-pass before PR)

1. Invoke `/pre-ci` (not `--fast`). This already runs biome, knip-equivalent, betterer, tests, schema validation, and lint.
2. If anything fails, loop back to Phase 4 fix pass. **Do not proceed to Phase 6 with a red CI gate.**
3. **Checkpoint:** show the `/pre-ci` results table, wait for user approval before opening the PR.

### Phase 6 — PR

1. **1 `general-purpose` agent** drafts PR title (≤70 chars) and summary from `git diff develop...HEAD` plus the spec brief from Phase 1.
2. Show draft to user.
3. On approval, invoke `/commit-commands:commit-push-pr` to commit, push, and open the PR.
4. Report the PR URL.

## Iteration notes

This skill is intentionally lightweight — it composes existing skills rather than duplicating their logic. To customize:

- Add new phase variants in this file.
- If a phase grows large, extract it to `dev/skills/feature-flow/phases/<phase>.md` and reference it from here.
- To add custom sub-agents (e.g. a project-specific reviewer), create `.claude/agents/<name>.md` at the repo root.

## Anti-patterns

- ❌ Skipping the synthesizer between parallel agents.
- ❌ Chaining all phases unattended — checkpoints exist so the user can redirect early.
- ❌ Opening a PR with a red `/pre-ci` — the hook would block it, but don't even try.
- ❌ Reimplementing `/pre-ci`, `/speckit-*`, or commit/PR logic inside this skill. Call them.
