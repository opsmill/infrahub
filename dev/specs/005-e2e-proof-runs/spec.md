# Feature Specification: E2E proof runs for the bug pipeline

**Feature Branch**: `e2e-proof-runs-ifc-3059`

**Created**: 2026-08-25

**Status**: Draft

**Input**: User description: "Integrate E2E proof runs into the bug pipeline — productionize the PoC from PR #10411 (CI-verified RED/GREEN reproduction runs with before/after screenshots embedded in the pipeline PR description), decide screenshot storage, update the pipeline prompts so agents may choose the E2E tier, and communicate the expected-red state of the normal e2e jobs on test-only PRs."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A frontend bug gets CI-verified E2E proof through the pipeline (Priority: P1)

A maintainer runs a frontend bug through the pipeline (`/bug-analyze` → `/bug-tdd` → `/bug-fix`). The test-writer agent chooses the E2E tier, writes a reproduction test, and opens the test-only PR without running the test locally. A CI proof job runs exactly that test, confirms it fails on its assertion, and embeds the failure screenshot ("before") in the PR description. After the fix agent pushes the fix, the proof job re-runs, confirms the test passes, and embeds the passing screenshot ("after"). The reviewer sees machine-verified FAIL→PASS evidence and both screenshots without leaving the PR.

**Why this priority**: This is the feature — the E2E tier is unreachable for the pipeline today because the test agent cannot boot the stack in its own runner. Everything else in this spec supports this journey.

**Independent Test**: Open a PR from an `ai-bug-pipeline-*` branch that adds one failing e2e test and carries the test-complete marker; observe the proof job confirm RED and embed the before screenshot. Push a fix and the fix-complete marker; observe GREEN confirmation and the after screenshot. (Exactly what PoC PR #10411 demonstrated.)

**Acceptance Scenarios**:

1. **Given** an `ai-bug-pipeline-*` PR to `stable` whose diff adds one e2e test and whose description contains the test-complete marker but not the fix-complete marker, **When** the proof job runs, **Then** it passes only if that test fails on an assertion, and the PR description gains a "before" screenshot and a RED-confirmed verdict line.
2. **Given** the same PR after the fix is pushed and the fix-complete marker added, **When** the proof job runs, **Then** it passes only if that test passes, and the PR description gains an "after" screenshot and a GREEN-confirmed verdict line.
3. **Given** a proof run where the test errors during setup (stack boot failure, fixture error, collection failure) or fails on something other than an assertion, **When** the verdict is computed, **Then** the job fails with an explicit "inconclusive" verdict and the pipeline does not treat the phase as satisfied.
4. **Given** a RED-phase run where the new test unexpectedly passes, **When** the verdict is computed, **Then** the job fails with a verdict stating the test does not reproduce the bug.

---

### User Story 2 - Pipeline agents can choose the E2E tier (Priority: P2)

The test-writer agent, following the pipeline prompts, selects the E2E tier when the bug warrants it: it writes the test in `tests/e2e/` with exactly one CI shard marker, does not attempt to run it locally, and relies on the proof job for the failure verification that other tiers do locally. The fix agent likewise relies on the proof job for GREEN verification of e2e tests.

**Why this priority**: Without prompt changes the agents will keep avoiding the E2E tier (their instructions demand a local failing run they cannot produce), so the proof job would never be exercised.

**Independent Test**: Read the updated prompts and confirm the E2E tier instructions replace local verification with CI verification, for the E2E tier only; other tiers' instructions are unchanged.

**Acceptance Scenarios**:

1. **Given** the test-writing instructions, **When** the agent picks the E2E tier, **Then** the instructions direct it to place the test under `tests/e2e/` with exactly one module-level shard marker, to skip local execution, and to open the PR for CI verification.
2. **Given** the test-writing instructions, **When** the agent picks a non-E2E tier, **Then** the local verify-it-fails requirement still applies unchanged.
3. **Given** the gh-aw workflow prompt copies, **When** the shared prompt files change, **Then** the workflow copies carry the same change and the compiled lock files are regenerated.

---

### User Story 3 - Reviewers are not misled by expected-red CI (Priority: P3)

On a test-only pipeline PR, the repository's normal e2e jobs fail because the new test fails by design. A reviewer looking at the PR understands immediately that this red state is expected for the RED phase and which check (the proof job) is the one that matters.

**Why this priority**: Without it, every pipeline PR with an E2E repro looks broken, reviewers chase phantom failures, and trust in the pipeline erodes. It is communication, not mechanics, so it ranks below the mechanics.

**Independent Test**: Open a RED-phase pipeline PR and confirm the explanation is present and accurate; confirm it no longer claims failures are expected once the fix phase starts.

**Acceptance Scenarios**:

1. **Given** a RED-phase pipeline PR with an e2e test, **When** a reviewer opens it, **Then** the PR clearly states that the normal e2e jobs are expected to fail during this phase and names the proof job as the authoritative check.
2. **Given** the same PR in the GREEN phase, **When** a reviewer opens it, **Then** the expected-red explanation no longer applies to the current phase (it is removed, updated, or clearly scoped to the RED phase).

---

### User Story 4 - Screenshot storage does not grow without bound (Priority: P3)

Screenshots are stored on a dedicated non-code orphan branch, pinned to immutable per-publish URLs. Each pipeline PR's images live in their own folder, superseded images are removed on every publish, and the folder is removed when the PR closes, so the store's tip stays bounded by open pipeline PRs. (Release-asset storage was the preferred option but failed inline-rendering validation — see the plan's validation-first decision.)

**Why this priority**: Hosting is mandatory (images in PR descriptions must be fetchable URLs; there is no API to upload issue/PR attachments), but unbounded growth is a maintenance liability, not a user-facing feature.

**Independent Test**: Run a proof phase, confirm the image URL serves the screenshot and renders in the PR description; close the PR, confirm the assets are removed; confirm no git branch accumulates image commits.

**Acceptance Scenarios**:

1. **Given** a completed proof run, **When** the screenshot is published, **Then** the embedded image renders inline in the PR description from an immutable URL.
2. **Given** a pipeline PR that closes (merged or not), **When** the cleanup runs, **Then** that PR's screenshots are deleted from the store.
3. **Given** the store after any publish or cleanup, **When** its tip is inspected, **Then** it contains folders only for open pipeline PRs.

### User Story 5 - Reproduction tests are demoted, not hoarded (Priority: P2)

After the fix is verified GREEN, the e2e reproduction is treated as evidence, not automatically as a permanent test. The fix agent leaves behind a regression test at the cheapest tier that can still exercise the wiring the bug traversed — usually demoting the e2e repro to a component or unit test in the same PR. The e2e test survives only when no cheaper tier can express the regression (backend-state, permission, branch or cache wiring), in which case it moves under `tests/e2e/regressions/` with its shard marker.

**Why this priority**: without a lifecycle policy, every pipeline bug appends one micro-test to the most expensive suite forever — eroding the hand-balanced CI shards and paying boot overhead on every e2e-triggering PR. This is the constitution's "tests at the appropriate level" applied to the pipeline.

**Independent Test**: read the updated fix-phase prompts — they require a demote-or-keep decision with a stated justification; on a demotable bug the final PR contains the cheaper-tier test and not the e2e repro; on an e2e-only bug the repro lands under `tests/e2e/regressions/`.

**Acceptance Scenarios**:

1. **Given** a GREEN-verified fix whose bug is expressible at a cheaper tier, **When** the fix phase completes, **Then** the PR contains a component/unit regression test targeting the wiring the bug traversed and the e2e reproduction is removed in the same PR.
2. **Given** a GREEN-verified fix that only reproduces with the full stack, **When** the fix phase completes, **Then** the e2e test is relocated under `tests/e2e/regressions/` keeping exactly one shard marker, with the keep justification stated in the PR.
3. **Given** the demoted test, **When** it targets a leaf component instead of the dispatch/wiring the bug traversed, **Then** review rejects it (coverage must not silently narrow).

---

### Edge Cases

- Proof run on a PR whose diff adds more than one e2e test file, or none (after the path filter matched a helper/conftest change): the job fails with an explicit verdict naming the problem — the pipeline contract is exactly one reproduction test.
- The new test fails on a non-assertion error that nevertheless proves the bug (e.g. a rendering timeout): out of scope for the verdict — it is inconclusive; the agent must sharpen the test to fail on an assertion.
- Re-runs of the same phase (new pushes, manual re-run): the PR-description embed is idempotent — one before image, one after image, refreshed rather than duplicated; the verdict line reflects the latest run.
- Concurrent runs on the same PR (rapid pushes): only the latest run's result stands; superseded runs must not interleave their body edits (concurrency control per PR).
- The PR description is edited by other bots or humans between runs: the embed only touches its own marker-delimited sections and must not corrupt the pipeline's phase markers or other content.
- Reviewer-agent compatibility: the proof job's body edits and the new sections must not break the existing reviewer triggers (`ai-bug-pipeline-*` + phase markers in the body).
- A backend-only pipeline bug (no e2e test in the diff): the proof job does not run at all; the existing pipeline behavior is unchanged.
- Demotion push (GREEN phase, the diff removes the e2e reproduction without adding/modifying one): the proof job skips successfully — the GREEN verdict from the pre-demotion run stands and the demoted cheaper-tier test is validated by the normal test jobs. In RED phase a deletion-only diff remains a hard failure.
- Release-asset store unavailable or upload fails: the verdict must still stand (evidence is best-effort; verification is not), and the job reports the missing screenshot rather than failing the phase for it.
- Inconclusive verdict (infra flake): a human or the reviewer re-runs the proof job; the test-writer agent escalates instead of looping after two consecutive inconclusive runs on the same commit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST run a proof job on pull requests from `ai-bug-pipeline-*` branches targeting `stable` whose diff touches `tests/e2e/`, and MUST NOT run it on other PRs.
- **FR-002**: The proof job MUST derive its expected outcome from the pipeline phase markers in the PR description: expect FAIL while the fix-complete marker is absent, expect PASS once it is present.
- **FR-003**: The proof job MUST run exactly the new/modified e2e test from the PR diff, and MUST fail with an explicit verdict when the diff does not contain exactly one such test file.
- **FR-004**: The RED verdict MUST be satisfied only when that single test fails on an assertion; setup/teardown errors, timeouts, collection failures, unexpected passes, or additional failing tests MUST yield a failing job with a distinct "inconclusive" (or "does not reproduce") verdict.
- **FR-005**: The GREEN verdict MUST be satisfied only when that single test passes.
- **FR-006**: Both phases MUST capture a screenshot of the test run (failure capture on RED, forced end-of-test capture on GREEN) and publish it to the screenshot store.
- **FR-007**: The proof job MUST embed the published screenshots and the verdict into the PR description inside marker-delimited sections, idempotently across re-runs, without altering the pipeline phase markers or content outside its sections.
- **FR-008**: Screenshots MUST be stored on the dedicated non-code orphan branch (`bug-pipeline-assets`), embedded via immutable commit-pinned URLs, with each publish removing the superseded image for that PR/phase. (Validation outcome: release-asset URLs do not render inline in PR descriptions — GitHub emits a direct, CSP-blocked image element for them — so the critique-X1 fallback to the PoC-proven storage is in effect; see research R1.)
- **FR-009**: The system MUST delete a PR's stored screenshots when that PR closes.
- **FR-010**: The pipeline prompts (shared `dev/bug-pipeline/` files and their gh-aw workflow copies) MUST allow the agents to choose the E2E tier: test placed in `tests/e2e/` with exactly one module-level shard marker, no local execution, CI verification via the proof job replacing the local verify-it-fails step — for the E2E tier only; all other tiers keep local verification. The compiled gh-aw lock files MUST be regenerated to match.
- **FR-011**: On RED-phase pipeline PRs with an e2e test, the system MUST surface an explanation that the repository's normal e2e jobs are expected to fail during this phase and that the proof job is the authoritative check; the explanation MUST NOT claim failures are expected once the GREEN phase starts.
- **FR-012**: The RED phase MUST use a published product image rather than building one (the test-only PR is code-identical to the base branch); the GREEN phase MUST build the image containing the fix.
- **FR-013**: Concurrent proof runs on one PR MUST be serialized or superseded such that the final PR description reflects only the latest run per phase.
- **FR-014**: The existing reviewer agent's triggers and gates MUST continue to work unchanged on pipeline PRs that carry the new proof sections.
- **FR-015**: The fix-phase instructions MUST require a demote-or-keep decision for the e2e reproduction after GREEN: demote to the cheapest tier that still exercises the wiring the bug traversed (removing the e2e repro in the same PR), or keep it under `tests/e2e/regressions/` with a stated justification that no cheaper tier can express the regression. The GREEN proof run MUST still have verified the fix against the e2e reproduction before any demotion happens.

### Key Entities

- **Proof run**: one CI execution bound to a pipeline PR and a phase (RED/GREEN); produces a verdict, optionally a screenshot, and a PR-description update.
- **Phase**: the pipeline state derived from the `AGENT_TEST_COMPLETE` / `AGENT_FIX_COMPLETE` markers in the PR description.
- **Verdict**: the machine judgment of a proof run — red-confirmed, green-confirmed, inconclusive, does-not-reproduce — the job's pass/fail follows from it and the phase.
- **Screenshot store**: the release-asset container holding per-PR before/after images; lifecycle bound to the PR (created on first proof run, emptied on PR close).
- **Pipeline PR**: the existing `ai-bug-pipeline-*` pull request created by the test-writer agent and reused by the fix agent; its description carries the phase markers, the proof sections, and the expected-red explanation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A frontend bug can travel the whole pipeline using an E2E reproduction with zero local test execution by the agents — demonstrated by at least one real bug fixed through the pipeline this way after release.
- **SC-002**: Each proof phase completes in under 15 minutes (PoC measured 8m45s RED / 8m04s GREEN).
- **SC-003**: A reviewer can see the bug and the fix without downloading anything: both screenshots render inline in the PR description.
- **SC-004**: Zero pipeline PRs proceed past the RED phase on an infrastructure failure — every non-assertion failure is surfaced as inconclusive.
- **SC-005**: The screenshot store carries assets only for open pipeline PRs (closed PRs' assets removed), and no git branch grows with image commits.

## Assumptions

- The PoC (PR #10411) is the validated reference: `ubuntu-latest` runners suffice for both phases; junit output distinguishes assertion failures from errors; marker-delimited body edits coexist with other bots editing the description.
- A published image close to `stable` HEAD is always available for the RED phase (the pipeline branches from `origin/stable`); minor drift between the published image and the suite at HEAD is acceptable for reproduction purposes.
- One reproduction test per pipeline PR is an existing pipeline contract, not introduced here.
- Screenshot evidence is best-effort: a missing screenshot never blocks a phase whose verdict is otherwise satisfied.
- The PoC's `bug-pipeline-assets` orphan branch and the PoC workflow on the PoC branch are left as-is (reference); production introduces its own workflow file and storage.
- `dev/guides/frontend/writing-e2e-tests.md` is already migrated upstream and is not touched by this feature.
- GitHub issue #3890 is fixed by PR #10412 and must not be auto-closed by this feature's PR.
