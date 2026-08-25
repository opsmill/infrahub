# Implementation Plan: E2E proof runs for the bug pipeline

**Branch**: `e2e-proof-runs-ifc-3059` | **Date**: 2026-08-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-e2e-proof-runs/spec.md`

## Summary

Give the bug pipeline a CI proof job so its agents can use the E2E tier: on `ai-bug-pipeline-*` PRs that add one e2e test, CI runs exactly that test, enforces the phase contract (assertion-failure before the fix marker, pass after), publishes each run's screenshot as a release asset, and idempotently embeds before/after evidence plus an expected-red note into the PR description. Pipeline prompts are updated so agents choose the E2E tier without local execution. Everything mechanical was validated by PoC PR #10411; this plan productionizes it with two changes over the PoC: release-asset storage (replacing the orphan branch) and the extracted, unit-tested verdict script.

## Technical Context

**Language/Version**: GitHub Actions YAML + Python 3.12 (verdict script, body-embed script), bash glue

**Primary Dependencies**: `gh` CLI (releases, PR body PATCH), `uv` + repo Python env, pytest-playwright suite at `tests/e2e/` (emits `playwright-junit.xml`), infrahub-testcontainers, `gh aw` compiler (v0.81.6) for the agent prompt locks

**Storage**: release assets on permanent prerelease tag `bug-pipeline-assets` (see research R1)

**Testing**: unit tests for the verdict script (`.github/scripts/tests/`); end-to-end validation replays the PoC scenario (quickstart.md)

**Target Platform**: `ubuntu-latest` hosted runners (PoC-proven: RED 8m45s pulled image, GREEN 8m04s including `dev.build`)

**Project Type**: CI/tooling — workflows, scripts, agent prompts; no product code

**Performance Goals**: ≤15 min per proof phase (SC-002)

**Constraints**: must not break bug-agent-review triggers (body markers untouched outside owned sections); no git branch may accumulate images; `.lock.yml` files must be regenerated whenever the `.md` workflow prompts change

**Scale/Scope**: one proof run per pipeline-PR push; assets bounded by open pipeline PRs (≤ a handful at a time)

## Constitution Check

*GATE: evaluated against `dev/constitution.md` (v via `.specify/memory/constitution.md`).*

- **IV Test Discipline**: the only real logic (junit → verdict) is extracted to a script with unit tests; workflow glue is validated by the quickstart replay. E2E tests for the feature itself are not applicable (the feature *is* CI). PASS.
- **VI Security & Input Boundaries**: PR body content is attacker-influenced text on a public repo — it is only string-matched for markers (never evaluated), passed via env vars into scripts, and the workflow grants itself only `contents: write` + `pull-requests: write`. The proof job runs on `pull_request` (same-repo branches only, since `ai-bug-pipeline-*` branches are created by the pipeline app), never `pull_request_target`. PASS.
- **VII Simplicity**: two small workflows + one script; no new services or dependencies. PASS.
- **Quality gates**: yamllint covers workflows; ruff/mypy cover the new Python script (repo-wide lint reach verified during implementation); changelog fragment not required (no user-facing product change — internal dev tooling; decision recorded here).
- **Ask-first area (CI/CD changes)**: crossed by definition; the feature PR itself is the ask.

No violations → Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/005-e2e-proof-runs/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── proof-workflow.md
└── tasks.md              # produced by /speckit-tasks
```

### Source Code (repository root)

```text
.github/
├── workflows/
│   ├── bug-agent-e2e-proof.yml        # NEW: the proof job (trigger, phases, verdict, publish, embed)
│   ├── bug-agent-e2e-cleanup.yml      # NEW: on PR close, delete pr-<n>-* release assets
│   ├── bug-agent-test.md              # EDIT: E2E tier instructions (no local run; shard marker; CI verifies)
│   ├── bug-agent-test.lock.yml        # REGENERATED via gh aw compile
│   ├── bug-agent-fix.md               # EDIT: E2E tier verification delegated to proof job
│   └── bug-agent-fix.lock.yml         # REGENERATED via gh aw compile
└── scripts/
    ├── e2e_proof_verdict.py           # NEW: junit → verdict (phase-aware), stdout = verdict + reason
    ├── e2e_proof_embed.py             # NEW: idempotent PR-body section replace (proof + note sections)
    └── tests/
        └── test_e2e_proof_verdict.py  # NEW: unit tests over crafted junit fixtures

dev/bug-pipeline/
├── test-writing.md                    # EDIT: E2E tier path (placement, shard marker, skip local verify)
└── fix-implementation.md              # EDIT: E2E verification via proof job
```

**Structure Decision**: All new logic under `.github/` (it is repository automation, not product code); shared agent prompts stay in `dev/bug-pipeline/` as today, with the gh-aw copies kept in sync and recompiled.

## Design decisions (delta over the PoC)

1. **Storage** — release assets, run-id-suffixed names, superseded assets deleted on each publish; cleanup workflow empties `pr-<n>-*` on close (research R1, R6). The PoC's `bug-pipeline-assets` orphan branch is left untouched as reference; production never writes to it.
2. **Verdict as a tested script** — `e2e_proof_verdict.py` takes `--phase` and the junit path, prints `verdict=... reason=...`, exit code communicates contract satisfaction; unit tests cover: assertion failure, setup error, unexpected pass, multi-test, missing report, non-assertion failure (research R2).
3. **Embed as a script** — `e2e_proof_embed.py` owns the three marker pairs (`E2E_PROOF:RED`, `E2E_PROOF:GREEN`, `E2E_PROOF:NOTE`); it never rewrites anything outside them (FR-007, FR-011, FR-014).
4. **Expected-red note** — written into the NOTE section during RED, rewritten during GREEN (research R4); no PR comments, no labels.
5. **Image strategy** — RED resolves the latest published release image with a build fallback; GREEN always builds (research R3, FR-012).
6. **Concurrency** — `concurrency: bug-e2e-proof-${{ pr }}` + `cancel-in-progress` (FR-013).
7. **Prompt scope** — E2E tier only: placement `tests/e2e/<domain>/test_*.py`, exactly one `pytestmark = pytest.mark.shard_<name>`, explicit "do NOT run locally; the proof job verifies"; step 7 (verify FAILS) gains an E2E carve-out; other tiers untouched (FR-010).

## Post-design constitution re-check

Unchanged: no new violations introduced by the design; the extracted scripts *improve* test discipline relative to the PoC's inline python.
