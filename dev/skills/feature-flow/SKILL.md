---
name: "feature-flow"
description: "Multi-phase orchestrator for a feature: spec → plan → implement → review → CI gate → PR. Uses parallel agents for divergent thinking and a single synthesizer between phases. Trigger when the user says 'start the feature flow', 'run feature-flow', or names a ticket and asks to drive it end to end."
argument-hint: "<ticket-id or short description>"
user-invocable: true
disable-model-invocation: false
---

# Feature Flow

End-to-end orchestrator for a single feature. Reuses existing repo-level slash commands and skills (`/speckit-*`, `/pre-ci`, `/git-commit`, `/git-pr`, `/capture-knowledge`) — does **not** reimplement them.

## Core principles

- **Parallel = divergent thinking** (specs, plans, reviews, assessments). Multiple agents with different framings, then one synthesizer to converge.
- **Sequential = convergent/deterministic** (CI checks, commit, PR).
- **Always synthesize before acting.** Never feed N parallel outputs directly into N implementation agents — one human-approved synthesis between phases.
- **Worktrees for implementation** so parallel implementers don't stomp each other (`isolation: "worktree"` on Agent calls).
- **Stop at checkpoints.** The user approves at the end of phases 1, 2, 4, 5, and 6a. Do not chain phases unattended.

## The divergent-then-synthesize primitive

This is the single most important pattern in this skill. **Any phase that involves judgment, opinion, or design choice uses it.** Any phase that is deterministic (running tests, formatting) does not.

**Shape:**

1. **Diverge:** Spawn 2-4 agents *in parallel in a single message* (multiple tool calls in one assistant turn). Each gets a **different framing** of the same problem — not the same prompt N times. The framings are deliberate: minimal vs. refactor-friendly, security vs. simplicity, single-PR vs. split, etc.
2. **Synthesize:** Spawn **1** `general-purpose` agent that receives all N outputs and produces a single ranked recommendation. It must compare, dedup, and flag tradeoffs — not just concatenate.
3. **Checkpoint:** Surface the synthesis to the user with the open tradeoffs. User approves, redirects, or asks for another framing.

**Why it works:** One agent's first answer is often locally optimal but globally narrow. Diverse framings surface options that no single agent would explore. The synthesizer prevents you from drowning in N opinions.

**Where this primitive is used in this skill:**

| Phase | Diverge (parallel) | Synthesize |
|---|---|---|
| 1 — Specs | 3 `Explore` framings | 1 `general-purpose` |
| 2 — Plan | 3 `Plan` framings | 1 `general-purpose` |
| 4 — Review | `coderabbit:code-reviewer` + `code-simplifier` + `general-purpose` | 1 `general-purpose` |
| 6a — Split assessment | 3 `general-purpose` framings | 1 `general-purpose` |

Phase 3 (implement) is **also** parallel but is *not* divergent — each agent owns a different unit of work, not a different framing of the same problem. Don't conflate the two.

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

#### 6a. Split assessment (bias toward single PR)

Apply the **divergent-then-synthesize primitive** to the split decision. Before drafting any PR, run **3 `general-purpose` agents in parallel** against `git diff develop...HEAD` and `git log develop..HEAD`, each with a deliberately different framing:

- **Reviewer ergonomics** — "what split would make this fastest to review?" (favors small, focused PRs)
- **Risk isolation** — "what split would let us revert one part without affecting the others?" (favors separating high-risk from low-risk changes)
- **Coherence preservation** — "what's the simplest narrative? when would splitting break tests or tell a worse story?" (favors a single PR; this framing is the counterweight)

Each agent returns either *"ship as one"* or *"split into N groups: ..."* with its reasoning.

**Synthesize** with **1 `general-purpose` agent**: compare the three framings, weigh tradeoffs, and produce a single recommendation. Apply the strong bias toward a single PR:

- **Only recommend a split when ≥2 of the 3 framings independently suggest it**, AND at least one of these clearly applies:
  - Independent concerns (e.g. unrelated drive-by refactor, or backend + frontend independently reviewable).
  - Different reviewers needed (e.g. infra/CI vs. product).
  - Different risk profiles (e.g. low-risk config + high-risk feature).
  - Revertable in isolation.
- **Do NOT recommend a split when:**
  - ❌ Changes are coupled (feature + its own tests + its own docs).
  - ❌ Splitting would leave one PR with broken tests or builds.
  - ❌ The change has a single coherent narrative.
  - ❌ The split would create a chain of dependent PRs that must merge in order, and the value isn't worth that cost.

The synthesizer outputs one of:

- **"Ship as one PR"** with a one-line justification.
- **"Suggest split into N PRs"** with the proposed groupings (which commits / which files go where, in dependency order if any), plus an explicit *"but a single PR is also reasonable"* note when the case is borderline.

**Checkpoint:** show the synthesis (and the three framings if useful) to the user. User picks single PR, accepts the split, or proposes a different split. Never force a split without approval.

#### 6b. Draft PR(s)

For **each** PR (one or many):

1. If splitting, create a new branch from `origin/develop` and cherry-pick the relevant commits onto it. Verify the branch builds (`/pre-ci --fast` at minimum on each split branch).
2. **1 `general-purpose` agent** drafts title (≤70 chars) and summary from the diff of *that* PR plus the spec brief from Phase 1. For split PRs, the summary should note any dependencies on sibling PRs.
3. Show draft(s) to user.

#### 6c. Open

For each approved PR branch, invoke `/git-pr` with the approved title and body:

```
/git-pr --title "<approved title>" --body "<approved body>"
```

`/git-pr` handles the push (setting upstream if needed) and `gh pr create` itself. It refuses to run if the working tree is dirty or if the branch has no commits ahead of base — surface either error to the user rather than working around it.

For split PRs with dependencies, prepend a `Depends on #<sibling-PR>` line to dependent bodies and open in dependency order.

Report the PR URL(s) returned by `/git-pr`. For split PRs, note merge order.

Note: by this point, the work was already committed iteratively during Phase 3. If anything is uncommitted, `/git-pr` will refuse — do not auto-commit drift to satisfy it; surface the dirty state to the user.

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
- ❌ Forcing a PR split when the changes are coupled — split assessment is a *suggestion*, not a mandate. Single PR is the default.
