# Implementation Report: E2E proof runs for the bug pipeline

**Spec dir**: `dev/specs/005-e2e-proof-runs` | **Ticket**: IFC-3059 | **Branch**: `e2e-proof-runs-ifc-3059`
**Base commit**: `bc252b196` (post-prep) → rebased onto `origin/stable` mid-run (see §6) | **Head commit**: `607e579c2`
**Status**: COMPLETE — all 22 tasks `[X]`, CI replay green end-to-end.

## 1. Chunk ledger

| # | Chunk | Tasks | Outcome | Commit(s) | Flagged upward |
|---|---|---|---|---|---|
| 1 | Setup: storage validation (orchestrator-run) | T001 | ✅ 1/1 | `65fc15d74`, `f7eb79efb` | **Release assets do NOT render inline** (direct `<img>`, `naturalWidth: 0`; control raw URL renders on the same page) → critique-X1 fallback to orphan-branch storage executed across spec/plan/data-model/contracts/tasks |
| 2 | Foundational scripts | T002–T006 | ✅ 5/5 | `23d3bb31d` | pyproject gained per-file-ignores for `.github/scripts/**` (repo runs ruff `select=ALL`); verdict script also treats `<skipped>` as inconclusive |
| 3 | Proof workflow | T007–T013 | ✅ 7/7 | `2cb0d37ed` | assets publish is `continue-on-error` (evidence best-effort); empty verdict defaults to inconclusive at embed |
| 4 | Pipeline prompts + locks | T014–T016 (+T015b) | ✅ 4/4 | `099266269` | gh-aw is v0.86.2 (locks were v0.81.3 → churn); **flagged the demotion design gap** that review then fixed |
| 5+6 | Demotion skip + cleanup workflow | T018 | ✅ | `380040431` (+ spec `6018a1974`) | (skip logic later removed — see review) |
| 7 | Gates + changelog | T019 | ✅ | `67e741618` | plan's changelog waiver contradicted AGENTS.md → housekeeping fragment added |
| Review fixes A | scripts/workflows | — | ✅ 15/15 items | `abfdaacf6` | orphan-repair keeps stale inner text as plain body text (never deletes user content) |
| Review fixes B | prompts + locks | — | ✅ 4/4 items | `4e8e7fe28` | marker form aligned on hidden HTML comments |
| Replay + docs | T017, T020, T021 | ✅ | `607e579c2` | see §"CI replay" |

Policy-D (demote-or-keep, US5/FR-015/T015b) was added mid-run at the user's direction (`1b93d7d00`); its semantics were corrected after review (`7fed3a37b`: the workflow never triggers on a demote push).

## 2. Tasks not completed

None — all 22 tasks are `[X]` in tasks.md.

## 3. Local-pass evidence

| Test id | Type | Run command | Passed at | Env | Verbatim pass line |
|---|---|---|---|---|---|
| 34 tests in `.github/scripts/tests/` (12 verdict + 10 embed at creation, 22→34 after review fixes; node ids in the chunk transcripts) | unit | `uv run pytest .github/scripts/tests/ -q` | 2026-08-27T10:01:26Z (final full run, post-review-fixes) | repo venv, py3.14.5, pytest 9.0.3, macOS | `============================== 34 passed in 0.19s ==============================` |
| `bug-agent-e2e-proof.yml` / `bug-agent-e2e-cleanup.yml` | e2e (CI) | quickstart step-3 replay on PR #10429 | 2026-08-27 (runs 33061938451 / 33067363784 / cleanup) | GitHub `ubuntu-latest` | deferred — local E2E not supported; **executed and green in CI** (see quickstart Results) |

Gates: ruff `All checks passed!`, mypy `Success: no issues found in 5 source files`, yamllint silent on both workflows, `invoke format` no-op, vale/markdown untouched paths.

## 4. CI replay (quickstart step 3, PR #10429 — closed scratch)

RED `red_confirmed` 4m16s (published-image path) with before screenshot; GREEN `green_confirmed` 6m55s (built image) with after screenshot; NOTE callout rewritten between phases; detection hard-failed correctly when the diff carried two tests (pre-rebase head); demotion push triggered no proof run; reviewer agent ran green with proof sections present; close → cleanup emptied `pr-10429/` from the assets branch; `AGENT_*` markers survived four embeds.

## 5. Review findings

| Sev | Finding | Outcome |
|---|---|---|
| HIGH | Embed failure skipped the gate (job red despite satisfied verdict) | Fixed (`abfdaacf6`): embed `continue-on-error` + `!cancelled()` + verify-step gate |
| HIGH | Demotion-skip was dead code; prompts described a "detection failure" that never happens (workflow doesn't trigger) | Fixed (`abfdaacf6` removed skip; `4e8e7fe28` corrected prompts; `7fed3a37b` corrected spec) |
| MED×4 | Body-race clobber, orphaned-marker deletion, cleanup 404-vs-failure, "Policy-D" spec-ID comment | All fixed (post-PATCH verify+retry, marker repair, 404-only tolerance, comment reworded) |
| LOW/SUGG×8 | timeouts, job name, pathspec direct-child, push retry, `$GITHUB_REPOSITORY`, reason-scan join, image comment, prompt drift | All fixed |
| Test gaps ×6 | attribute-only AssertionError, mid-body replace, malformed XML, error+pass, no-PATCH-when-unchanged, green image label | All added (22→34 tests) |
| Deferred | none | — |

## 6. Autonomous decisions

- **T001 run by the orchestrator** (validation + docs, no feature code) rather than a subagent.
- **Review before replay** (task order deviation) so the CI replay ran once, post-fixes.
- **Mid-run rebase**: the branch script had based the feature branch on the #3890 fix branch; the two foreign commits were rebased out (`--onto origin/stable`) and both branches force-pushed — surfaced by the replay's detection step finding two tests, i.e. the guard worked.
- **jira ticket IFC-3059 created** to satisfy the mandatory branch-naming hook.
- Housekeeping changelog fragment added despite the plan's waiver (AGENTS.md wins).
- Proof job intentionally NOT a required status check (demotion semantics); recorded in spec + PR body.

## 7. Suggested next steps

1. Open the feature PR (description drafted; references PoC #10411 and replay #10429).
2. After merge: exercise the demote-or-keep rule for real via the pending follow-up (demote the #3890 e2e test once #10412 merges).
3. Optional later: component-tier screenshots for cheap-class bugs; link Playwright traces for interaction bugs; run `speckit-opsmill-extract` on this spec dir.
