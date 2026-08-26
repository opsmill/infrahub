# Research: E2E proof runs for the bug pipeline

## R1. Screenshot hosting mechanism

**Decision**: Release assets on a single permanent prerelease (tag `bug-pipeline-assets`, marked prerelease so it never shows as "latest"), uploaded/deleted with `gh release upload` / `gh release delete-asset`.

**Rationale**:
- Images embedded in a PR description must be publicly fetchable URLs; GitHub has **no API** to upload issue/PR attachments (the `user-attachments` store is browser-session only), so hosting is mandatory.
- Release assets add **zero git history**, are **individually deletable**, and serve from `https://github.com/<repo>/releases/download/<tag>/<file>` with public access on a public repo. GitHub's camo proxy follows the 302 redirect, so they render inline in markdown.
- The PoC's orphan branch works but git history only grows (deletes don't shrink it), and pruning it via branch reset eventually kills the image URLs embedded in merged PRs.

**Cache-staleness trap and its fix**: camo caches an image by URL. Re-uploading a same-named asset (`--clobber`) keeps the URL, so a re-run could render the *old* screenshot. Therefore asset names embed the run id: `pr-<pr>-<phase>-<run_id>.png`. Every publish produces a fresh URL, the body embed replaces the old URL, and the publisher deletes the superseded asset(s) for that `pr-<pr>-<phase>-` prefix.

**Alternatives considered**:
- Orphan branch + delete-folder-on-close (PoC): rejected for unbounded history growth and the prune-vs-dead-URL tradeoff.
- GHA artifacts: auth-gated zip downloads; cannot render inline. Rejected.
- Check-run `output.images`: still requires an externally hosted `image_url`. Doesn't solve hosting.
- Dedicated assets repository: works but moves the problem and adds a second repo to operate.

**T001 validation outcome (2026-08-25) — DECISION REVERSED**: release assets do **not** render inline. GitHub does not camo-proxy `releases/download` URLs (same-origin); it emits a direct `<img src>` whose load fails in the browser (`naturalWidth: 0`; page CSP/redirect chain), verified on PR #10411 with a same-page control: the PoC's `raw.githubusercontent.com` images render at full width. **Fallback per critique X1 is in effect**: storage is the `bug-pipeline-assets` orphan branch (PoC-proven) behind the same naming/cleanup contract — path `pr-<pr>/<phase>-<run_id>.png`, embed URLs pinned to the publishing commit SHA (immutable, no cache staleness), superseded files and closed-PR folders deleted by commit. Known trade-off: git history grows by one small commit per publish; deletes bound the checkout, not the history. A manual orphan reset remains possible at the cost of killing embeds in old PRs.

**Superseded by T001** (kept for the record): the release must exist before the first upload. The publisher step runs `gh release create bug-pipeline-assets --prerelease --title "bug-pipeline assets" --notes "Screenshot store for bug-pipeline proof runs. Do not delete."` if missing (idempotent, `|| true` on already-exists).

## R2. Verdict extraction

**Decision**: Parse `playwright-junit.xml` (already emitted by `tests/e2e/pytest.ini` via `--junitxml`). Verdict rules, validated by the PoC:

| Phase | junit state | Verdict | Job result |
|---|---|---|---|
| RED | exactly 1 testcase, 1 `<failure>` whose message/text contains `AssertionError` | `red_confirmed` | pass |
| RED | testcase passed | `does_not_reproduce` | fail |
| RED | any `<error>`, non-assertion failure, 0 or >1 testcases | `inconclusive` | fail |
| GREEN | exactly 1 testcase, no failure/error | `green_confirmed` | pass |
| GREEN | anything else | `inconclusive` (or failing) | fail |

**Rationale**: pytest's junit output structurally separates assertion failures (`<failure>` on the call phase) from infrastructure errors (`<error>` on setup/teardown) — the PoC's first local run (compose boot flake → `error`) would have been classed inconclusive, and the real CI run produced `failure` + `AssertionError` text. Exit codes cannot make this distinction.

**Placement**: the verdict logic lives in a standalone script `.github/scripts/e2e_proof_verdict.py` with unit tests colocated (`.github/scripts/tests/test_e2e_proof_verdict.py`), executed by the proof workflow before use. This keeps the constitution's test-discipline principle for the one piece of real logic; the rest of the workflow is glue.

## R3. Image strategy per phase

**Decision**: RED pulls the newest published `opsmill/infrahub` release image from Docker Hub (resolved as the highest non-prerelease tag, with `INFRAHUB_TESTING_DOCKER_IMAGE=docker.io/opsmill/infrahub`, `INFRAHUB_TESTING_DOCKER_PULL=true`); GREEN builds with `uv run invoke dev.build` and runs with `INFRAHUB_TESTING_IMAGE_VER=local`, `INFRAHUB_TESTING_DOCKER_PULL=false`.

**Rationale**: the test-only PR is code-identical to `origin/stable`, so a published image reproduces the bug; skipping the build kept the PoC RED phase at 8m45s on `ubuntu-latest`. The GREEN phase must contain the fix, so it builds (8m04s in the PoC — the build is cheaper than expected on hosted runners). Tag resolution: `gh api repos/opsmill/infrahub/releases/latest --jq .tag_name` (strips leading `infrahub-v` if present) with a hard fallback to querying Docker Hub tags; if resolution fails the job falls back to building, because a missing image must not produce an inconclusive RED.

**Alternative considered**: building in both phases — simpler, but doubles RED cost and loses the validated fast path.

## R4. PR-description embedding

**Decision**: Marker-delimited sections, PATCHed idempotently (regex-replace between `<!-- E2E_PROOF:<PHASE>:BEGIN/END -->`; append the section if absent), exactly as the PoC did. A third marker pair `<!-- E2E_PROOF:NOTE:BEGIN/END -->` carries the expected-red explanation: written during RED ("the normal e2e jobs fail by design on this phase; the authoritative check is bug-agent-e2e-proof"), rewritten during GREEN ("fix phase: all jobs are expected to pass").

**Rationale**: proven to coexist with other body-editing bots (cubic) and to leave the `AGENT_*` phase markers untouched. Description-over-comment matches how the pipeline already communicates state and keeps the evidence where reviewers look first.

**Concurrency**: workflow-level `concurrency: bug-e2e-proof-<pr>` with `cancel-in-progress: true` — the newest push wins; a cancelled run never reaches its embed step (embed happens after the run completes).

## R5. Trigger and phase detection

**Decision**: `on: pull_request` (opened/synchronize/reopened) targeting `stable`, `paths: tests/e2e/**`, job-level `if: startsWith(head.ref, 'ai-bug-pipeline-')`. Phase from the PR body: `AGENT_FIX_COMPLETE` present → GREEN, else RED. Target test = `git diff --diff-filter=AM base...HEAD -- 'tests/e2e/**/test_*.py'` excluding `tutorial/`, must be exactly one file.

**Rationale**: mirrors the pipeline's existing marker protocol (the reviewer agent already keys on the same markers, FR-014); the PoC validated phase flipping via a body PATCH before push. `paths` keeps the job off backend-only pipeline PRs (FR-001).

## R6. Cleanup on PR close

**Decision**: A separate tiny workflow `on: pull_request: types [closed]` (same branch guard) that deletes every asset named `pr-<n>-*` from the `bug-pipeline-assets` release.

**Rationale**: closed-PR cleanup cannot live in the proof workflow (different event), and a dedicated workflow keeps permissions minimal (`contents: write` only).

## R7. gh-aw prompt propagation

**Decision**: Edit the shared prompts (`dev/bug-pipeline/test-writing.md`, `fix-implementation.md`) and the workflow copies (`.github/workflows/bug-agent-test.md`, `bug-agent-fix.md`), then run `gh aw compile` to regenerate both `.lock.yml` files and commit them together.

**Rationale**: the lock files embed a `body_hash` of the markdown; stale locks mean the running agents never see the prompt change. Local `gh aw` v0.81.6 vs lock-stamped v0.81.3 will churn the compiled files — expected and unavoidable; noted for the PR description.
