# Feature Specification: Dynamic Versioning from Git Tags

**Feature Branch**: `dynamic-versions-infp-566`
**Created**: 2026-05-11
**Status**: Draft
**Jira**: [INFP-566](https://opsmill.atlassian.net/browse/INFP-566) · Implements epic [IFC-2530](https://opsmill.atlassian.net/browse/IFC-2530)
**Reference PR**: [opsmill/infrahub#8974](https://github.com/opsmill/infrahub/pull/8974) (closed, partial reference implementation)
**Code references baseline**: `develop` at commit [`2406fae3c`](https://github.com/opsmill/infrahub/commit/2406fae3c49ac9661cf6c486e99efd0dea7b773e) (2026-05-11). All file path + line number citations in this spec ("at spec time") are anchored to this commit; expect drift on any later baseline and re-verify before relying on a specific line.
**Input**: Switch `infrahub-server` and `infrahub-testcontainers` to dynamic versioning derived from git tags so that release engineers and developers stop paying the cost of dedicated version-bump PRs and recurring `pyproject.toml`/`uv.lock` merge conflicts across long-lived branches.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Release Without Version-Bump PR (Priority: P1)

A release engineer cuts a new Infrahub release by creating an annotated git tag matching `infrahub-v<version>` (e.g., `infrahub-v1.10.0`). Build artifacts produced from that tag are stamped with the matching version automatically, with no edits to `pyproject.toml` and no separate version-bump PR triggering the CI pipeline.

**Why this priority**: This is the primary pain point INFP-566 was opened to solve. Every release today requires a dedicated bump PR that triggers a full CI run (significant minutes per release) and adds a touchpoint to coordinate. Removing the bump PR removes the most visible release-day cost.

**Independent Test**: From a clean checkout, the release engineer creates an `infrahub-v1.10.0` tag on the release commit, then runs the build for both `infrahub-server` and `infrahub-testcontainers`. The resulting wheels/sdists report version `1.10.0` in their package metadata, and no commit modifying `pyproject.toml` is required between cutting and building.

**Acceptance Scenarios**:

1. **Given** a commit tagged exactly `infrahub-v1.10.0`, **When** the `infrahub-server` package is built, **Then** the produced artifact's package metadata reports version `1.10.0`.
2. **Given** the same tagged commit, **When** the `infrahub-testcontainers` package is built (it lives in a subdirectory), **Then** the produced artifact's package metadata also reports version `1.10.0`.
3. **Given** a release commit, **When** the release is cut, **Then** no separate PR modifying `[project].version` in either `pyproject.toml` is required as part of the release process.

---

### User Story 2 - Merge Across Branches Without Version Conflicts (Priority: P1)

A developer merges between `stable`, `develop`, and an active `release-x.y` branch. The merge does not produce conflicts caused by divergent static `version` fields in `pyproject.toml` or by version-derived entries in `uv.lock`, because no branch carries a static version value that differs from another.

**Why this priority**: The Jira ticket cites #8965 as a recent example, and the team treats these conflicts as a persistent, predictable tax on every cross-branch merge. Eliminating this class of conflict is half of the business case for the change and is independently valuable even without the release-engineering win.

**Independent Test**: Take the current `stable` and `develop` branches (which differ today in their hardcoded version) after the change has landed; merge `stable` into `develop` (or vice versa) and observe that neither `pyproject.toml` produces a version-related conflict and that `uv.lock` does not require resolution caused by version drift.

**Acceptance Scenarios**:

1. **Given** `stable` and `develop` after the change is merged into both, **When** one is merged into the other, **Then** there is no conflict on the `version` field in either `pyproject.toml` (because no static `version` exists in either branch).
2. **Given** a `release-x.y` branch and `develop` after the change, **When** they are merged in either direction, **Then** there is no version-related conflict in `uv.lock`.

---

### User Story 3 - Build Always Produces a Usable Version (Priority: P1)

A build is triggered in any supported environment (CI, local checkout, Docker image build, Enterprise pipeline). The build always produces an artifact with a valid, [PEP 440](https://peps.python.org/pep-0440/)-compliant version string, even when no `infrahub-v*` tag is reachable in the local git history.

**Why this priority**: The reference PR explicitly fails the build when no tag is reachable. The Jira ticket flags this as Open Issue #1 and asks for a fallback safety net. Falling back loudly to a known sentinel version is strictly safer than failing every build in any clone that does not have the tag history (shallow clones, forks, archived snapshots, environments that consume the source as a tarball, the Enterprise pipeline whose tag posture is currently unknown).

**Independent Test**: In a checkout where no `infrahub-v*` tag is reachable (e.g., a shallow clone or a snapshot with tags pruned), build each package. The build succeeds and the resulting artifact reports the configured fallback version.

**Acceptance Scenarios**:

1. **Given** a checkout with no reachable `infrahub-v*` tag, **When** either package is built, **Then** the build succeeds and the artifact reports the configured fallback version (initially `1.10.0.dev0`).
2. **Given** a checkout with a reachable tag `infrahub-v1.10.0`, **When** either package is built, **Then** the fallback is not used and the artifact reports `1.10.0`.
3. **Given** the build configuration files, **When** they are inspected, **Then** the fallback value is `1.10.0.dev0` and is accompanied by an inline comment noting that it must be raised to `1.10.0` after the change has been validated end-to-end.

---

### User Story 4 - Untagged Development Build Has Identifiable Version (Priority: P2)

A developer or CI job builds the packages from an untagged commit on `develop` or a feature branch. The resulting artifact carries a version that is PEP 440-compliant, clearly identifies the artifact as a development build, and is distinguishable from a real release.

**Why this priority**: Development builds are produced constantly (CI smoke tests, local experimentation, nightly artifacts). They must not collide with released versions in any installer or registry, and they must be greater than the previous release so that ordering remains intuitive. This is a standard outcome of any setuptools-scm-derived scheme but must be explicitly preserved.

**Independent Test**: From a checkout three commits past `infrahub-v1.10.0`, build each package. The artifact reports a version such as `1.10.1.dev3+g<hash>` (or similar PEP 440 dev-release form) that sorts strictly after `1.10.0` and is clearly not a release.

**Acceptance Scenarios**:

1. **Given** N commits past tag `infrahub-v1.10.0`, **When** a package is built, **Then** the version contains a development/local segment derived from commit distance and short hash.
2. **Given** any untagged commit, **When** a package is built, **Then** the version is PEP 440-compliant and sorts strictly after the most recent reachable release tag.

---

### User Story 5 - Runtime and Internal Tooling Read the Current Version (Priority: P2)

Runtime code paths and internal tooling that surface the package version (FastAPI `/info`, the `InfrahubInfo` GraphQL query, telemetry, worker labels, log output, etc.) continue to return the correct current version after the change. No human-facing surface that previously displayed the version regresses.

**Why this priority**: Backend runtime code already reads `__version__` via `importlib.metadata.version("infrahub-server")` in `backend/infrahub/__init__.py`, so this is mostly a verification story rather than a migration story — but it is the user-facing contract of the version surface and must be confirmed end-to-end, not assumed.

**Independent Test**: Build and install the package from a tagged commit. Hit `/api/info`, run the `InfrahubInfo` GraphQL query, inspect worker labels and log headers. Each one returns the same version that `python -c "import importlib.metadata; print(importlib.metadata.version('infrahub-server'))"` reports for the installed build.

**Acceptance Scenarios**:

1. **Given** the new build setup is installed, **When** any runtime surface reports a version (`/api/info`, GraphQL `InfrahubInfo`, worker label, log header), **Then** it matches the package's installed metadata version.
2. **Given** a Docker image built from a tagged commit, **When** the image's running server reports its version, **Then** the version matches the build's package metadata.

---

### User Story 6 - Release-Orchestration Tasks Continue to Work (Priority: P1)

The release pipeline that propagates a new version into downstream artifacts — Helm chart `appVersion`, `docker-compose.yml` image tags, the `infrahub-helm` repo — continues to run successfully without manual intervention after dynamic versioning lands. No release-time task or CI workflow fails or silently no-ops as a result of the static `version` field disappearing from `pyproject.toml`.

**Why this priority**: This is P1 because release-pipeline regression directly blocks shipping. Three release-orchestration tasks today read `[project].version` from `pyproject.toml` (`update_helm_chart`, `update_docker_compose`, `update_test_containers` in `tasks/release.py`); a CI workflow (`.github/workflows/update-compose-file-and-chart.yml`) triggers on changes to `pyproject.toml` and invokes these tasks; and another CI step (`.github/workflows/ci.yml:360-375`) cross-checks the two packages' versions via `uv version --short`. After this change, the static field is gone, `pyproject.toml` no longer changes on releases (so the path-filtered trigger never fires), the cross-check is tautological, and the behavior of `uv version --short` on a dynamically-versioned project is unverified. Each of these MUST be addressed, not assumed away.

**Independent Test**: Cut a release with the new dynamic-versioning configuration in place (in a staging branch / dry-run repo if necessary). Confirm: (a) the Helm chart `appVersion` bump produces the correct value, (b) the `docker-compose.yml` image tags update to the new release version, (c) no release-pipeline workflow is silently skipped, (d) no `uv version --short` invocation returns an empty or unexpected value.

**Acceptance Scenarios**:

1. **Given** a release tag `infrahub-v1.10.0` is pushed, **When** the post-release automation runs, **Then** `helm/charts/infrahub/Chart.yaml` `appVersion` is updated to `1.10.0` and `docker-compose.yml` image tags are updated to `1.10.0`.
2. **Given** the change has landed, **When** the unchanged `update_test_containers` task and its CI step would have run, **Then** they no longer exist (deleted as obsolete; the two packages share a version by construction).
3. **Given** any CI workflow that previously invoked `uv version --short`, **When** it runs against a dynamically-versioned checkout, **Then** the invocation either returns the resolved dynamic version cleanly or has been replaced with an equivalent `importlib.metadata.version(...)` call against the installed package.
4. **Given** a release is cut after the change, **When** the post-release "update docker-compose & helm chart" automation is expected to fire, **Then** it does fire (its trigger has been updated so that it does not depend on a `pyproject.toml` change that will no longer occur).
5. **Given** the current release line is `1.12.x` and `stable` is pinned to `infrahub:1.12.4` in `docker-compose.yml`, **When** a maintenance release `infrahub-v1.11.7` is pushed from a `release-1.11` branch, **Then** `docker-compose.yml` and the Helm chart `appVersion` on `stable` remain at `1.12.4` — they are NOT rewritten to `1.11.7`. The `infrahub-v1.11.7` release itself still publishes its own artifacts (wheel, image, release notes) as a normal release.

---

### Edge Cases

- A contributor opens a PR from a fork that has not fetched tags. CI must still build successfully (full-fetch in CI already covers this, but the fallback in US3 is the explicit safety net).
- A developer runs `uv build` locally on a fresh shallow clone (`git clone --depth 1`). Build must succeed via the fallback, not fail loudly, so the local "first build" experience does not regress.
- Two pre-release tags exist for the same version line (e.g., `infrahub-v1.10.0a0` and `infrahub-v1.10.0a1`). Build output must select the closest reachable tag and produce ordered, distinguishable versions.
- Someone creates a non-conforming tag (e.g., `v1.10.0` without the `infrahub-` prefix, or `infrahub-V1.10.0` with wrong case). The tag must be ignored by version resolution rather than producing a malformed version.
- The Enterprise build pipeline consumes this repo (mechanism unknown today, see Open Issue #3 in Jira). The spec must not block on resolving that, but must not actively break it; behavior in the Enterprise pipeline is a verification target during validation, not an in-scope deliverable here.
- A Docker build today consumes the version through some mechanism (Open Issue #4 in Jira). The change must not silently regress whatever version surfaces in container images and labels.
- A release is cut but `.github/workflows/update-compose-file-and-chart.yml` does not fire because its existing `paths: [pyproject.toml]` trigger never matches (the file no longer changes on releases). Downstream consumers of `docker-compose.yml` and the Helm chart `appVersion` would silently drift. FR-019 forces the trigger to be migrated; this edge case clarifies that the workflow change is mandatory, not optional.
- `uv version --short` is invoked in a CI workflow against a dynamically-versioned project (e.g., `.github/workflows/ci.yml:362` and `.github/workflows/update-compose-file-and-chart.yml:52-53,66`). `uv version` reads `[project].version`, which is absent on dynamically-versioned projects; the call is expected to fail. FR-018 mandates migration to `importlib.metadata`-based reads.
- A developer runs `uv sync` on commit A, then advances the working tree to commit B without re-syncing. `importlib.metadata.version("infrahub-server")` returns commit A's version indefinitely — the editable install does not refresh its metadata on every working-tree change. This is a quirk of editable installs (not a defect introduced by this change), but it changes the semantics of "what version am I running" in local development: today the static field in `pyproject.toml` is the developer-visible source of truth; after the change, the resolved version is fixed at sync time. Local-developer documentation (FR-012) MUST mention this.
- An sdist is extracted by a downstream consumer (Conda packager, air-gapped rebuild, third-party hardening pipeline) and rebuilt. The extracted sdist has no `.git/` inside it — the build-time resolver falls back to `1.10.0.dev0`. Standard mitigation is for the chosen resolver to also write a version-file (`tool.hatch.build.hooks.vcs.version-file` for hatch-vcs, `write_to` for setuptools-scm) so the resolved version is baked into a Python file included in the sdist. Whether this is required is open question OQ-3.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `infrahub-server`'s build configuration MUST resolve its version at build time from git tags matching `^infrahub-v(?P<version>[^+]+)$`. Mechanically: `[project].version` MUST be removed and `[project].dynamic` MUST declare `"version"`; the chosen build-time resolver (per FR-013) MUST be configured to read from the tag pattern above.
- **FR-002**: `infrahub-testcontainers`'s build configuration MUST resolve its version at build time using the same tag pattern. Because the package lives in `python_testcontainers/` (a subdirectory of the repo), the resolver MUST be configured to walk up to the repo root for git metadata (e.g., `tool.hatch.build.hooks.vcs.root = ".."` for hatch-vcs, or the equivalent setting on the chosen tool). The `[project].version` field MUST be removed and `[project].dynamic` MUST declare `"version"`, parallel to FR-001.
- **FR-003**: Both packages MUST be configured with a fallback version of `1.10.0.dev0` (canonical PEP 440 form) for use when no `infrahub-v*` tag is reachable. The fallback declaration MUST be accompanied by an inline comment stating that the fallback should be raised to `1.10.0` once the dynamic-versioning change has been validated end-to-end (so the fallback is not silently left at a pre-release value forever).
- **FR-004**: When an `infrahub-v*` tag is reachable, the build MUST prefer the tag-derived version over the fallback.
- **FR-005**: When the build is performed exactly on an `infrahub-v<X>` tag, the resulting artifact metadata MUST report exactly `<X>` (e.g., tag `infrahub-v1.10.0` → version `1.10.0`).
- **FR-006**: When the build is performed on an untagged commit reachable from an `infrahub-v*` tag, the artifact version MUST be PEP 440-compliant, MUST sort strictly after the reachable release tag, and MUST contain a development/local segment derived from commit distance and short hash so the artifact is identifiable as a development build.
- **FR-007**: Tags that do not match the `infrahub-v*` pattern MUST be ignored by version resolution; their presence MUST NOT cause builds to fail or pick a wrong version.
- **FR-008**: The change MUST remove the static `[project].version` field from both `pyproject.toml` files so that branches cannot diverge on a static version value. Both lockfiles (`uv.lock` at the repo root and `python_testcontainers/uv.lock`) MUST be regenerated as part of this change. **Verification gate (open question OQ-2):** uv's behavior when a workspace member is dynamically versioned is currently unverified — uv may write the *resolved* version into the workspace-member `[[package]]` entry of `uv.lock`, in which case every commit potentially rewrites the lockfile and US2's merge-conflict goal collapses for `uv.lock`. Before implementation, the implementer MUST verify that uv either writes a stable sentinel value or omits the version for dynamically-versioned workspace members. If it writes the resolved version, a mitigation (e.g., `.gitattributes` merge driver, lockfile-scrubbing pre-commit hook, or switching the workspace member to a non-workspace install) MUST be selected before merge.
- **FR-009**: `tasks/utils.py::get_version_from_pyproject()` MUST be removed (after its callers are reworked per FR-016 and FR-017). Any runtime/internal-tooling code paths that need the package version at runtime MUST read it via `importlib.metadata.version("infrahub-server")` (or `importlib.metadata.version("infrahub-testcontainers")` for that package). Backend code already follows this pattern via `backend/infrahub/__init__.py`, so the FR-009 work is mostly verification on the runtime side; the substantive code changes for release-time callers are in FR-016 and FR-017.
- **FR-010**: Dead code left behind by this change MUST be removed rather than retained:
  - `tasks/utils.py::project_ver()` has zero callers anywhere in the repo today (verified by grep at spec time) and MUST be deleted in the same change.
  - `tasks/utils.py::get_version_from_pyproject()` MUST be deleted once its callers are reworked (FR-016, FR-017).
  - The `tomllib` / `tomli` import block at the top of `tasks/utils.py` MUST be deleted once both functions above are gone.
  - Any tests targeting the deleted code MUST be deleted. Grep at spec time finds zero such tests, but the implementer MUST re-verify and delete any that have appeared in the meantime.
- **FR-011**: The Docker build path MUST be modified so that built container images report the same resolved version as a wheel built from the same commit. The current state is broken-by-design under dynamic versioning: `.dockerignore` includes `.git*` (line 9 at spec time), so the `.git/` directory is excluded from the Docker build context. The Dockerfile then runs `uv sync --frozen --no-dev` (e.g., `development/Dockerfile:121`) which would invoke the build-time version resolver with no git history available, silently producing the fallback version on every release image. The required fix is captured in FR-020. The audit MUST also cover `.github/workflows/update-compose-file-and-chart.yml`, which rewrites image tags in `docker-compose.yml` at release time (see FR-017 and FR-019).
- **FR-012**: Local-developer and release-engineering documentation MUST be updated to cover three new operational rules:
  - Local builds from a fresh clone require `git fetch --tags` to obtain a tag-derived version (otherwise the fallback applies).
  - An editable install (`uv sync`) pins the resolved version at sync time; advancing the working tree without re-syncing does NOT update `importlib.metadata.version("infrahub-server")`. Developers wanting an accurate version in logs/UI must re-sync after switching commits.
  - **Maintenance-branch hygiene**: a maintenance branch (e.g., `release-1.11` carrying `1.11.x` patches) MUST NEVER have a newer main-line release tag merged into its history. The version resolver picks the most recent `infrahub-v*` tag *reachable from HEAD*; if a `1.12.x`-tagged commit is reachable on a `release-1.11` branch via a merge, the next `1.11` release builds as a (broken) `1.12.x`-derived version. Patches across version lines MUST be cherry-picked, not merged.
- **FR-013**: At least one alternative to `hatch-vcs` (e.g., `setuptools-scm` used directly, `uv-dynamic-versioning`, or another comparable approach) MUST be evaluated against `hatch-vcs` before implementation begins, and the choice MUST be recorded with the reasoning (compatibility with the existing `hatchling` build backend, subdirectory-package support, fallback support, maintenance posture). `hatch-vcs` is the example used by the reference PR, not a hard requirement.
- **FR-014**: All existing CI workflows that build, publish, or otherwise consume a package version MUST continue to function. Every `actions/checkout` (or equivalent) step in `.github/workflows/` MUST be audited to confirm it fetches enough git history *and tags* for the resolver to find the most recent `infrahub-v*` tag — the default `actions/checkout@v6` configuration fetches only the triggering ref and omits tags unless `fetch-depth: 0` and `fetch-tags: true` are set. Any workflow that today omits one of these MUST be corrected as part of this change rather than relying on the fallback. Workflow-specific obligations are detailed in FR-018 and FR-019.
- **FR-015**: The Enterprise release pipeline's interaction with versioning (Jira Open Issue #3) MUST be assessed before merge, and any coordinated change required on the Enterprise side MUST be identified and tracked. (Assessment is in scope; resolution of any Enterprise-side change is allowed to be a follow-up.)
- **FR-016**: `tasks/release.py::update_test_containers` MUST be deleted. Its sole purpose is to keep `python_testcontainers/pyproject.toml`'s static `version` in lockstep with the root `pyproject.toml`'s static `version`. Once both packages resolve from the same `infrahub-v*` tag pattern (FR-001, FR-002), the two values are equal by construction and the task is meaningless. The corresponding step in `.github/workflows/update-compose-file-and-chart.yml` ("Update Versions in python_testcontainers/pyproject.toml", lines 61-62 at spec time) MUST be removed in the same change.
- **FR-017**: `tasks/release.py::update_helm_chart` and `tasks/release.py::update_docker_compose` MUST be reworked so the target version is supplied explicitly rather than read from `[project].version`. The chosen input source MUST be documented and MUST be consistent between the two tasks. Acceptable inputs: (a) an explicit `--version` argument passed by the caller, (b) the most recent `infrahub-v*` git tag reachable from `HEAD`, or (c) `importlib.metadata.version("infrahub-server")` against an installed package — the choice MUST be made deliberately based on where the task is invoked in the release flow, not chosen reflexively. Each task MUST continue to produce the same output it does today for the equivalent release. The `infrahub-enterprise` Helm chart's `infrahub` dependency version (updated by `update_helm_chart` at `tasks/release.py:181-186` at spec time) is explicitly in scope: the new input source MUST flow through to that update so the enterprise chart's `infrahub` dependency continues to track the main release.
- **FR-018**: The `.github/workflows/ci.yml` "Compare package versions" step (lines 360-375 at spec time) MUST be addressed: once both packages resolve from the same `infrahub-v*` tag pattern, the runtime cross-check is tautological. The step MUST either (a) be removed, or (b) be replaced with a static-configuration check that both `pyproject.toml` files declare the same tag prefix and the same dynamic-versioning plugin configuration. In addition, **all `uv version --short` invocations in CI workflows MUST be migrated** to read from installed package metadata (e.g., `python -c "import importlib.metadata; print(importlib.metadata.version('infrahub-server'))"`). `uv version` reads from `[project].version`, which is absent on dynamically-versioned projects per the `[project].dynamic` contract — the call is expected to fail or return an empty value, so this is a planned migration rather than a verify-and-decide. Call sites at spec time:
  - `.github/workflows/ci.yml:362`
  - `.github/workflows/release.yml:49,50,51,52` (four invocations in the main release/publish workflow)
  - `.github/workflows/update-compose-file-and-chart.yml:52,53,66`

  In `release.yml` specifically, the migration MUST preserve the surrounding *semantics* of the workflow: the prerelease/devrelease gating logic (computed today via `Version('$(uv version --short)').is_prerelease` / `.is_devrelease`) remains correct under dynamic versioning and MUST NOT be dropped during the read-mechanism migration.

  **Active publish-time safety checks (mandatory):** the existing tag-vs-pyproject equality check at `release.yml:60-63` becomes tautological after dynamic versioning (the resolved version comes *from* the tag), but the surrounding intent — "catch silent version drift before publishing" — MUST be preserved and broadened. `release.yml` MUST fail the publish job if either of the following holds:
  - **(a) Fallback equality check**: the resolved version equals the configured fallback (`1.10.0.dev0` at spec time). This catches silent resolver failures (tag not fetched, `.git/` not in the Docker build context, hatch-vcs misconfiguration) that would otherwise ship an artifact masquerading as a real release.
  - **(b) Tag-match check**: the resolved version does not exactly match the version segment of the pushed tag (i.e., for tag `infrahub-v1.10.0` the resolved version MUST be `1.10.0`). This catches the additional class of failure where the resolver reads a *different* tag than the one being released — for example, a maintenance-branch hygiene violation (FR-012) where a newer main-line tag is reachable and the resolver picks it instead of the intended maintenance tag.

  Both checks MUST be implemented as hard preconditions on the publish job (failing the workflow, not just warning), and MUST consume the new `importlib.metadata`-derived read path (not `uv version --short`). The two checks guard different failure modes and MUST both be present; they are defense in depth and the cost is a few lines of CI script.
- **FR-019**: `.github/workflows/update-compose-file-and-chart.yml` MUST be updated so that the release-time work it performs (docker-compose image-tag bump, Helm chart `appVersion` bump in the `infrahub-helm` repo) continues to run on actual releases. Today the workflow triggers on `push`/`pull_request` against `stable` filtered to `paths: [pyproject.toml]`; after dynamic versioning, `pyproject.toml` no longer changes on releases and that trigger never fires. The trigger MUST be migrated to fire on `infrahub-v*` tag pushes (or an equivalent post-release event). The workflow's three `uv version --short` invocations (lines 52, 53, 66 at spec time) MUST be migrated per FR-018. The "Update Versions in python_testcontainers/pyproject.toml" step is removed per FR-016. **Pre-release/dev-release gate preservation:** the workflow's existing conditional logic — today expressed as `if: steps.release.outputs.is_prerelease == 0 && steps.release.outputs.is_devrelease == 0` at `update-compose-file-and-chart.yml:56,59,77,85` at spec time — MUST be preserved through the migration. Pre-release tags (e.g., `infrahub-v1.10.0b3`) and dev-release tags MUST continue to publish their own artifacts but MUST NOT rewrite `docker-compose.yml` image tags or the Helm chart `appVersion` on `stable`. The gate MUST be re-implemented using a PEP 440-aware mechanism that consumes the new `importlib.metadata`-derived version read (e.g., `packaging.version.Version(resolved).is_prerelease` / `.is_devrelease`); the read-mechanism migration MUST NOT silently drop the conditional. **Cutover ordering constraint:** FR-019 MUST land in the same commit (or earlier commit on the same release-train branch) as FR-001/FR-002. Otherwise there is a window where the old trigger no longer fires (because `pyproject.toml` no longer changes on releases) and the new trigger is not yet wired — the first release in that window silently skips the docker-compose and Helm-chart updates.
- **FR-020**: The Docker version-resolution path MUST be modified so that container images built from a tagged commit report the same resolved version as a wheel built from that commit (rather than the fallback). The current `.dockerignore` excludes `.git*` (line 9 at spec time), making `.git/` unavailable to the build-time version resolver inside the container. The change MUST do all of the following:
  - Remove the `.git*` exclusion from `.dockerignore` (or scope it tighter — e.g., to specific large subtrees — but `.git/HEAD`, `.git/refs/`, `.git/packed-refs`, and `.git/objects/` MUST be reachable from the build context).
  - Ensure `.git/` does NOT end up in the final image layer. The broad `COPY . ./` (`development/Dockerfile:120` at spec time) MUST either be replaced with scoped `COPY` instructions that do not include `.git/`, or the `.git/` directory MUST be made available to the build-time resolver via a non-persisting mechanism such as a BuildKit bind mount (e.g., `RUN --mount=type=bind,source=.git,target=.git uv sync ...`).
  - The chosen mitigation MUST be documented and applied uniformly across all Dockerfiles in the repo that install the project (verified at spec time: `development/Dockerfile`, `.devcontainer/Dockerfile`, `utilities/benchmark/Dockerfile`).
  - All workflows that build Docker images (`publish-preview-dev-docker-image.yml`, `publish-dev-docker-image.yml`, `schedule-publish-docker-image.yml`, `ci-docker-image.yml`, and the docker image build in `release.yml`) MUST have their `actions/checkout` step configured to fetch tags (`fetch-depth: 0`, `fetch-tags: true`); covered transitively by FR-014 but called out explicitly here because FR-020 is the failure mode if any of them omits it.
  - The post-implementation final image size MUST NOT regress materially — image-size delta is an explicit acceptance gate.
  - The chosen mitigation is recorded as open question OQ-1; this FR commits to the outcome (Docker images get the real resolved version) without locking in a specific implementation path.
- **FR-021**: The `/cut-release` slash command (`dev/commands/cut-release.md`) MUST be rewritten. Its current premise is incompatible with dynamic versioning at every step:
  - Step 1 reads `version = "X.Y.Z"` from line 3 of `pyproject.toml`. After FR-008, that field does not exist.
  - Step 3 runs `uv version <new_version>` (root) and `uv version --directory python_testcontainers <new_version>` to bump the static fields. Both commands operate on `[project].version`, which is absent on a dynamically-versioned project; both are expected to fail.

  Leaving this command unmodified means the first invocation of `/cut-release` after this change lands will fail immediately on Step 1, breaking the team's primary release-cutting path. The rewritten command MUST:
  - Determine the new version by reading the most recent reachable `infrahub-v*` tag (e.g., `git describe --tags --match 'infrahub-v*' --abbrev=0`) and incrementing patch (default) or honoring an explicit `$ARGUMENTS` version.
  - Remove all `pyproject.toml`-bumping steps. The release-cut flow becomes: determine version → run `towncrier build --version <new>` → commit `CHANGELOG.md` and the removed fragment files → create the annotated tag `infrahub-v<new>` on that commit → push the tag (and the changelog commit).
  - Preserve the existing pre-flight checks (changelog fragment count, current-branch report, towncrier draft preview, user confirmation via `AskUserQuestion`) — only the bump step changes.
  - Explicitly document that no `pyproject.toml` edit happens at any point in the flow; that is the entire point of the change.

  This FR is mandatory and lands in the same change as FR-001/FR-008 — the team uses this command to ship.
- **FR-022**: Maintenance releases on older version lines (e.g., publishing `infrahub-v1.11.7` after `infrahub-v1.12.4` is already out) MUST NOT cause downstream artifacts on the current release line to regress. Two specific gaps in today's tasks/workflows MUST be closed:
  - `tasks/release.py::update_docker_compose` currently uses an inequality check (`if old_version != version` at `tasks/release.py:223` at spec time) and would rewrite `docker-compose.yml` image tags on `stable` *downward* if invoked with a maintenance-release version. It MUST be tightened to use a strict-greater comparison matching the existing pattern in `update_helm_chart` (`tasks/release.py:136`: `if not app_version.is_prerelease and app_version > old_app_version`). This change lands together with FR-017.
  - `.github/workflows/update-compose-file-and-chart.yml` (after FR-019's trigger migration to `infrahub-v*` tag pushes) MUST be scoped so that the docker-compose / Helm-chart bump only runs when the tag points at a commit that is an ancestor of `stable` (i.e., the tag is on the main-line history, not on a maintenance branch). Maintenance-branch tags MUST bypass the bump entirely. Relying solely on the in-task version comparison as the safety net is insufficient — defense in depth is required because the in-task check protects against the *version number* going backwards but not against, say, a maintenance release that happens to have a higher patch number than `stable` for some structural reason. The intent of the workflow is "propagate the current release-line's new version," and that intent should be encoded at the workflow scope, not just inside the task.

  Tag-only fields (release notes, GitHub Release creation, PyPI/Docker publish of the maintenance version itself) are unaffected — maintenance releases are still real releases and should still publish their own artifacts. FR-022 is solely about preventing the maintenance release from overwriting the *current* release line's pinned references in `stable`.
- **FR-023**: A coordinated cutover communication MUST accompany this change to handle in-flight feature branches that already contain `[project].version = "1.9.3"` (and any files this change modifies). Before FR-008 / FR-001 lands on `develop`, the implementer/release engineer MUST:
  - Enumerate all open PRs at cutover time.
  - Post a notice on each open PR explaining: (a) the cutover date, (b) the requirement to rebase after the change merges, (c) the steps to regenerate `uv.lock` post-rebase (`uv lock` from repo root and from `python_testcontainers/`), (d) what to do if the PR also touches files modified by this change (`tasks/utils.py`, `tasks/release.py`, `.dockerignore`, the Dockerfiles, workflow files).
  - Set a deadline by which in-flight branches SHOULD be rebased. PRs that miss the deadline are not blocked but are flagged for a follow-up rebase.

  Migration tooling (a helper invoke task or shell script) is NOT required for this cutover; the `pyproject.toml` conflict is mechanical and `uv lock` handles regeneration. Documentation alone (no proactive PR notices) is insufficient — authors would discover the conflict at merge time rather than in advance, producing a merge-time scramble during the release window when team attention is already stretched.

### Key Entities

- **Source-of-truth version**: The annotated git tag matching `infrahub-v<PEP440-version>`. This is the only place a released version is declared after the change.
- **Build-time version resolver**: The chosen tooling (e.g., `hatch-vcs` or an evaluated alternative) that reads git state at build time and stamps the produced artifact with the derived version.
- **Fallback version**: A configured PEP 440 string used when no tag is reachable. Initial value `1.10.0.dev0` (canonical form; sorts strictly below `1.10.0` and below any tag-derived `1.10.1.devN+g<hash>` development builds), with an inline comment stipulating the post-validation raise to `1.10.0`.
- **Installed metadata version**: The version recorded in the built package's distribution metadata, queryable via `importlib.metadata.version("infrahub-server")` or `importlib.metadata.version("infrahub-testcontainers")`. This is the new read path for runtime/internal tooling.
- **Release-target version**: The version a release-orchestration task (`update_helm_chart`, `update_docker_compose`) is asked to propagate into downstream artifacts. After the change this is no longer derivable from `[project].version` and must be supplied explicitly (CLI argument, reachable tag, or installed metadata — see FR-017).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Cutting a new Infrahub release no longer requires a dedicated version-bump PR. Measured by zero version-bump PRs in the next two release cycles after the change lands.
- **SC-002**: Merge conflicts between `stable`, `develop`, and any `release-*` branch caused by divergent static `version` fields or version-derived lockfile entries drop to zero in the merge events observed in the next two release cycles.
- **SC-003**: Builds performed in any supported environment (CI, local, Docker, Enterprise) produce a valid PEP 440 version 100% of the time, including in checkouts with no reachable `infrahub-v*` tag (where the fallback applies).
- **SC-004**: Every internal tool, task, and image-build step that previously surfaced a package version continues to surface a correct, non-empty, non-stale version after the change. Measured by a one-time audit pass before merge and by absence of "version is `0.0.0` / unknown / empty" incident reports in the first release cycle after merge.
- **SC-005**: Time spent per release on version-bump CI runs drops to zero (previously: one full CI pipeline per bump PR).
- **SC-006**: The first release after dynamic versioning lands completes its automated propagation steps (Helm chart `appVersion` bump in `infrahub-helm`, `docker-compose.yml` image-tag bump) without manual intervention. Measured by zero hotfix PRs or manual workflow re-runs for version-propagation reasons in the first release cycle after merge.

## Assumptions

- All current CI workflows already check out with full history and submodules (the reference PR claims this); this is treated as the baseline. Any workflow that does not is treated as a defect to fix as part of FR-014.
- The fallback value `1.10.0.dev0` is acceptable initial state because the next planned release is `1.10`; the inline comment captures the obligation to raise it after the change is validated end-to-end so the fallback never becomes a stale lie.
- `importlib.metadata` is available and acceptable as the new read path for internal tooling (Python 3.12, per the project's tech stack).
- Backend runtime code already reads `__version__` via `importlib.metadata.version("infrahub-server")` in `backend/infrahub/__init__.py`. All `from infrahub import __version__` consumers (FastAPI app version, `/api/info`, GraphQL `InfrahubInfo` query, telemetry, worker labels, log headers) ride that, so no runtime migration is required for those surfaces. US5 is therefore primarily a verification story; the substantive code work is in US6 / FR-009 / FR-016 / FR-017 / FR-018 / FR-019.
- Towncrier is configured with `package = "infrahub"` (`pyproject.toml:1165` at spec time), which causes it to read the version from `infrahub.__version__` rather than `[project].version` in `pyproject.toml`. Because the backend already exports `__version__` via installed metadata (preceding assumption), towncrier auto-resolves to the dynamic version with no migration required. Changelog rendering (`title_format = "## [Infrahub - v{version}]..."` at `pyproject.toml:1170`) continues to produce the correct `infrahub-v<version>` tag links.
- Both packages are uv workspace members (`pyproject.toml:77-80`: `infrahub-server = { workspace = true }`, `infrahub-testcontainers = { path = "python_testcontainers", editable = true }`). FR-008's verification gate concerns specifically how uv handles workspace members with dynamic versions in `uv.lock`.
- The bootstrap is consistent: the most recent tag is `infrahub-v1.9.3`, both `pyproject.toml` files currently declare `version = "1.9.3"`, and the next planned release is on the `1.10` line — so the fallback `1.10.0.dev0` is correctly positioned above all current releases and below the next planned release. No tag backfill is required.
- The existing `hatchling` build backend in both packages is the baseline; the alternatives evaluated in FR-013 are scoped to those that work cleanly with `hatchling` and with packages in subdirectories. If evaluation surfaces that a non-`hatchling` backend is materially better, switching backends is out of scope for this feature and is recorded as a follow-up.
- The Enterprise release pipeline is owned outside this repo. Coordination, not reimplementation, is in scope here (FR-015).
- No user-visible behavior of `infrahub-server` or `infrahub-testcontainers` changes as a result of this work; this is purely a build/release-pipeline change.

## Out of Scope

- Changing the release cadence, the tag naming convention beyond what is required to support dynamic versioning, or the contents of release notes.
- Replacing the `hatchling` build backend itself; only the version-resolution plugin/strategy is in scope.
- Resolving any breakage discovered in the Enterprise release pipeline (assessment is in scope per FR-015; remediation may be tracked as a follow-up).
- Backfilling tags or rewriting history to satisfy the new tag pattern; only forward-looking tags are required.
- Redesigning the post-release automation flow itself (e.g., whether the bot-driven `update-compose-file-and-chart.yml` is still the right pattern, or whether the Helm/docker-compose updates should move into a different system). FR-019 only ensures the existing flow continues to function; structural rework is a follow-up.

## Clarifications

### Session 2026-05-12

- Q: After FR-019 migrates the trigger and FR-018 migrates the read mechanism, should the existing `is_prerelease == 0 && is_devrelease == 0` gate in `.github/workflows/update-compose-file-and-chart.yml` (lines 49-53 at spec baseline) be preserved, so that pre-release tags do not rewrite `docker-compose.yml` / Helm `appVersion` on `stable`? → A: Preserve the gate — pre-release tags publish their own artifacts but do not rewrite `stable`'s pinned references.
- Q: How should the one-time cutover cost be handled for in-flight feature branches that already contain `[project].version = "1.9.3"` (and other files modified by this change) when FR-008 lands on `develop`? → A: Coordinated cutover — document the cutover date and post a notice on every open PR identifying the rebase requirement and the `uv.lock` regeneration steps, with a deadline. No migration tooling required.
- Q: Should the publish workflow include active assertions that prevent shipping an artifact with the fallback version, or should detection rely on the reactive SC-004 incident-report signal? → A: Required and broader — `release.yml` MUST fail the publish job if (a) the resolved version equals the fallback `1.10.0.dev0`, or (b) the resolved version does not exactly match the version segment of the pushed tag. Both checks land as hard requirements (MUST), not SHOULDs.

## Open Questions

These are decisions that MUST be resolved before implementation begins (or, where noted, before merge). Each is owned by the implementer to research and propose a recommendation; the spec captures the trade-off so the recommendation is informed rather than reflexive.

### OQ-1: Which Docker `.git/` exposure mitigation to adopt (FR-020)

The Docker build path needs git history available to the version resolver at build time but must not bloat the final image. The viable options:

| Option | Image grows? | Build-context grows? | Dockerfile diff | Mechanism agreement with wheel build |
|---|---|---|---|---|
| **A. BuildKit bind mount + scoped `COPY`s** (`--mount=type=bind,source=.git,target=.git` on the `uv sync` step; replace `COPY . ./` with explicit subdirectory `COPY`s) | No | Yes (transient `.git/` transfer) | ~5 lines | Same mechanism (resolver reads `.git/`) |
| **B. BuildKit bind mount + keep broad `COPY . ./`** | Yes (sizeable `.git/` in layer) | Yes | 1 line | Same mechanism |
| **C. Build-arg passthrough** (`docker build --build-arg INFRAHUB_VERSION=...`; resolver-specific pretend-version env var inside the container) | No | No | ~3 lines + CI plumbing | Different mechanism — two systems must agree |
| **D. Pre-built wheel** (build the wheel outside Docker in a builder stage with `.git/` available; `COPY --from=builder *.whl` into the runtime stage) | No (likely smaller) | No | Significant restructuring of all three Dockerfiles | Same mechanism (resolver runs once in builder) |

**Recommendation to investigate first:** Option A. It is the documented hatch-vcs / setuptools-scm Docker pattern, requires minimal Dockerfile changes, keeps the version-resolution mechanism uniform with wheel builds, and the build-context size cost is transient (not persisted). The scoped-`COPY` refactor is independently a Docker best practice (the current `COPY . ./` brings in test fixtures, docs sources, dev tooling, etc., none of which the runtime image needs).

Option D is the architecturally cleanest but the most invasive. Option C couples Docker builds to an external version source, doubling the number of places version logic can drift.

**Decision owner:** implementer. **Decision required before:** FR-020 implementation begins.

### OQ-2: How does uv handle `version` in `uv.lock` for dynamically-versioned workspace members? (FR-008)

This is a verification gate, not a free design choice. uv's documented behavior for `[[package]]` entries pointing at workspace members with `[project].dynamic = ["version"]` MUST be confirmed empirically before merge:

- **Outcome A (US2 holds):** uv writes a stable sentinel value (e.g., `version = "0.0.0"`), omits the field, or otherwise does not embed a per-commit-changing value in `uv.lock`. No mitigation required.
- **Outcome B (US2 partially collapses):** uv writes the *resolved* version. Every commit potentially rewrites the lockfile's workspace-member entry, reintroducing the lockfile-conflict problem US2 is meant to eliminate.

If outcome B, the implementer MUST select a mitigation from this menu (or propose another, justified):

- Add a `.gitattributes` merge driver that ignores the `version` field on workspace-member `[[package]]` entries during merges.
- Add a pre-commit / pre-push hook that scrubs the resolved version back to a sentinel before commit.
- Drop workspace-member declarations and install the local packages via path-only (non-workspace) install, accepting whatever fallout that has on the broader dev experience.

**Decision owner:** implementer. **Decision required before:** merge.

### OQ-3: Whether to write a version-file into the sdist

If the project's sdists are consumed by downstream rebuild pipelines (Conda packaging, air-gapped rebuilds, third-party hardening) that extract the sdist and call the build backend again, those rebuilds will fall back to `1.10.0.dev0` because the extracted sdist has no `.git/`. The fix is to configure the chosen resolver to also write a Python version-file (e.g., `tool.hatch.build.hooks.vcs.version-file = "backend/infrahub/_version.py"`) that is included in both wheel and sdist, baking the resolved version in.

Whether this is needed depends on whether anyone is actually rebuilding from sdists today. If no, this is unnecessary complexity and the sdist's `PKG-INFO` already carries the right version. If yes, the version-file is mandatory.

**Decision owner:** release engineering — needs to confirm sdist consumption patterns. **Decision required before:** the first dynamic-versioning release is published to PyPI. (Can be deferred slightly later than the other open questions if uncertain.)

### OQ-4: Final input source for `update_helm_chart` / `update_docker_compose` (FR-017)

FR-017 lists three acceptable inputs (explicit `--version` arg, most recent reachable `infrahub-v*` tag, installed metadata) and requires a deliberate choice. The trade-off:

- **`--version` arg from the workflow:** explicit, easy to dry-run with a fake version, but requires the workflow caller to know the version (CI computes it once from the tag and passes it).
- **Reachable git tag:** self-contained — task figures out the version from git state. Risk: in a workflow run triggered by a tag push, `HEAD` is the tag commit, so the answer is correct. In a workflow run triggered by something else, the answer may be wrong (e.g., if there are commits between the most recent tag and `HEAD`, the task would propagate the *previous* tag's version, not the one being released).
- **Installed metadata:** requires the package to be `uv sync`'d in the workflow before the task runs (it already is). Returns whatever was resolved at sync time, which is the same value the released artifact reports. Plays well with FR-019's tag-push trigger.

**Recommendation to investigate first:** installed metadata, paired with FR-019's tag-push trigger — the workflow runs on the tag, `uv sync` resolves to the tag-derived version, the release tasks read that version from installed metadata. One consistent mechanism end-to-end.

**Decision owner:** implementer. **Decision required before:** FR-017 implementation begins.
