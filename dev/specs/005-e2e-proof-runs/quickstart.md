# Quickstart: validating E2E proof runs

## Prerequisites

- `gh` authenticated with write access to `opsmill/infrahub`.
- The reference behavior to compare against: PoC PR [#10411](https://github.com/opsmill/infrahub/pull/10411) (RED run 32873414287, GREEN run 32874468897).

## 1. Unit-verify the verdict logic (seconds, local)

```bash
uv run pytest .github/scripts/tests/test_e2e_proof_verdict.py -v
```

Expected: all cases pass — assertion failure→`red_confirmed`, setup error→`inconclusive`, RED pass→`does_not_reproduce`, GREEN pass→`green_confirmed`, multi-test and missing-report→`inconclusive`.

## 2. Dry-run the embed script against a scratch body (local)

Feed it a body containing the `AGENT_TEST_COMPLETE` marker and third-party bot content; run twice with the same inputs; diff. Expected: sections present exactly once, second run is a no-op, everything outside the markers byte-identical.

## 3. End-to-end replay (CI, ~20 min total)

Replay the PoC scenario on a scratch branch pair:

1. Branch `ai-bug-pipeline-99999-quickstart` from `origin/stable`; commit a deliberately failing e2e test (the PoC test `tests/e2e/form/test_long_text_attribute.py` reverted-fix variant works, or any test asserting an impossibility with an `assert`); open a draft PR to `stable` whose body contains `<!-- AGENT_TEST_COMPLETE -->`.
2. Expect: `bug-agent-e2e-proof` runs, ends **success**, PR body gains the RED section (verdict + before image rendering inline) and the NOTE section; the image URL is a `releases/download/bug-pipeline-assets/pr-<n>-red-<run>.png` asset.
3. Push a commit that makes the test pass; PATCH the body to add `<!-- AGENT_FIX_COMPLETE -->` **before** pushing.
4. Expect: proof job runs GREEN, ends **success**, GREEN section embedded, NOTE rewritten; a new asset `pr-<n>-green-<run>.png` exists.
5. Negative check: re-run the RED-phase run on the fixed code (or push a passing test in RED phase) — expect job **failure** with `does_not_reproduce`.
6. Close the PR. Expect: cleanup workflow deletes both `pr-<n>-*` assets from the `bug-pipeline-assets` release; the release itself remains.

## 4. Prompt/lock consistency

```bash
gh aw compile bug-agent-test bug-agent-fix
git status --short .github/workflows/
```

Expected: clean tree (locks already regenerated and committed with the prompt edits).

## 5. Reviewer-agent non-regression

On the replay PR from step 3 (which carries proof sections + both markers): confirm the Bug reviewer agent workflow still evaluates its gates normally (it triggers on `ai-bug-pipeline-*` + markers) and is not confused by the new sections.

## Results (2026-08-27 replay, PR #10429)

| Step | Outcome |
|---|---|
| RED phase | `red_confirmed` in 4m16s, published-image path, before screenshot embedded — [run 33061938451](https://github.com/opsmill/infrahub/actions/runs/33061938451) |
| GREEN phase | `green_confirmed` in 6m55s incl. image build, after screenshot embedded, NOTE rewritten — [run 33067363784](https://github.com/opsmill/infrahub/actions/runs/33067363784) |
| Detection guard | Two e2e tests in the diff → hard fail with explicit message ([run 33061729412](https://github.com/opsmill/infrahub/actions/runs/33061729412), from the pre-rebase head) |
| Demotion push | No proof run triggered on the deletion-only head, as specified |
| Reviewer agent | Ran and completed on the replay PR with the proof sections present (non-regression) |
| Close + cleanup | `bug-agent-e2e-cleanup` succeeded; assets branch tip holds no `pr-10429/` folder |
| Markers | `AGENT_TEST_COMPLETE` / `AGENT_FIX_COMPLETE` intact through four body embeds |
