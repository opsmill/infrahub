# Implementation Plan: Dynamic Versioning from Git Tags

**Branch**: `fac/dynamic-version-uxrrg` (feature pinned via `.specify/feature.json` → `specs/infp-566-dynamic-versions`) | **Date**: 2026-06-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/infp-566-dynamic-versions/spec.md`
**Plan baseline commit**: `5c08fd004` (current `develop` head) — re-verified; supersedes the spec's `2406fae3c` citations.

## Summary

Switch `infrahub-server` and `infrahub-testcontainers` from a static `[project].version` to a
build-time version derived from git tags (`infrahub-v*`), eliminating version-bump PRs and the
recurring `pyproject.toml`/`uv.lock` cross-branch merge conflicts. The resolver is **hatch-vcs**
(keeps the existing `hatchling` backend; FR-013), with fallback **`1.10.1.dev0`** and a
version-file baked into wheel+sdist (OQ-3). Runtime version surfaces already read installed
metadata, so US5 is verification-only. The substantive work is in the release/CI plumbing:
remove dead version-reading code, rework `update_helm_chart`/`update_docker_compose` to read
installed metadata (OQ-4) with a strict-`>` guard (FR-022), migrate every `uv version --short`
and tag-fetch-less checkout, add publish-time fallback/tag-match guards (FR-018), migrate the
post-release propagation trigger to tag pushes (FR-019), expose `.git/` to the Docker build via
a BuildKit bind mount (OQ-1, one Dockerfile), and rewrite `/cut-release` (FR-021). Cutover
ordering and a coordinated PR notice (FR-023) accompany the landing.

All open questions are resolved (see [research.md](./research.md)); OQ-2 was settled empirically.

## Technical Context

**Language/Version**: Python `>=3.12,<3.15` (root), `>=3.10` (testcontainers). Build/release
engineering change — no runtime feature code.
**Primary Dependencies**: `hatchling` (build backend, unchanged) + **`hatch-vcs`** (new
build-time dep, pulls `setuptools-scm`); `uv 0.11.6`; Invoke 2.2; `packaging`; towncrier;
GitHub Actions; Docker/BuildKit; Helm.
**Storage**: N/A (no database).
**Testing**: build-output verification (wheel/sdist metadata, version-file, lockfile),
CI workflow execution, and a unit-level check for the reworked release tasks where practical.
No new pytest DB/runtime suites. Frontend/E2E: N/A.
**Target Platform**: GitHub Actions CI, local dev checkouts, Docker images, PyPI, the
externally-owned Enterprise pipeline (assessment only, FR-015).
**Project Type**: build/release pipeline (packaging + CI/CD + release tasks). Not web/mobile.
**Performance Goals**: zero version-bump PRs/CI runs per release (SC-001/005); Docker final
image size MUST NOT regress (FR-020 gate).
**Constraints**: PEP 440 compliance always; build never fails on missing tag (US3); cutover
ordering — FR-019 and FR-021 land in the same commit/branch as FR-001/FR-008; maintenance-branch
hygiene (no newer main-line tag reachable from a release branch).
**Scale/Scope**: 2 `pyproject.toml` + 2 `uv.lock`; `tasks/utils.py` + `tasks/release.py`;
`.dockerignore` + `development/Dockerfile`; ~6 workflow files (publish-pypi, ci, release,
update-compose-file-and-chart, ci-docker-image, + the docker-publish callers); `.gitignore`;
`/cut-release`; docs (FR-012); a changelog fragment.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Most principles target data/schema/branch/query/frontend concerns that this build-config change
does not touch. Relevant gates:

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | N/A | No schema, no DB, no generated schema files touched. |
| II. Branch-Safe by Default | N/A (data); **addressed (process)** | No DB queries. The branch concern here is *maintenance-branch hygiene* (FR-012) — documented & guarded by FR-018(b)/FR-022. |
| III. Type Safety & Explicit Contracts | **PASS** | Reworked `tasks/*.py` keep full type hints (`str | None` etc.). No new untyped dicts. |
| IV. Test Discipline | **PASS** | Verification-driven (build outputs, CI, quickstart.md). Reworked release tasks get a unit-level check where practical; no runtime/DB code added. E2E N/A. |
| V. Query Performance | N/A | No queries. |
| VI. Security & Input Boundaries | **PASS (with watch)** | No user input/API. Security-relevant action: removing `.git*` from `.dockerignore` MUST NOT leak `.git/` into the published image — the BuildKit bind mount (OQ-1) keeps it transient; verified by quickstart step 5. No secrets committed. |
| VII. Simplicity & Maintainability | **PASS** | Net dead-code removal (`project_ver`, `get_version_from_pyproject`, `tomllib` block, `update_test_containers`, the tautological CI step). Exactly one new dep (`hatch-vcs`), justified by FR-013. Shared metadata helper serves ≥2 callers before extraction. |

**Dev-workflow gates**: changelog fragment required (operational change); `uv run invoke
format`/`lint`; `/pre-ci`; `docs.validate` (FR-012 docs). **New dependency** (`hatch-vcs`) is an
AGENTS.md "Ask First" item — it is the feature's core mechanism, minimal, and recorded in
research.md (FR-013).

**Frontend principles / Shared Components Inventory**: N/A — no UI in this feature.

**Gate result: PASS.** No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/infp-566-dynamic-versions/
├── plan.md              # This file
├── research.md          # Phase 0 — resolver choice, OQ-1..4, drift findings, empirical results
├── data-model.md        # Phase 1 — version entities & flows
├── quickstart.md        # Phase 1 — end-to-end validation guide
├── contracts/           # Phase 1 — build-config, release-tasks, ci-workflows, cut-release
│   ├── build-config.md
│   ├── release-tasks.md
│   ├── ci-workflows.md
│   └── cut-release-command.md
├── checklists/
│   └── requirements.md  # (existing) spec quality checklist
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT this command)
```

### Source Code (files this feature touches — repository root)

```text
pyproject.toml                                  # FR-001/003/008: dynamic version, hatch-vcs, fallback, version-file
python_testcontainers/pyproject.toml            # FR-002/003/008: same + raw-options.root=".."
uv.lock                                         # FR-008: regenerate
python_testcontainers/uv.lock                   # FR-008: regenerate
.gitignore                                      # OQ-3: ignore backend/infrahub/_version.py + testcontainers _version.py
backend/infrahub/__init__.py                    # US5: verify only (already importlib.metadata)
tasks/utils.py                                   # FR-009/010: delete project_ver, get_version_from_pyproject, tomllib block; add metadata helper
tasks/release.py                                 # FR-016/017/022: delete update_test_containers; rework helm/docker-compose tasks; strict-> guard
.dockerignore                                   # FR-020: stop excluding .git/ from build context
development/Dockerfile                           # FR-020: BuildKit bind mount of .git on the uv sync step (+ optional scoped COPY)
.github/workflows/publish-pypi.yml               # FR-014: fetch tags before uv build/publish
.github/workflows/ci.yml                         # FR-018: migrate uv version --short; remove/replace compare-versions step
.github/workflows/release.yml                    # FR-014/018: fetch tags; migrate reads; add fallback + tag-match publish guards
.github/workflows/update-compose-file-and-chart.yml  # FR-016/018/019/022: trigger→tag push, migrate reads, drop testcontainers step, main-line scope
.github/workflows/ci-docker-image.yml            # FR-014/020: fetch tags (reused by all docker publishers + release)
.agents/commands/cut-release.md                  # FR-021: rewrite (also reconcile the /cut-release Skill)
docs/...                                          # FR-012: local-dev + release-eng + maintenance-branch hygiene docs
changelog/+<fragment>.<type>.md                  # dev-workflow gate
```

**Structure Decision**: There is no `src/` feature module. The change is distributed across
build config, release tasks, CI workflows, the Docker build, and the release command, plus docs
and a changelog fragment. The file map above is the authoritative scope; `/speckit-tasks` will
order it respecting the cutover constraints below.

## Cutover ordering constraints (must hold in tasks.md)

1. **FR-001/FR-002/FR-008** (remove static version, add resolver, regenerate lockfiles) land
   together.
2. **FR-019** (propagation trigger → `infrahub-v*` tag push) lands in the **same commit** as, or
   an earlier commit on the same release-train branch than, FR-001/FR-002 — else the first
   release in the gap silently skips docker-compose/Helm propagation.
3. **FR-021** (`/cut-release` rewrite) lands in the **same change** as FR-001/FR-008 — else the
   first `/cut-release` after the change fails immediately.
4. **FR-022** (strict-`>` in `update_docker_compose`) lands with **FR-017**.
5. **FR-023** (open-PR cutover notice) precedes the merge of FR-008/FR-001 to `develop`.

## Complexity Tracking

> No Constitution violations. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
