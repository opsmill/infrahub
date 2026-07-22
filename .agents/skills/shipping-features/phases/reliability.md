# Reliability model

Three independent layers, each catching a different failure mode. The gate is universal;
parallel and adversarial-verify sit at opposite ends of the pipeline; all three stack on a
single phase **only** when a risk flag makes it worth the cost.

## The three layers

| Layer | Catches | Fires |
|---|---|---|
| **Gate** (exit-criteria) | artifact is objectively incomplete / malformed | end of *every* phase, deterministic |
| **Parallel** (divergent framings + synthesize) | a locally-optimal but narrow approach | *before* work exists — genuine design forks only |
| **Adversarial verify** (skeptic tries to refute a claim) | looks right but is actually wrong | *after* a phase emits a checkable correctness claim |

**Why they don't all belong everywhere:** parallel and adversarial-verify apply at opposite ends.
A spec/plan phase has a design fork but no ground truth yet → parallel helps, a skeptic has nothing
concrete to refute. An implement/review phase produces a concrete claim → a skeptic is exactly right,
but divergence is wrong (each implement agent owns *different work*, not a *different framing*).

## Default placement (no risk flags)

| Phase | Gate | Parallel | Verify |
|---|---|---|---|
| understand (spec/plan) | ✅ | ✅ on `M`/`L` (framings → synthesize) | — (speckit-analyze/clarify already play the check role) |
| implement | ✅ (red→green test) | — | ✅ skeptic: "does this actually implement the spec / fix the bug?" |
| review | ✅ (no open blockers) | ✅ (review lenses → synthesize) | ✅ (verify each finding is real before acting) |
| ci / commit / pr | ✅ | — | — (deterministic) |

**Review is the one phase that naturally runs all three** — multiple lenses diverge, a synthesizer
ranks, then each finding is verified real. It's read-only, so it's cheap. That's by design, not a risk escalation.

## Risk-triggered stacking

Add the *third* layer to a phase only when a risk flag set at classification justifies it. The
trigger is: **high blast radius AND the first two layers share a failure mode** (parallel agents read
the same codebase, so their framings — and the synthesizer inheriting them — can share a blind spot; a
skeptic breaks that correlated error).

| Risk flag | Escalation |
|---|---|
| `irreversible` | skeptic pass on the **plan synthesis** — red-team "what breaks in prod that all framings missed" |
| `security` | `/security-review` mandatory in review; skeptic on each security finding |
| `cross-team` | plan-synthesis skeptic + name required reviewers in the PR body |
| `crux-algorithm` | on the one hard unit only: **two independent implementations** (real divergence on implement), gate on tests, skeptic picks the survivor apart |

## Scaling by size

- **`S`** — gate + one verify on implement. No parallelism. A skeptic on a one-line fix is enough.
- **`M`** — parallel only where a real fork exists; verify on implement + review.
- **`L`** — full parallel front-end (spec, plan), verify on implement + review, plus any risk stacking.

## Rules

- **Gate first, always.** If you add only one layer to a phase, it's the gate. Parallel and verify
  are refinements on top of a gate, never replacements for it.
- **One synthesizer per divergence.** Never feed N parallel framings into N downstream agents.
- **A skeptic must try to fail the claim.** Prompt it to refute, defaulting to "not proven" when
  uncertain — a verifier that rubber-stamps is worse than none (false confidence).
- **Give the skeptic explicit lenses, even at `S`.** A single refute-the-claim prompt anchors on
  spec conformance and misses orthogonal defects. Always name at least: (1) spec/bug correctness,
  (2) interaction with existing concurrent paths (locks, transactions, in-flight writers touching
  the same data), (3) compliance with the repo's own guidelines (`dev/guidelines/` or equivalent),
  (4) query/IO efficiency (N+1s, per-item loops that should be set-based). One agent, four lenses —
  this is not parallelism.
- **Don't stack to look thorough.** Three layers on a no-risk phase is wasted tokens and slower
  checkpoints. Match the layers to the flags in `ship.md`.
