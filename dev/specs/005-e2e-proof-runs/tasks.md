# Tasks: E2E proof runs for the bug pipeline

**Input**: Design documents from `specs/005-e2e-proof-runs/` (plan.md, research.md, data-model.md, contracts/proof-workflow.md, quickstart.md)
**Reference implementation**: PoC PR #10411 — `.github/workflows/bug-e2e-proof.yml` on branch `poc-e2e-proof-3890` (read it before writing the production workflow; do not modify the PoC branch)

**Tests**: included — the two scripts carry unit tests per the plan's constitution check; workflow-level validation is the quickstart replay.

## Phase 1: Setup — validate the storage bet (critique X1, MUST run first)

- [X] T001 Validate release-asset inline rendering: create the permanent prerelease (`gh release create bug-pipeline-assets --prerelease --title "bug-pipeline assets" --notes "Screenshot store for bug-pipeline proof runs. Do not delete."`), upload any PNG, embed its `https://github.com/opsmill/infrahub/releases/download/bug-pipeline-assets/<file>` URL in a scratch PR/issue body, and confirm it renders inline. Record the outcome in `specs/005-e2e-proof-runs/research.md` under R1. **Outcome: rendering FAILED (direct `<img>` to `releases/download` is blocked; `naturalWidth: 0`, control raw URL renders at 1280px on the same page). Fallback executed: FR-008/data-model/contracts/T012/T018 rewritten to orphan-branch storage; the validation release and tag were deleted.**

## Phase 2: Foundational — the two tested scripts (block US1/US3/US4)

- [X] T002 [P] Implement `.github/scripts/e2e_proof_verdict.py` per contracts/proof-workflow.md: `--phase {red,green} --junit <path>`, stdout `verdict=`/`reason=` lines, exit 0 iff phase contract satisfied; junit rules from research R2 (assertion-failure detection via `<failure>` message/text containing `AssertionError`; `<error>` anywhere → inconclusive; testcase count must be exactly 1)
- [X] T003 [P] Unit tests in `.github/scripts/tests/test_e2e_proof_verdict.py` over crafted junit fixtures: RED+assertion→`red_confirmed`/exit 0; RED+setup-error→`inconclusive`/exit 1; RED+pass→`does_not_reproduce`/exit 1; RED+timeout-failure(no AssertionError)→`inconclusive`; GREEN+pass→`green_confirmed`/exit 0; GREEN+failure→exit 1; 0 or 2 testcases→`inconclusive`; missing report→`inconclusive`
- [X] T004 [P] Implement `.github/scripts/e2e_proof_embed.py` per contracts: owns marker pairs `E2E_PROOF:RED|GREEN|NOTE`; replace-in-place or append-once; fetch body via `gh api`, PATCH result; `--reason` truncated ≤200 chars and markdown-neutralized (critique E1); NOTE content phase-dependent (red → expected-red explanation naming `bug-agent-e2e-proof` as authoritative; green → all-jobs-expected-green)
- [X] T005 [P] Unit tests in `.github/scripts/tests/test_e2e_proof_embed.py` exercising the pure body-transform function: sections appended once when absent; replaced when present; second identical run is a no-op; `AGENT_TEST_COMPLETE`/`AGENT_FIX_COMPLETE` and all content outside markers byte-identical; third-party bot content preserved; NOTE rewritten on phase change; reason sanitization
- [X] T006 Make the script tests runnable and green locally with `uv run pytest .github/scripts/tests/ -v` (add `__init__.py`/conftest only if collection requires it; keep the scripts dependency-free beyond stdlib so no pyproject change is needed) and confirm `uv run ruff check .github/scripts/` and repo mypy settings pass on them

## Phase 3: User Story 1 — CI-verified E2E proof on pipeline PRs (P1) 🎯 MVP

**Goal**: on `ai-bug-pipeline-*` PRs touching `tests/e2e/`, a proof job enforces the RED/GREEN phase contract and embeds verdict + screenshot into the PR description.

**Independent test**: quickstart step 3 replay — scratch `ai-bug-pipeline-99999-quickstart` PR with a failing e2e test + test marker → job success with RED section; fix + fix marker → job success with GREEN section; negative: passing test in RED phase → job failure with `does_not_reproduce`.

- [X] T007 [US1] Write `.github/workflows/bug-agent-e2e-proof.yml` skeleton per the trigger contract: `pull_request [opened, synchronize, reopened]` on base `stable` with `paths: tests/e2e/**`; job `if: startsWith(head.ref, 'ai-bug-pipeline-')`; `concurrency: bug-e2e-proof-<pr>` + cancel-in-progress; permissions `contents: write`, `pull-requests: write`; timeout 45m; runs-on ubuntu-latest
- [X] T008 [US1] Add phase/target detection step (adapt from the PoC workflow): phase from `AGENT_FIX_COMPLETE` in the PR body (via env, never shell-interpolated); target test from `git diff --diff-filter=AM base...HEAD -- 'tests/e2e/**/test_*.py'` excluding `tutorial/`; hard-fail with explicit message unless exactly one file
- [X] T009 [US1] Add environment steps (python 3.12, uv sync --all-groups, `uv run playwright install --with-deps chromium`, tini) and a fast-fail step running `uv run pytest .github/scripts/tests/ -q` so a broken script never produces a wrong verdict
- [X] T010 [US1] Add image-selection steps per research R3: RED resolves the latest published image (`gh api repos/opsmill/infrahub/releases/latest` → tag, Docker Hub `docker.io/opsmill/infrahub`, `INFRAHUB_TESTING_DOCKER_PULL=true`) with fallback to `uv run invoke dev.build` when resolution/pull fails; GREEN always builds (`INFRAHUB_TESTING_IMAGE_VER=local`, pull=false)
- [X] T011 [US1] Add the run + verdict + gate steps: `tini -s -g -- uv run pytest -c tests/e2e/pytest.ini <test> --screenshot on` with captured exit code; verdict via `e2e_proof_verdict.py`; step summary line; final gate step fails the job unless the phase contract is satisfied; `actions/upload-artifact` of `test-results/` + `playwright-junit.xml` on `always()`
- [X] T012 [US1] Add screenshot publish step per the asset contract: newest `test-results/**/*.png` → commit as `pr-<pr>/<phase>-<run_id>.png` to orphan branch `bug-pipeline-assets` (checkout the branch into a subdir; delete the older `pr-<pr>/<phase>-*.png` in the same commit; push; capture the commit SHA for the raw URL); missing screenshot logs a notice and never fails the job (evidence is best-effort)
- [X] T013 [US1] Wire `e2e_proof_embed.py` into the workflow after publish (runs `if: always()` once phase is known), passing verdict/reason/run-url/image-url; verify against contracts that only owned sections change

## Phase 4: User Story 2 — agents may choose the E2E tier (P2)

**Goal**: pipeline prompts allow E2E reproductions with CI verification replacing the local verify-it-fails step, E2E tier only.

**Independent test**: read the four prompt files — E2E instructions present and scoped; other tiers unchanged; `gh aw compile` leaves a clean tree.

- [X] T014 [P] [US2] Update `dev/bug-pipeline/test-writing.md`: in step 5's E2E bullet add the proof-run path — place exactly one test under `tests/e2e/<domain>/test_*.py` with one module-level `pytestmark = pytest.mark.shard_<name>`; add an E2E carve-out to step 7 (do NOT run locally; push and the `bug-agent-e2e-proof` job verifies the failure; on `inconclusive` do not loop — escalate after two consecutive inconclusive runs on the same commit)
- [X] T015 [P] [US2] Update `dev/bug-pipeline/fix-implementation.md`: E2E repro verification is the proof job's GREEN phase, not a local run (keep local verification for every other tier)
- [X] T015b [US5] Add the demote-or-keep step (FR-015) to `dev/bug-pipeline/fix-implementation.md`: after GREEN, demote the e2e repro to the cheapest tier that still exercises the wiring the bug traversed (remove the e2e file in the same PR; the demoted test must target the dispatch/wiring seam, not the leaf component), or keep it by moving it under `tests/e2e/regressions/` with exactly one shard marker and a one-line justification that no cheaper tier can express the regression
- [X] T016 [US2] Mirror the same edits into `.github/workflows/bug-agent-test.md` and `.github/workflows/bug-agent-fix.md`, run `gh aw compile bug-agent-test bug-agent-fix`, and commit the regenerated `.lock.yml` files in the same commit (compiler v0.81.6 churn is expected; note it in the commit body)

## Phase 5: User Story 3 — expected-red communication (P3)

**Goal**: RED-phase PRs explain that the normal e2e jobs fail by design; GREEN-phase PRs stop claiming it.

**Independent test**: unit tests from T005 already assert NOTE phase behavior; quickstart replay confirms the rendered text on a live PR.

- [ ] T017 [US3] Review the NOTE section wording end-to-end on the replay PR (quickstart step 3): RED text names the failing-by-design jobs (`E2E-testing-*`) and the authoritative check; GREEN text replaces it; adjust copy in `.github/scripts/e2e_proof_embed.py` if the live rendering is unclear

## Phase 6: User Story 4 — bounded storage lifecycle (P3)

**Goal**: assets exist only for open pipeline PRs; no git branch grows.

**Independent test**: close the replay PR → its `pr-<n>-*` assets disappear; `bug-pipeline-assets` release remains; PoC orphan branch untouched by production code.

- [ ] T018 [US4] Write `.github/workflows/bug-agent-e2e-cleanup.yml`: `pull_request [closed]` + `startsWith(head.ref, 'ai-bug-pipeline-')` guard, permissions `contents: write` only, commits removal of the `pr-<pr>/` folder from orphan branch `bug-pipeline-assets` (tolerate absent branch/folder)

## Phase 7: Polish & validation

- [ ] T019 Run repo gates on everything touched: `yamllint` on both new workflows, `uv run ruff check` + repo mypy on `.github/scripts/`, `uv run invoke format`, and markdown lint on the edited prompt docs; fix findings
- [ ] T020 Execute the quickstart end-to-end replay (quickstart steps 3, 5, 6) on a scratch `ai-bug-pipeline-99999-quickstart` branch pair: RED success + section, GREEN success + section, negative `does_not_reproduce`, reviewer-agent non-regression, cleanup on close; record run links in `specs/005-e2e-proof-runs/quickstart.md` under a Results heading
- [ ] T021 Delete the scratch replay branch/PR artifacts and confirm `git status` clean, all commits pushed on `e2e-proof-runs-ifc-3059`

## Dependencies

- T001 gates everything (storage decision can rewrite T012/T013/T016's storage references).
- Phase 2 (T002–T006) blocks T009/T011/T013 (US1) and T017 (US3).
- US1 (T007–T013) blocks the replay halves of US3 (T017) and Phase 7 (T020).
- US2 (T014–T016) is independent of US1 code but T016's prompt text references the proof job name fixed in T007 — do T016 after T007.
- US4 (T018) independent after T001; validated in T020.

## Parallel execution examples

- After T001: T002+T003 ∥ T004+T005 (different files).
- After T007: T014 ∥ T015 ∥ T018.
- T019 partially parallel with T020 (lint local vs CI replay).

## Implementation strategy

MVP = Phase 1 + Phase 2 + US1 (T001–T013): the proof job working end-to-end on a replay PR. US2 makes agents use it, US3/US4 harden communication and lifecycle. Ship as one PR (the user asked for a single feature PR referencing PoC #10411), but the phases are independently revertable.
