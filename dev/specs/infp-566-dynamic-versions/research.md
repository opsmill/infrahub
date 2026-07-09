# Phase 0 Research: Dynamic Versioning from Git Tags

**Feature**: `specs/infp-566-dynamic-versions` · **Date**: 2026-06-25
**Plan baseline commit**: `5c08fd004` (current `develop` head at plan time) — supersedes the spec's `2406fae3c` baseline. All line citations below are re-verified against `5c08fd004`.

This document resolves the spec's open questions (OQ-1…OQ-4) and the FR-013 resolver
evaluation, and records the codebase-drift findings that change the plan relative to
the spec's "at spec time" citations. Empirical results were produced in an isolated
scratch repo using the repo's pinned `uv 0.11.6` and `hatch-vcs`.

---

## Drift findings (spec baseline → current `develop`)

The spec warned its citations would drift. They have. These shift the plan:

| Item | Spec ("at spec time") | Current (`5c08fd004`) | Impact |
|---|---|---|---|
| Most recent tag | `infrahub-v1.9.3` | **`infrahub-v1.10.0`** (also `infrahub-v1.10.0b0`) | Bootstrap assumption stale; fallback re-baselined (below) |
| Both `pyproject.toml` `version` | `1.9.3` | **`1.10.0`** | — |
| Fallback `1.10.0.dev0` | sorts above `1.9.3`, below next line | **sorts BELOW shipped `1.10.0`** | Re-baselined to `1.10.1.dev0` (decision below) |
| `.dockerignore` `.git*` | line 9 | **line 16** | — |
| `tasks/utils.py` `project_ver()` | present, 0 callers | **lines 49-52, still 0 callers** | Delete per FR-010 |
| `tasks/utils.py` `get_version_from_pyproject()` | present | **lines 111-114** | Delete per FR-009/FR-010 after callers reworked |
| `tasks/release.py` helm `>` check | `:136` | **`:141`** (`if not app_version.is_prerelease and app_version > old_app_version`) | Pattern to copy into `update_docker_compose` (FR-022) |
| `tasks/release.py` docker-compose `!=` check | `:223` | **`:228`** (`if old_version != version`) | Tighten to `>` (FR-022) |
| `ci.yml` "Compare package versions" | `:360-375` | **`:403-418`** | Remove/replace (FR-018) |
| `ci.yml` `uv version --short` | `:362` | **`:405,409`** | Migrate (FR-018) |
| `release.yml` `uv version --short` | `:49-52` (4×) | **`:49,50,51,52` (5 invocations; `:52` calls it twice)** | Migrate (FR-018) |
| `release.yml` tag-vs-pyproject check | `:60-63` | **`:60-64`** (`if: github.event.release.tag_name != format('infrahub-v{0}', …version)`) | Becomes tautological; broaden to fallback + tag-match guards (FR-018) |
| `update-compose-…yml` trigger | `paths: [pyproject.toml]` on `stable` | **confirmed `:8-18`** (push `stable` `paths:[pyproject.toml]` + closed PR) | Migrate to `infrahub-v*` tag push (FR-019) |
| `update-compose-…yml` prerelease gate | `:56,59,77,85` | **`:55-60,77,85,89`** (`is_prerelease==0 && is_devrelease==0`) | Preserve via PEP 440-aware read (FR-019) |
| `update-compose-…yml` testcontainers step | `:61-62` (no conditional) | **confirmed `:61-62`** | Remove (FR-016) |
| `/cut-release` location | `dev/commands/cut-release.md` | **`.agents/commands/cut-release.md`** (+ a `/cut-release` Skill) | FR-021 retargets here |
| `development/Dockerfile` `COPY . ./` / `uv sync` | `:120` / `:121` | **`:121` (`COPY . ./`) / `:122` (`uv sync --frozen --no-dev`)** | FR-020 target |
| Other Dockerfiles install project? | spec implied all 3 | **only `development/Dockerfile` runs `uv sync`**; `.devcontainer/Dockerfile` and `utilities/benchmark/Dockerfile` do NOT build/install the project | FR-020 scope narrows to 1 Dockerfile |
| `infrahub-testcontainers` in `[tool.uv.sources]` | "workspace = true" assumed | **`{ path = "python_testcontainers", editable = true }`** (`:83`); only `infrahub-server` is `workspace = true` (`:81`) | Both shapes verified safe for OQ-2 |

**New material finding — runtime read path already correct (US5).** `backend/infrahub/__init__.py:3`
is `__version__ = importlib.metadata.version("infrahub-server")`. Eleven backend modules
import `from infrahub import __version__` (workflows, events, trigger, telemetry, worker,
server, graphql internal query, git agent, async worker). `telemetry/utils.py:8` reads
`importlib.metadata.version("infrahub-enterprise")`. US5 is verification-only; **no runtime
code change is required.**

---

## FR-013 — Build-time version resolver choice

**Decision: `hatch-vcs`.**

**Rationale.** The build backend is `hatchling` in both packages and is out of scope to
change (spec Out-of-Scope + Assumptions). `hatch-vcs` is the hatchling-native VCS version
source (it wraps `setuptools-scm`), and it satisfies every FR mechanic empirically (see
"Empirical verification" below): custom tag pattern, exact-on-tag version, dev/local
segment past a tag, configurable fallback, subdirectory `root`, and a version-file written
into wheel **and** sdist. It is the resolver used by the reference PR (#8974), minimizing
divergence from a known-good baseline.

**Alternatives considered.**

| Option | Verdict | Reason |
|---|---|---|
| **`hatch-vcs`** | **Chosen** | Native hatchling plugin; setuptools-scm-backed (mature); supports `fallback-version`, `raw-options.root` for subdirectory, `git_describe_command` for tag filtering, and `version-file`. Reference-PR proven. |
| `setuptools-scm` used directly | Rejected | Requires the `setuptools` build backend or bespoke wiring; the project uses `hatchling`. `hatch-vcs` *is* the supported way to use setuptools-scm under hatchling. |
| `uv-dynamic-versioning` | Rejected (viable but riskier) | uv-native, hatchling-compatible, dunamai-based; good fallback support. But it is a newer/less-ubiquitous plugin, diverges from the reference PR, and offers no capability `hatch-vcs` lacks for this use case. No benefit to justify the divergence. |

**Cost:** one new **build-time** dependency (`hatch-vcs`, pulling `setuptools-scm`) added to
each package's `[build-system].requires`. This is the "Ask First: New dependencies" item
from AGENTS.md — it is the core mechanism of the feature and is the minimal, standard choice.

---

## OQ-2 — How does `uv lock` record dynamically-versioned members? **(RESOLVED EMPIRICALLY → Outcome A)**

**Result: uv writes NO `version` field for dynamically-versioned workspace/editable
members. US2 holds for `uv.lock`. No mitigation required.**

Reproduction (scratch workspace, `uv 0.11.6`): a root package (`workspace = true` analog)
and a subdirectory member (`path/editable` analog), both `dynamic = ["version"]` via
hatch-vcs, on a tagged commit. After `uv lock`, the `[[package]]` entries were:

```toml
[[package]]
name = "member-pkg"
source = { editable = "member" }

[[package]]
name = "root-pkg"
source = { editable = "." }
```

No `version = …` line on either. Both source shapes present in the real repo
(`infrahub-server = { workspace = true }`, `infrahub-testcontainers = { path, editable }`)
are covered. Per-commit lockfile churn does not occur, so US2's `uv.lock` merge-conflict
goal is met without a `.gitattributes` driver, scrub hook, or de-workspacing.

**Caveat / gate.** This is verified for the pinned `uv 0.11.6`. If uv is upgraded as part
of this change, re-run the reproduction before merge. Record the uv version alongside the
regenerated `uv.lock`.

---

## OQ-1 — Docker `.git/` exposure mitigation (FR-020)

**Decision: Option A — BuildKit bind mount + scoped `COPY`** , applied to the **one**
Dockerfile that installs the project.

**Scope correction.** The audit shows only `development/Dockerfile` runs `uv sync`
(`:122`, after `COPY . ./` at `:121`). `.devcontainer/Dockerfile` installs `invoke`/`uv`
but never `uv sync`s the project; `utilities/benchmark/Dockerfile` only copies an
entrypoint. **FR-020's "apply uniformly across all three Dockerfiles" reduces to one
Dockerfile** — note this in tasks; the other two need no change (re-grep at implementation
time in case a new `uv sync` appears).

**Mechanism.** On the `uv sync` step that installs the project, mount `.git` transiently so
the resolver can read it, and keep it out of the final layer:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=.git,target=.git \
    uv sync --frozen --no-dev
```

`.dockerignore` must stop excluding `.git` from the build context (it is at `:16`,
`.git*`). The narrowest change is to scope that to `.gitignore`/`.gitmodules`/`.gitattributes`
and the docs `.git` artifacts while letting `.git/` through — but the bind mount means
`.git/` never persists in a layer regardless. The current `COPY . ./` (`:121`) already
relies on `.dockerignore` to keep `.git/` out of the image; once `.gitignore`-style
patterns are preserved but `.git/` is allowed into the *context*, the bind-mount approach
keeps it out of the *image*. Replacing the broad `COPY . ./` with scoped copies is an
independent Docker-hygiene win (the current copy drags in tests, docs sources, dev tooling)
but is optional for correctness given the bind mount; treat it as a recommended sub-task,
not a blocker.

**Acceptance gate (FR-020):** final image size MUST NOT regress materially — measure before/after.

**Alternatives:** Option B (broad COPY, no scoping) bloats the image with `.git/`; Option C
(build-arg passthrough) couples Docker to an external version source (two systems to keep in
sync); Option D (pre-built wheel in a builder stage) is cleanest architecturally but the most
invasive. A is the documented hatch-vcs/setuptools-scm Docker pattern and the least risk.

---

## OQ-3 — Version-file in the sdist **(DECIDED: write it proactively)**

**Decision: configure `version-file` so the resolved version is baked into wheel AND sdist.**

User direction: write the version-file proactively (cheap insurance against downstream
sdist-rebuild consumers — Conda/air-gapped/hardening pipelines — which have no `.git/`).

**Verified behavior.** With `[tool.hatch.build.hooks.vcs] version-file = "<pkg>/_version.py"`,
the build writes a `_version.py` containing `__version__ = '1.10.1.dev1+g40b0e21'` and
**includes it in the sdist** (confirmed via `tar tzf …`). A rebuild from that sdist therefore
reports the baked version instead of the fallback. The generated file header explicitly says
"don't track in version control" → **add both version-files to `.gitignore`**:

- `backend/infrahub/_version.py`
- `python_testcontainers/infrahub_testcontainers/_version.py`

(Confirm the exact package import paths at implementation time; `infrahub-server` maps to the
`backend/infrahub` package, `infrahub-testcontainers` to `python_testcontainers/infrahub_testcontainers`.)

---

## OQ-4 — Input source for `update_helm_chart` / `update_docker_compose` (FR-017)

**Decision: installed metadata** — `importlib.metadata.version("infrahub-server")` — paired
with FR-019's `infrahub-v*` tag-push trigger.

**Rationale.** Under FR-019 the workflow runs on the tag push; it already `uv sync`s before
invoking the release tasks, so the installed metadata equals the tag-derived version the
released artifact reports. One consistent read path end-to-end, no caller needs to compute or
pass a version, and it composes with the publish guards (FR-018) that read the same path.
Reachable-git-tag was rejected because a non-tag-triggered run could resolve the *previous*
tag; explicit `--version` arg was rejected as redundant plumbing once metadata is reliable.

**Implementation note.** The two tasks currently call `get_version_from_pyproject()`
(`release.py:114,204`; also `:250` in `update_test_containers`, which is deleted per FR-016).
Replace with a small shared helper reading `importlib.metadata.version("infrahub-server")`.
Keep `packaging.version.Version` for the prerelease/comparison logic. `update_docker_compose`'s
`!=` (`:228`) becomes `>` mirroring `update_helm_chart` (`:141`) per FR-022.

---

## Fallback re-baseline (new decision — spec value is stale)

**Decision: `1.10.1.dev0`** (next-patch baseline), per user direction.

`infrahub-v1.10.0` has shipped, so the spec's `1.10.0.dev0` now sorts below a released
version. `1.10.1.dev0` sorts strictly above `1.10.0` and is the natural setuptools-scm
guess-next floor for the `1.10` line; real dev builds (`1.10.1.devN+g…`) sort above it.
Inline comment per FR-003: "raise to the next release once dynamic versioning is validated
end-to-end."

**FR-018(a) guard nuance (empirical).** The emitted version when a `.git/` exists but no
`infrahub-v*` tag matches is **not** the literal `1.10.1.dev0` — setuptools-scm appends a
local segment: `1.10.1.devN+g<hash>.d<date>`. The literal `1.10.1.dev0` appears only when
there is **no `.git/` at all** (sdist rebuild). Therefore FR-018(a)'s "resolved == fallback"
guard MUST compare the fallback **base** (e.g. fail if `Version(resolved).base_version`
matches the fallback base **and** it is a dev/local release), not a literal string equality.
FR-018(b) (resolved must equal the pushed tag's version segment) is the primary guard and is
unaffected.

---

## Empirical verification summary (hatch-vcs + `infrahub-v*` pattern, uv 0.11.6)

Config under test (root package):

```toml
[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"
fallback-version = "1.10.1.dev0"   # raise to next release after end-to-end validation

[tool.hatch.version.raw-options]
git_describe_command = ["git", "describe", "--tags", "--long", "--match", "infrahub-v*"]

[tool.hatch.build.hooks.vcs]
version-file = "backend/infrahub/_version.py"
```

| Scenario | Resolved | FR |
|---|---|---|
| Exactly on `infrahub-v1.10.0` | `1.10.0` | FR-005 ✅ |
| 1 commit past tag | `1.10.1.dev1+gda5b438` | FR-006 ✅ |
| Stray non-conforming tag `v9.9.9` present | `1.10.1.dev1+gda5b438` (ignored) | FR-007 ✅ |
| No matching tag, `.git/` present | `1.10.1.devN+g<hash>.d<date>` | US3 ✅ |
| No `.git/` (sdist rebuild) | `1.10.1.dev0` (literal fallback) | US3 ✅ |
| Subdirectory pkg, `raw-options.root = ".."` | parent repo's tag resolved | FR-002 ✅ |
| `uv lock` with dynamic members | no `version` recorded | FR-008/OQ-2 ✅ |

> **Follow-up (post-cutover): `--dirty` dropped from `git_describe_command`.** The findings above
> were captured with `--dirty`. The first release exposed the case deferred at T026: the Docker
> build resolves the version against a work tree that `.dockerignore` strips of tracked files, so
> `git describe --dirty` reported it dirty and setuptools-scm bumped every on-tag image to
> `{next}.devN+g<node>.d<date>`. Removing `--dirty` derives the version from committed state only.
> The `.d<date>` suffix in the scenarios above no longer appears; a dirty work tree no longer
> affects the resolved version.
| `version-file` in sdist | `_version.py` present in tarball | OQ-3 ✅ |

The default setuptools-scm `tag_regex` already strips the `infrahub-` prefix; `--match
infrahub-v*` in `git_describe_command` is what enforces FR-007. An explicit
`tag_regex = "^infrahub-v(?P<version>[^+]+)$"` may be added to mirror FR-001 literally, but
is not required for correct resolution.

---

## FR-015 — Enterprise pipeline (assessment, not resolution)

Per spec, assessment is in scope; remediation may be a follow-up. The Enterprise pipeline is
owned outside this repo. Two repo-side hooks the Enterprise side likely depends on:
(1) `infrahub-enterprise` Helm chart `infrahub` dependency version, updated by
`update_helm_chart` (`release.py:184-191`) — FR-017's installed-metadata input must flow
through to it; (2) `importlib.metadata.version("infrahub-enterprise")` read in
`telemetry/utils.py:8` — unaffected by this change. **Action:** open a tracked
coordination item with Enterprise-pipeline owners covering tag-fetch posture and any
`uv version` usage on their side; capture findings before merge, allow remediation to follow.

---

## FR-023 — Cutover communication (process, not code)

Before FR-008/FR-001 land on `develop`: enumerate open PRs, post a notice on each (cutover
date; rebase requirement; `uv lock` regeneration from repo root and `python_testcontainers/`;
guidance if the PR also touches `tasks/utils.py`, `tasks/release.py`, `.dockerignore`,
`development/Dockerfile`, or the workflow files); set a non-blocking rebase deadline. No
migration tooling required — the `pyproject.toml` conflict is mechanical.
