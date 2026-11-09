# Phase 1 Data Model: Dynamic Versioning from Git Tags

This feature has no database entities. The "data model" is the set of **version values**
and how they flow between sources, build-time resolution, installed metadata, and
release-orchestration consumers. Each entity below lists its representation, source of
truth, validation rules, and the transitions that move a version through the system.

---

## Entity: Source-of-truth tag

- **Representation**: an annotated git tag matching `^infrahub-v(?P<version>[^+]+)$`
  (e.g. `infrahub-v1.10.0`, `infrahub-v1.10.0b3`).
- **Source of truth**: git. This is the *only* place a released version is declared after
  the change (no static `[project].version`).
- **Validation**:
  - The version segment MUST be PEP 440-compliant.
  - Tags not matching the pattern (`v1.10.0`, `infrahub-V1.10.0`) are ignored by resolution
    (enforced by `git describe --match "infrahub-v*"`).
  - Maintenance-branch hygiene: a tag from a newer main line MUST NOT be reachable from an
    older release branch's HEAD (else resolution picks the wrong line).
- **Lifecycle**: created by `/cut-release` (FR-021) → pushed → triggers release + propagation
  workflows (FR-019).

## Entity: Resolved build-time version

- **Representation**: PEP 440 string stamped into package metadata at build time.
- **Source**: `hatch-vcs` reading git state (`git describe --tags --long --match infrahub-v*`).
- **Derivation rules** (verified empirically):
  - Exactly on a tag → exact version segment (`infrahub-v1.10.0` → `1.10.0`).
  - N commits past tag → `<next-patch>.devN+g<shorthash>` (sorts strictly after the tag).
  - No matching tag but `.git/` present → `<fallback-base>.devN+g<hash>.d<date>`.
  - No `.git/` (extracted sdist) → the baked version-file value, else the literal fallback.
- **Validation**: always PEP 440-compliant; always non-empty (fallback guarantees this).
- **Applies to both packages** (`infrahub-server`, `infrahub-testcontainers`) from the same
  tag → equal by construction.

## Entity: Fallback version

- **Representation**: configured PEP 440 string. **Value: `1.10.1.dev0`** (re-baselined from
  the spec's stale `1.10.0.dev0`; see research.md).
- **Source**: `[tool.hatch.version].fallback-version` in each `pyproject.toml`.
- **Validation / invariants**:
  - MUST be PEP 440-compliant and sort strictly above the latest shipped release (`1.10.0`).
  - MUST carry an inline comment: "raise to the next release after end-to-end validation."
  - MUST be identical in both packages.
- **Used when**: no `infrahub-v*` tag is reachable. MUST never ship as a real release —
  guarded at publish time (see Publish guard contract).

## Entity: Version-file (`_version.py`)

- **Representation**: generated Python module (`__version__ = '<resolved>'`).
- **Source**: `[tool.hatch.build.hooks.vcs].version-file`. Written at build time, included in
  wheel and sdist.
- **Paths**: `backend/infrahub/_version.py`, `python_testcontainers/infrahub_testcontainers/_version.py`.
- **Validation**: MUST be git-ignored (header says "don't track in version control"); MUST
  appear in the sdist so downstream rebuilds (no `.git/`) get the baked version.

## Entity: Installed metadata version

- **Representation**: `importlib.metadata.version("infrahub-server")` /
  `…("infrahub-testcontainers")`.
- **Source**: the built/installed distribution's metadata; fixed at `uv sync`/install time.
- **Consumers (runtime, US5 — no change needed)**: `backend/infrahub/__init__.py:3` →
  `from infrahub import __version__` in workflows, events, trigger, telemetry, worker, server,
  graphql internal query, git agent, async worker; FastAPI app version / `/api/info`;
  GraphQL `InfrahubInfo`.
- **New consumers (release-time, FR-016/017/018)**: reworked `update_helm_chart`,
  `update_docker_compose`; CI version reads (replacing `uv version --short`).
- **Quirk (FR-012 doc)**: editable installs pin the value at sync time — advancing the
  working tree without re-syncing does not refresh it.

## Entity: Release-target version (propagated artifacts)

- **Representation**: the version written into downstream artifacts:
  - `docker-compose.yml` image tags (services `infrahub-server`, `task-worker`, `task-manager`).
  - `helm/charts/infrahub/Chart.yaml` `appVersion` (+ `version` bump, + `values.yaml`
    `prefectTag`).
  - `helm/charts/infrahub-enterprise/Chart.yaml` `infrahub` dependency version.
- **Source after change**: installed metadata (FR-017/OQ-4), not `[project].version`.
- **Validation / state transitions**:
  - Update only when new version `>` existing (strict-greater) — `update_helm_chart` already
    does this (`release.py:141`); `update_docker_compose` MUST be tightened from `!=` (`:228`)
    to `>` (FR-022) so a maintenance release never rewrites `stable` downward.
  - Pre-release / dev-release tags MUST NOT rewrite `stable`'s pinned references (gate
    preserved via `Version(resolved).is_prerelease`/`.is_devrelease`, FR-019).
  - Maintenance-branch tags (not an ancestor of `stable`) MUST bypass propagation entirely
    (workflow-scope guard, FR-022).
