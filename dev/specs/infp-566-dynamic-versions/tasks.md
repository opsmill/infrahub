---
description: "Task list for Dynamic Versioning from Git Tags (infp-566)"
---

# Tasks: Dynamic Versioning from Git Tags

**Input**: Design documents from `specs/infp-566-dynamic-versions/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Plan baseline commit**: `5c08fd004` — all line numbers below are current as of this commit; **T001 re-verifies them before any edit** (the spec's original citations have drifted).

**Tests**: The spec does not request a TDD suite — this is a build/release-engineering change.
"Verification" here means build-output checks and CI runs (per quickstart.md), plus one
optional unit check for the reworked version-comparison logic. No pytest DB/runtime suite.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: User story served (US1–US6). Setup/Foundational/Polish carry no story label.

---

## ⚠️ Read first: this feature is a coordinated cutover, not an incremental story stack

Removing the static `[project].version` (FR-008) **simultaneously breaks every consumer that
reads it** — `uv version --short` in CI, `get_version_from_pyproject()` in the release tasks,
the `/cut-release` bump steps, and the propagation-trigger premise. Therefore the foundational
core (Phase 2) and the US6 plumbing (Phase 3) **MUST be committed together** (or as a tight
sequence on the same release-train branch). They cannot be merged independently without leaving
`develop` broken.

**Story → phase mapping**

| Story | Pri | Where implemented | Where verified |
|---|---|---|---|
| US1 release w/o bump PR | P1 | Phase 2 (core config) | Phase 4 |
| US2 merge w/o conflicts | P1 | Phase 2 (no static version; lockfiles) | Phase 5 |
| US3 build always usable (fallback) | P1 | Phase 2 (fallback) + Phase 3 (publish guards) | Phase 6 |
| US4 untagged dev build identifiable | P2 | Phase 2 (resolver scheme) | Phase 7 |
| US5 runtime/tooling read version | P2 | **no code change** (already importlib.metadata) | Phase 8 |
| US6 release orchestration works | P1 | Phase 3 (tasks, CI, Docker, cut-release) | Phase 9 |

**MVP = Phases 1–3 landed together** (delivers US1–US4 mechanics + keeps US6 green). US5 is
verification-only. Phases 4–9 are verification + cross-cutting that follow the cutover.

**Cutover ordering invariants (MUST hold):**
1. FR-001/FR-002/FR-008 land together (Phase 2).
2. FR-019 (trigger → tag push) lands in the same commit as FR-001/FR-002 (T019).
3. FR-021 (`/cut-release` rewrite) lands in the same change as FR-001/FR-008 (T024).
4. FR-022 strict-`>` lands with FR-017 (T010).
5. FR-023 PR notice precedes the merge to `develop` (T033).

---

## Phase 1: Setup & Pre-flight

**Purpose**: Re-baseline against current code and confirm the environment before editing.

- [X] T001 Re-verify every target file's current line numbers against HEAD (`pyproject.toml`, `python_testcontainers/pyproject.toml`, `tasks/utils.py`, `tasks/release.py`, `.dockerignore`, `development/Dockerfile`, the 5 workflow files, `.agents/commands/cut-release.md`); confirm the most recent `infrahub-v*` tag and that the chosen fallback `1.10.1.dev0` still sorts strictly above it. Record any drift. — **DONE: no drift from baseline `5c08fd004`; all cited line numbers verified. Latest tag `infrahub-v1.10.0`; `git describe` → `infrahub-v1.10.0-11-ge5c4a92f2`. Note: the `update-compose-…yml` `:66` "third `uv version`" the spec flagged is now a `commit-message` line — only 2 reads there (`:52,53`); 9 reads total across 3 files. `/cut-release` is a single file (no separate Skill).**
- [X] T002 [P] Confirm `uv` version is the pinned `0.11.6`; if it has been bumped, re-run the OQ-2 lockfile reproduction (research.md) and record the result before relying on "no version recorded". — **DONE: `uv 0.11.6` confirmed; OQ-2 holds (locks regenerated with no `version` line on either member).**
- [ ] T003 [P] Enumerate all open PRs (`gh pr list`) and stage the FR-023 cutover notice text (posted later in T033). — **DEFERRED with T033 (outward-facing cutover communication).**

---

## Phase 2: Foundational — Core dynamic versioning (delivers US1–US4 mechanics) 🎯

**Purpose**: Replace the static version with the hatch-vcs resolver in both packages. Blocking
prerequisite for everything else. See `contracts/build-config.md`.

**⚠️ CRITICAL**: Do NOT commit Phase 2 alone — it breaks version readers until Phase 3 lands too.

- [X] T004 Edit `pyproject.toml` (root, `infrahub-server`): remove `[project].version` (line 3); add `dynamic = ["version"]`; add `"hatch-vcs"` to `[build-system].requires`; add `[tool.hatch.version] source = "vcs"` + `fallback-version = "1.10.1.dev0"` with an inline comment "raise to next release after end-to-end validation"; add `[tool.hatch.version.raw-options].git_describe_command = ["git","describe","--dirty","--tags","--long","--match","infrahub-v*"]`; add `[tool.hatch.build.hooks.vcs].version-file = "backend/infrahub/_version.py"`. (FR-001/003/008)
- [X] T005 Edit `python_testcontainers/pyproject.toml` (`infrahub-testcontainers`): identical changes to T004, plus `raw-options.root = ".."` and `version-file = "infrahub_testcontainers/_version.py"`; remove `[project].version` (line 3). (FR-002/003/008)
- [X] T006 [P] Add the two generated version-files to `.gitignore`: `backend/infrahub/_version.py` and `python_testcontainers/infrahub_testcontainers/_version.py` (the hook header says "don't track in version control"). (OQ-3)
- [X] T007 Regenerate lockfiles: `uv lock` at repo root and in `python_testcontainers/`. Verify the `infrahub-server` and `infrahub-testcontainers` `[[package]]` entries carry **no** `version =` line. (FR-008/OQ-2) — **DONE: both locks regenerated; only change is removing the two `version = "1.10.0"` lines.**
- [X] T008 Build-smoke: `uv build` both packages on the current commit and on `infrahub-v1.10.0`; confirm exact-on-tag, dev-past-tag, and that `_version.py` appears in the sdist. (foundation gate; quickstart §1) — **DONE (live): both packages build; resolve to identical `1.10.1.dev11+ge5c4a92f2.d20260625` (dev-past-tag, sorts strictly after tag); `_version.py` baked into both sdists+wheels. Exact-on-tag is research-verified with this config (clean tag checkout needed; not exercisable pre-commit) and re-confirmed by T038.**

**Checkpoint**: Both packages resolve their version from git. US1–US4 mechanics exist (verified in Phases 4–7). Now fix all version consumers (Phase 3) before committing.

---

## Phase 3: User Story 6 — Release orchestration & CI (Priority: P1)

**Goal**: Every release-time task, CI workflow, Docker build, and the release command keep
working with the version sourced from git instead of `[project].version`.

**Independent Test**: Cut a release (staging/dry-run): wheels/images carry the tag version,
Helm `appVersion` + docker-compose tags propagate, no workflow silently skips, publish guards
fire on a faked fallback.

### 3a — Release tasks & dead-code removal (see `contracts/release-tasks.md`)

- [X] T009 [US6] In `tasks/utils.py`, add a typed helper returning `importlib.metadata.version("infrahub-server")` (single source for release-time reads). (FR-017/OQ-4) — **DONE: `get_project_version()`.**
- [X] T010 [US6] Rework `tasks/release.py::update_docker_compose` (~line 200): read the T009 helper instead of `get_version_from_pyproject()` (~line 204); tighten the version comparison from `if old_version != version` (~line 228) to a strict-greater (`packaging.version.Version`) check mirroring `update_helm_chart` (~line 141). (FR-017/FR-022)
- [X] T011 [US6] Rework `tasks/release.py::update_helm_chart` (~line 100): read the T009 helper instead of `get_version_from_pyproject()` (~line 114); preserve all current behavior (appVersion/version bump, `values.yaml` `prefectTag`, the `infrahub-enterprise` `infrahub` dependency update at ~line 184-191, the strict-`>`/non-prerelease gate). (FR-017)
- [X] T012 [US6] Delete `tasks/release.py::update_test_containers` (~lines 244-260) and remove its registration/import. (FR-016) — **DONE (Invoke auto-collects `@task`s, so deleting the function deregisters it; the workflow caller is removed in T019).**
- [X] T013 [US6] Delete `tasks/utils.py::get_version_from_pyproject()` (~111-114), `project_ver()` (~49-52, zero callers), and the `tomllib`/`tomli` import block (~6-12); remove the `get_version_from_pyproject` import from `tasks/release.py` (~line 14). (FR-009/FR-010) — **DONE: also removed now-unused `import sys`. The `tomli` dep stays in `pyproject` — `backend/infrahub/config.py` uses `tomllib` at runtime.**
- [X] T014 [P] [US6] Grep the repo for any remaining references to the deleted functions and for tests targeting them; delete dead tests if found (re-verify per FR-010). (FR-010) — **DONE: no remaining refs except the workflow caller (T019); no tests target them.**

### 3b — CI/CD workflow migration (see `contracts/ci-workflows.md`)

- [X] T015 [US6] `.github/workflows/publish-pypi.yml`: add `fetch-depth: 0` + `fetch-tags: true` to the checkout (~line 51) so `uv build`/`uv publish` (~lines 62/71) stamp the real tag version, not the fallback. (FR-014)
- [X] T016 [US6] `.github/workflows/ci-docker-image.yml`: add `fetch-depth: 0` + `fetch-tags: true` to the checkout (~line 80) — this workflow is reused by all docker publishers and `release.yml`. (FR-014/FR-020)
- [X] T017 [US6] `.github/workflows/release.yml`: add tags to checkout (~line 29); migrate the 5 `uv version --short` reads (~lines 49-52) to `importlib.metadata`, preserving the `is_prerelease`/`is_devrelease`/`version`/`major_minor_version` outputs. (FR-014/FR-018)
- [X] T018 [US6] `.github/workflows/release.yml`: replace the now-tautological tag-vs-pyproject check (~lines 60-64) with two **hard** publish-job guards reading `importlib.metadata` — (a) fail if the resolved version's **base** equals the fallback base (`1.10.1`) and it is a dev/local release; (b) fail if the resolved version ≠ the pushed tag's version segment. Both must be present (defense in depth). (FR-018)
- [X] T019 [US6] `.github/workflows/update-compose-file-and-chart.yml`: migrate the trigger from `push`/`pull_request` on `stable` `paths:[pyproject.toml]` (~lines 8-18) to **`push` on `infrahub-v*` tags**; add `fetch-depth: 0` + `fetch-tags: true` to the workflow's checkout (~line 34) — after the trigger moves to tag pushes, both the installed-metadata read and the FR-022 `git merge-base --is-ancestor <tag> stable` main-line check need full history + tags (a shallow tag checkout has neither `stable`'s history nor the tag's ancestry); migrate **every** `uv version --short` read to `importlib.metadata` (the spec flags `:52,53,66` — three; grep the file to confirm the current set, incl. the `:66` invocation); **preserve** the `is_prerelease == 0 && is_devrelease == 0` gate (~lines 55-60,77,85,89); **remove** the "Update Versions in python_testcontainers/pyproject.toml" step (~lines 61-62, FR-016); scope propagation to tags whose commit is an ancestor of `stable` (main-line only). **Must co-land with T004/T005** (cutover invariant 2). (FR-016/FR-018/FR-019/FR-022) — **REVISED 2026-07-02 (supersedes the tag-push design): propagation is now `workflow_dispatch` with a required `version` input, run BEFORE tagging — docker-compose.yml must already be up to date in the tagged commit (hard requirement); `release.yml` gains a `release.validate-docker-compose` publish gate. The invoke tasks accept an explicit `--version` (installed metadata is only the fallback), so tag fetch/mainline checks were dropped from this workflow.**
- [X] T020 [US6] `.github/workflows/ci.yml`: migrate `uv version --short` (~lines 405,409) to `importlib.metadata`; remove or replace the tautological "Compare package versions" step (~lines 403-418) with a static check that both `pyproject.toml` files declare the same hatch-vcs match pattern/config. (FR-018)
- [X] T021 [P] [US6] **DONE: 0 `uv version` left across workflows; docker publishers reuse the fixed `ci-docker-image.yml`; `push-bench`/`version-upgrade`/`uv-check`/`update-sdk-compatibility-docs` neither publish nor read the real package version, so no further checkouts need tags.** Audit every remaining checkout in `.github/workflows/` and add `fetch-depth: 0` + `fetch-tags: true` to any other job that builds, publishes, or reads a package version (none currently set tags). Additionally, grep all of `.github/workflows/` for `uv version` and confirm every occurrence has been migrated to `importlib.metadata` — enumerated line numbers have already drifted once, so do not rely on the spec's line list. (FR-014/FR-018)

### 3c — Docker version resolution (see OQ-1; only `development/Dockerfile` installs the project)

- [X] T022 [US6] `.dockerignore`: stop excluding `.git/` from the build context (~line 16 `.git*`); scope the pattern to `.gitignore`/`.gitmodules`/`.gitattributes` (and keep the docs `.git` artifacts excluded) so `.git/HEAD`, `refs/`, `packed-refs`, `objects/` are reachable. (FR-011/FR-020) — **DONE: `.git*` → `.gitignore`/`.gitmodules`/`.gitattributes`/`.github` (`.github` re-added since `.git*` previously matched it; `.git/` now reachable).**
- [X] T023 [US6] `development/Dockerfile`: add `--mount=type=bind,source=.git,target=.git` to the project-installing `uv sync --frozen --no-dev` step (~line 122) so the resolver reads git transiently; ensure `.git/` is NOT persisted in the final image (bind mount handles this; optionally replace the broad `COPY . ./` at ~line 121 with scoped COPYs). (FR-020) — **DONE. ⚠️ DEVIATION (empirically required, not optional): `.dockerignore` filters the bind-mount source, so `.git/` MUST be un-ignored for the mount to work — but then plain `COPY . ./` drags `.git/` into the image (verified with a BuildKit test). Fix: `# syntax=docker/dockerfile:1-labs` + `COPY --exclude=.git . ./` + bind-mount `target=/source/.git`. Verified: resolver reads `.git`, `.git/` absent from image, all source files present. (`git config --add safe.directory '*'` already set in the backend stage.)**
- [X] T024 [P] [US6] Re-grep all Dockerfiles for a project install; confirm `.devcontainer/Dockerfile` and `utilities/benchmark/Dockerfile` still do not `uv sync`/build the project (no change needed). (FR-020 scope) — **DONE: only `development/Dockerfile` runs `uv sync` (line 117 deps-only/no resolver; line 127 project install with the bind mount). The other two don't install the project.**

### 3d — Release command (see `contracts/cut-release-command.md`)

- [X] T025 [US6] **DONE: rewritten — version from `git describe --tags --match 'infrahub-v*' --abbrev=0`, no `uv version`/pyproject bump, flow = determine→towncrier→commit→annotated `infrahub-v<new>` tag→push; states no pyproject edit. Added `Bash(git:*)` to allowed-tools. No separate `/cut-release` Skill exists — this is the single source.** Rewrite `.agents/commands/cut-release.md`: determine the new version from `git describe --tags --match 'infrahub-v*' --abbrev=0` (+patch increment or `$ARGUMENTS`); remove all `uv version`/`pyproject.toml`-bump steps; keep pre-flight (fragment count, branch report, towncrier draft, `AskUserQuestion`); flow becomes determine→towncrier build→commit changelog→annotated `infrahub-v<new>` tag→push; state explicitly that no `pyproject.toml` edit occurs. Reconcile the registered `/cut-release` Skill so it agrees. **Must co-land with T004** (cutover invariant 3). (FR-021) — **REVISED 2026-07-02: /cut-release now also (a) bumps `fallback-version` in both pyprojects to the released version's next patch + `.dev0` (the one pyproject edit it makes), and (b) updates + validates docker-compose.yml before tagging (`release.update-docker-compose` / `release.validate-docker-compose --version`), matching the new pre-tag propagation flow.**

**Checkpoint**: All version consumers fixed. Phase 2 + Phase 3 are now committable together.

---

## Phase 4: User Story 1 verification — Release without bump PR (Priority: P1)

**Independent Test**: tag the release commit, build both packages, metadata reports the tag version, no `pyproject.toml` edit required.

- [ ] T026 [US1] On a commit tagged `infrahub-v<X>`, build `infrahub-server` and `infrahub-testcontainers`; assert both report exactly `<X>` and that no commit modified `[project].version`. (quickstart §1; FR-005) — **DEFERRED (post-cutover): needs a clean checkout exactly on a tag; cannot be exercised pre-commit (working tree dirty). Covered by the T038 staging dry-run / first release. Partially established: research.md empirically verified exact-on-tag → `<X>` with this exact config; `[project].version` is removed (verified).**

---

## Phase 5: User Story 2 verification — Merge without version conflicts (Priority: P1)

**Independent Test**: merge `stable`↔`develop` (and a `release-x.y`↔`develop`) with no version-related conflict.

- [ ] T027 [US2] Merge `stable` into `develop` (and vice versa) after the change; assert no conflict on `[project].version` (absent in both) and no `uv.lock` version-drift conflict; re-confirm no `version` recorded for the dynamic members. (quickstart §3; FR-008/OQ-2) — **DEFERRED (post-cutover, cross-branch): the structural precondition is verified — `[project].version` is absent from both pyproject files and no `version` line exists for either dynamic member in either lock — so the version-conflict class is eliminated by construction. The live cross-branch merge is a post-landing gate.**

---

## Phase 6: User Story 3 verification — Build always usable + publish guards (Priority: P1)

**Independent Test**: a checkout with no reachable tag builds successfully on the fallback; the publish guards reject a fallback/mismatched build.

- [ ] T028 [US3] In a shallow clone (no `infrahub-v*` tag) build both packages; assert success with a fallback-derived version (build never fails). Then exercise the T018 guards: a faked no-tags publish path and a resolved≠tag path MUST both fail the workflow. (quickstart §2, §8; FR-003/FR-004/FR-018) — **DEFERRED (guards need CI): build-never-fails-on-missing-tag is research-verified with this config and consistent with the live builds here. The two publish guards exist in `release.yml` (fallback-base + tag-match); their firing must be exercised in CI (T038).**

---

## Phase 7: User Story 4 verification — Untagged dev build identifiable (Priority: P2)

**Independent Test**: N commits past a tag yields a PEP 440 dev/local version sorting strictly after the tag.

- [X] T029 [US4] From a commit several commits past `infrahub-v1.10.0`, build a package; assert the version contains a dev/local segment (`1.10.1.devN+g<hash>`) and sorts strictly after the tag. (quickstart §1; FR-006) — **DONE (live): built `1.10.1.dev11+ge5c4a92f2.d20260625` (11 commits past the tag); `is_devrelease=True`, has a local segment, and `Version(...) > Version('1.10.0')`.**

---

## Phase 8: User Story 5 verification — Runtime/tooling read the version (Priority: P2)

**Independent Test**: every runtime surface matches the installed metadata version. (No code change — `backend/infrahub/__init__.py` already uses `importlib.metadata`.)

- [ ] T030 [US5] Install a build from a tagged commit; assert `importlib.metadata.version("infrahub-server")` equals `from infrahub import __version__`, `/api/info`, GraphQL `InfrahubInfo`, worker labels, and log headers; assert a Docker image built from a tagged commit reports the same version. (quickstart §4-5; FR-009 verification) — **DEFERRED (needs running server/image): partially verified live — `importlib.metadata.version("infrahub-server")` == `infrahub.__version__` (already metadata-based, no change) == `infrahub_testcontainers.__version__` == `get_project_version()`, all `1.10.1.dev11+...`. `/api/info`, GraphQL `InfrahubInfo`, worker labels, log headers, and the Docker-image read require a running stack — post-cutover gate.**

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T031 [P] Documentation (FR-012): add local-dev rules (`git fetch --tags` on fresh clones; editable-install version staleness — re-sync after switching commits) and the maintenance-branch hygiene rule (never merge a newer main-line tag into a `release-x.y` branch; cherry-pick patches) to the relevant `docs/` and `dev/` pages. — **DONE: `dev/guidelines/git-workflow.md` (new Versioning section + Critical Rule) and `docs/docs/development/git-best-practices.mdx` (Versioning subsection + updated Release workflow to drop the version bump).**
- [X] T032 [P] Add a Towncrier changelog fragment in `changelog/` (Housekeeping/Changed) describing the move to dynamic versioning and the new local-build expectations. — **DONE: `changelog/+dynamic-versioning-from-git-tags.housekeeping.md`.**
- [ ] T033 FR-023 cutover: post the staged notice (T003) on every open PR (cutover date, rebase requirement, `uv lock` regeneration from root + `python_testcontainers/`, guidance for PRs touching the changed files), set a non-blocking deadline. **Before merging Phase 2/3 to `develop`** (cutover invariant 5). — **DEFERRED (outward, needs sign-off): posting on every open PR is an outward action gated on the maintainer's go-ahead and the chosen cutover date. Not executed by this implementation run.**
- [ ] T034 FR-015 Enterprise assessment: open a tracked coordination item with the Enterprise-pipeline owners (tag-fetch posture, any `uv version` usage); confirm the `infrahub-enterprise` Helm dependency still flows from the installed-metadata input (T011); record findings before merge (remediation may follow). — **DEFERRED (outward): cross-team coordination item. Repo-side fact confirmed: `update_helm_chart` still updates the `infrahub-enterprise` chart's `infrahub` dependency from the installed-metadata input (logic preserved in T011).**
- [ ] T035 FR-020 image-size gate: measure `development/Dockerfile` final image size before vs. after; confirm the final image size does not increase versus the pre-change build (treat >1% / a few MB as a regression, since the bind-mounted `.git/` is transient) and that `.git/` is absent from the image (inspect the image filesystem / `docker run … ls -la /.git` returns nothing). (quickstart §5) — **DEFERRED (needs full image build): the mechanic is BuildKit-verified in an isolated test — `COPY --exclude=.git` + bind mount keeps `.git/` out of the image while the resolver reads it. The before/after size measurement on the real `development/Dockerfile` is a post-cutover gate.**
- [X] T036 [P] (Optional) Add a unit test for the `update_docker_compose` strict-`>` comparison logic if a `tasks/` test harness exists; else note skipped. — **SKIPPED per condition: no `tasks/` test harness exists (the repo's `test_tasks.py` files target backend Prefect tasks, not Invoke tasks; there is no `tasks/tests/`). The strict-`>` logic mirrors the long-standing `update_helm_chart` gate.**
- [X] T037 Run `/pre-ci` (format, lint, unit) and `uv run invoke docs.validate`; ensure clean. Confirm the cutover invariants held (FR-001/008 + FR-019 + FR-021 in one commit/branch). — **DONE (locally-runnable subset): `invoke format` clean; `main.lint` (ruff) ✅; `uv lock --check` ✅ both packages; ty reports 0 diagnostics on changed files (the 486 are pre-existing `infrahub_sdk`-unresolved noise from the un-provisioned submodule in this sandbox); `docs.validate` is blocked by the same missing `infrahub_sdk` import — my change touches no generated-doc source so it cannot introduce staleness. `docs.format/lint` need `markdownlint-cli2`/`vale` (not installed locally). Unit suite out of scope (no runtime code changed, per plan). Cutover invariants hold: FR-001/002/008 (pyproject + locks), FR-019 (tag-push trigger), FR-021 (cut-release) are all staged together on this branch. ⚠️ Re-run full `/pre-ci` + `docs.validate` in CI / a submodule-provisioned env before merge.**
- [ ] T038 [US6] **Pre-merge dry-run release** (staging branch / scratch repo, before the cutover merge): push a throwaway `infrahub-v<X>` tag; confirm `update-compose-file-and-chart.yml` fires on the tag push, propagates `docker-compose.yml` image tags + Helm `appVersion`, the FR-018 publish guards **pass** on a real tag (happy path, not just the faked-failure path in T028), and no workflow silently skips. Tear down the staging tag afterward. Closes the SC-006 / US6-independent-test gap otherwise only verified by the first production release. (SC-006; US6 Independent Test) — **DEFERRED (outward, needs CI + tag push): this is the recommended pre-merge gate. It must be run by a maintainer on a staging branch/scratch repo before the cutover merges to `develop`.**

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies.
- **Phase 2 (Foundational core)**: after Phase 1. Blocks everything.
- **Phase 3 (US6 plumbing)**: after Phase 2 (reads the new resolver) — but **committed together** with Phase 2.
- **Phases 4–8 (US1–US5 verification)**: after Phases 2+3 are landed; independent of each other → parallelizable.
- **Phase 9 (Polish)**: docs/changelog (T031/T032) can start anytime; T033 gates the merge; T038 (staging dry-run) precedes the cutover merge; T035/T037 after the cutover.

### Critical co-land set (one commit / one branch)

`T004, T005, T006, T007` + all of `T009–T025` + (regenerated lockfiles). Committing any subset
leaves `develop` broken. T033 (PR notice) precedes this merge.

### Within Phase 3

- T009 (helper) before T010/T011 (consumers).
- T010/T011 before T012 (delete `get_version_from_pyproject` only after callers reworked).
- T013 after T009–T012 (delete dead code last).
- Workflow tasks (T015–T021) are independent of the release-task tasks → parallelizable across files.
- Docker tasks (T022–T024) independent of workflow/release-task tasks.
- T025 (cut-release) independent of the above.

### Parallel opportunities

- Phase 1: T002, T003 in parallel.
- Phase 2: T006 in parallel with T004/T005; T007 after T004/T005.
- Phase 3: 3a (T009–T014), 3b (T015–T021), 3c (T022–T024), 3d (T025) are largely independent file sets — different developers can take a sub-phase each. Within 3b, T015/T016/T017+T018/T019/T020/T021 touch different files (mind that T017 and T018 both edit `release.yml`).
- Phases 4–8: all verification phases run in parallel once the cutover lands.
- Phase 9: T031, T032, T036 in parallel.

---

## Parallel Example: Phase 3 sub-phases

```bash
# Different file sets — assign in parallel after Phase 2:
Dev A (3a): tasks/utils.py, tasks/release.py            # T009–T014
Dev B (3b): .github/workflows/*                          # T015–T021 (T017/T018 share release.yml — same dev)
Dev C (3c): .dockerignore, development/Dockerfile        # T022–T024
Dev D (3d): .agents/commands/cut-release.md              # T025
```

---

## Implementation Strategy

### MVP = the coordinated cutover

1. Phase 1 (re-baseline).
2. Phase 2 (core config) **and** Phase 3 (all consumers) edited together.
3. Regenerate lockfiles; build-smoke (T008); local verification (Phases 4–8 quickstart checks); run T038 (staging dry-run) to exercise tag-push propagation + publish guards before merging.
4. Post FR-023 PR notice (T033).
5. Commit the whole co-land set; merge to `develop`.
6. First real release exercises US1/US6 end-to-end (SC-001/SC-006).

### Why not incremental-by-story

US1–US4 are emergent properties of the same config change; they cannot be shipped one at a
time. US5 needs no code. US6 must co-land or CI breaks immediately. The only meaningful
increments are *verification gates*, run after the single cutover — not separately shippable
stories.

---

## Notes

- `[P]` = different files, no incomplete-task dependency.
- `[Story]` labels give traceability; the foundational core (Phase 2) is what actually delivers US1–US4.
- FR/OQ IDs are intentionally referenced here (tasks.md is a spec artifact); do **not** carry them into source comments (per `.agents/rules/code-doc-style.md`).
- Line numbers are `5c08fd004`-current; T001 re-verifies before editing.
- Commit the critical co-land set as one logical change; do not push partial cutovers to `develop`.
