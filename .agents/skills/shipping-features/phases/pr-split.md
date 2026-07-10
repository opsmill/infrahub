# Phase 8 — PR split assessment (bias toward single PR)

Reference for the split-assessment step of `shipping-features` (phase 8, before opening the PR).
Apply the **parallel divergence + synthesize** layer to the split decision.

## Diverge

Run **3 `general-purpose` agents in parallel** against `git diff <base>...HEAD` and
`git log <base>..HEAD` (auto-detect the base branch), each with a deliberately
different framing:

- **Reviewer ergonomics** — "what split would make this fastest to review?" (favors small, focused PRs)
- **Risk isolation** — "what split would let us revert one part without affecting others?" (favors separating high-risk from low-risk)
- **Coherence preservation** — "what's the simplest narrative? when would splitting break tests or tell a worse story?" (favors a single PR; the counterweight)

Each agent returns *"ship as one"* or *"split into N groups: ..."* with reasoning.

## Synthesize

**1 `general-purpose` agent**, applying a strong bias toward a single PR:

- **Only recommend a split when ≥2 of the 3 framings independently suggest it**, AND at least one of:
  - Independent concerns (unrelated drive-by refactor, or backend + frontend independently reviewable).
  - Different reviewers needed (infra/CI vs. product).
  - Different risk profiles (low-risk config + high-risk feature).
  - Revertable in isolation.
- **Do NOT recommend a split when:**
  - ❌ Changes are coupled (feature + its own tests + its own docs).
  - ❌ Splitting would leave one PR with broken tests or builds.
  - ❌ The change has a single coherent narrative.
  - ❌ The split would create a chain of dependent PRs that must merge in order for little value.

## Output

The synthesizer outputs one of:

- **"Ship as one PR"** with a one-line justification.
- **"Suggest split into N PRs"** with the proposed groupings (which commits / files go where, in
  dependency order), plus an explicit *"but a single PR is also reasonable"* note when borderline.
