---
description: Run all locally-executable CI checks (format, lint, unit tests) for the areas you changed
argument-hint: "[--fast] [--all]"
allowed-tools:
  - Bash(git fetch:*)
  - Bash(git merge-base:*)
  - Bash(git diff:*)
  - Bash(git ls-files:*)
  - Bash(git rev-parse:*)
  - Bash(uv run invoke:*)
  - Bash(uv run ruff check:*)
  - Bash(uv run ruff format:*)
  - Bash(uv run ty check:*)
  - Bash(uv run yamllint:*)
  - Bash(uv run --directory python_testcontainers pytest:*)
  - Bash(uv lock --check:*)
  - Bash(uv lock:*)
  - Bash(pnpm --dir frontend/app:*)
  - Bash(pnpm --dir frontend/packages/graph:*)
  - Bash(npx markdownlint*:*)
---

# Pre-CI

Run the locally-executable CI checks that apply to what you changed. **Every check below mirrors
a job in `.github/workflows/ci.yml` — keep them in parity.**

**Every command runs from the repository root and must leave the working directory unchanged.**
The parallel phases share a single shell, so a `cd` in one command changes where its siblings run
and the `invoke` tasks then fail on relative paths. Use `pnpm --dir` for the frontend checks —
never `cd frontend/app && ...`.

**Options:**

- `--fast` — Formatting and fast lint only (~20s). Skips mypy, Betterer, docs lint,
  generated-file and doc validation, schema validation, and all unit tests.
- `--all` — Skip detection and run every phase regardless of what changed.

---

## Phase 0 — Detect what changed

Identify which areas below this branch touched — committed, staged, and untracked — relative to
its base: `stable`, `develop`, a `release-*` branch, whichever long-lived branch it forked from.
`git fetch` the candidates first so the base is not stale, then collect paths from three places:
`git diff --name-only --no-renames <merge-base>...HEAD` for committed work, the same command
against `HEAD` for staged and unstaged work, and `git ls-files --others --exclude-standard` for
untracked files. Keep `--no-renames`: without it a rename reports only the new path, so the area
that *lost* the file is never flagged.

Run only the phases for the areas that changed, plus those marked always-run. **When unsure about
the base, or whether a path counts, include it.** Over-running is cheap; a missed area is a red PR.

Classify the paths using the globs from `.github/file-filters.yml`, so local gating matches the
`files-changed` outputs CI branches on.

| Area | Paths | Enables |
|---|---|---|
| **frontend** | `frontend/app/**`, `frontend/packages/**`, `frontend/package.json`, `frontend/pnpm-workspace.yaml`, `frontend/pnpm-lock.yaml`, `schema/openapi.json`, `frontend/app/src/shared/api/rest/types.generated.ts`, `development/**`, `tasks/**`, `.github/workflows/ci.yml`, `.github/file-filters.yml` | Phases 1A, 3B |
| **backend** | `backend/**`, `python_sdk`, `development/**`, `tasks/**`, `**/pyproject.toml`, `**/uv.lock`, `.github/workflows/ci.yml`, `.github/file-filters.yml` | Phases 1B, 2B, 4B, 4C.2, 4D, 5.1 |
| **python** | any other `**/*.py` — `models/`, `utilities/`, `python_testcontainers/`, `tests/`, root scripts | Phases 1B, 2B, 4C.2 |
| **testcontainers** | `python_testcontainers/**`, `.github/workflows/*.yml` (any workflow, not just `ci.yml`) | Phase 5.2 |
| **docs** | `docs/**`, `**/*.{md,mdx}`, `.vale/**`, `.vale.ini`, `package.json`, `package-lock.json`, `development/**`, `tasks/**`, `python_sdk` | Phases 1C, 4C |
| **schema** | `schema/**` | Phase 4D |
| **yaml** | `**/*.{yml,yaml}`, `**/pyproject.toml`, `**/uv.lock` | Phase 2C |

Three frontend validation jobs gate on their own narrow filters rather than the whole frontend
area — check these paths separately:

| Trigger paths | Enables |
|---|---|
| `schema/openapi.json`, `frontend/app/src/shared/api/rest/types.generated.ts` | Phase 3C |
| `schema/schema.graphql`, `frontend/app/src/shared/api/graphql/generated/**` | Phase 3D |
| `schema/error-catalogue.json`, `frontend/app/src/shared/api/errors/catalogue.generated.ts`, `frontend/app/scripts/generate-error-bindings.mjs` | Phase 3E |

**State the detected areas before running anything**, e.g.
`Detected changes: frontend, docs. Skipping backend phases.`

Sub-step letters are stable per area — **A** frontend, **B** backend or python, **C** docs (yaml
in Phase 2), **D** schema — so a phase omits letters where an area has nothing to do. Phase 3 is
entirely frontend: `3A`–`3E` enumerate its individual CI jobs.

> **Phase 3A always runs, even with no frontend changes.** The `frontend-lint` job has **no path
> filter** — a backend-only change still fails CI if frontend lint is broken on your branch. Only
> the frontend *tests* (Phase 3B) are path-gated.

---

## Phase 1 — Auto-fix formatting (sequential)

These modify files and must complete before any lint check.

**1A. Frontend** — *if frontend changed*

```bash
pnpm --dir frontend/app run biome:fix
```

**1B. Python** — *if backend or python changed*

```bash
uv run invoke format
```

**1C. Documentation** — *if docs changed*

```bash
uv run invoke docs.format
```

---

## Phase 2 — Fast checks

**Send all applicable commands in a SINGLE message as parallel Bash calls.**

**2B. Python** — *if backend or python changed*

1. `uv run invoke main.lint`
2. `uv run ruff check . --exclude python_sdk`
3. `uv run ruff format --check --diff --exclude python_sdk .`
4. `uv run ty check .`
5. `uv lock --check` — root project (job `infrahub-uv-check`). On failure run `uv lock` and
   commit the updated lockfile.
6. `uv lock --check --directory python_testcontainers` — same for the separate
   `python_testcontainers` project (job `infrahub-testcontainers-uv-check`).

Steps 2–4 are CI's `python-lint` job verbatim, and repo-wide — the `invoke` tasks are not.

**2C. YAML** — *if yaml changed*

1. `uv run yamllint -s .` — CI's `yaml-lint` job. Call it directly, not via
   `uv run invoke lint`, which bundles unrelated steps.

---

> **If `--fast` was specified, stop here** and report results, marking slow checks as "skipped".

---

## Phase 3 — Frontend gate (CI parity)

The **complete** set of frontend checks CI runs. If dependencies are stale, first run
`pnpm --dir frontend/app install --frozen-lockfile` (CI always does).

**3A. Lint trio — ALWAYS run, regardless of detected areas** (job `frontend-lint`). Send as
parallel Bash calls:

1. `pnpm --dir frontend/app exec biome ci .` — `biome ci`, **not** `biome check --write`: only
   the `ci` variant is check-only.
2. `pnpm --dir frontend/app run knip` — unused exports, files, and dependencies.
3. `pnpm --dir frontend/app exec betterer ci` — `betterer ci`, **not** bare `betterer`, which
   rewrites the snapshot instead of failing.

**3B. Unit tests — if frontend changed** (job `frontend-tests`). Sequential:

1. `pnpm --dir frontend/app exec playwright install chromium` — the suite runs in browser mode.
   One-off per machine; skip if already installed.
2. `pnpm --dir frontend/app run test:coverage` — plain `pnpm test` skips coverage.
3. `pnpm --dir frontend/packages/graph run test` — the `@infrahub/graph` suite, a second step of
   the same job living outside `frontend/app`.

**3C. OpenAPI types** — *if the OpenAPI trigger paths changed* (job
`frontend-validate-openapi-types`). On a non-empty diff, stage and commit the regenerated file:

```bash
pnpm --dir frontend/app run codegen:openapi && git diff --exit-code frontend/app/src/shared/api/rest/types.generated.ts
```

**3D. GraphQL types** — *if the GraphQL trigger paths changed* (job
`frontend-validate-graphql-types`). On a non-empty diff, commit both generated files:

```bash
pnpm --dir frontend/app run codegen:graphql && git diff --exit-code frontend/app/src/shared/api/graphql/generated/graphql-env.d.ts frontend/app/src/shared/api/graphql/generated/graphql-cache.d.ts
```

**3E. Error catalogue bindings** — *if the error-catalogue trigger paths changed* (job
`frontend-validate-error-catalogue`). On failure, run
`pnpm --dir frontend/app run generate:error-bindings` and commit the result:

```bash
pnpm --dir frontend/app run check:error-bindings
```

---

## Phase 4 — Slow backend and docs checks

**Send all applicable commands in a SINGLE message as parallel Bash calls.**

**4B. Backend** — *if backend changed*

1. `uv run invoke backend.lint` — call this task directly, not `uv run invoke lint`, which
   bundles `main.lint`, `backend.lint` and `yamllint`. **mypy is what this phase adds** over
   Phase 2.
2. `uv run invoke backend.validate-generated` — on failure run `uv run invoke backend.generate`
   and report the regenerated files.

**4C. Docs** — *if docs changed; step 2 also if any Python changed*

1. `uv run invoke docs.lint` — markdownlint + vale, mirroring `markdown-lint` and
   `validate-documentation-style`. Pre-existing errors in `docs/docs/` may exist; only flag those
   in changed files. Does **not** cover the `documentation` job, which runs
   `uv run invoke docs.build` — run that manually if you touched the Docusaurus config.
2. `uv run invoke docs.validate` — reference docs generated from Python source (CLI, schema,
   events, repository config, config). On failure the correct files are already on disk; stage
   and commit them.

**4D. Schema** — *if backend or schema changed*

1. `uv run invoke schema.validate-graphqlschema` — regenerates, then checks for uncommitted
   diffs. On failure the correct file is already on disk; stage and commit it.
2. `uv run invoke schema.validate-jsonschema` — same, for `schema/openapi.json`.

---

## Phase 5 — Slow unit tests

Run after all lint and validation checks pass.

**5.1** — *if backend changed* (job `backend-tests-unit`):

```bash
uv run invoke backend.test-unit
```

**5.2** — *if testcontainers changed* (job `backend-testcontainers-unit`):

```bash
uv run --directory python_testcontainers pytest --rootdir=. -c pyproject.toml -vs tests
```

CI runs this as a Python 3.10–3.14 matrix; one interpreter is enough locally.

---

## After all checks

Summarize in a table. Include **every** row; mark rows as `skipped (no <area> changes)` or
`skipped (--fast)` rather than omitting them.

| Check | CI job | Status |
|-------|--------|--------|
| Frontend format/lint (`biome ci`) | frontend-lint | ... |
| Frontend unused exports (`knip`) | frontend-lint | ... |
| Frontend TS regressions (`betterer ci`) | frontend-lint | ... |
| Frontend unit tests (`test:coverage`) | frontend-tests | ... |
| `@infrahub/graph` unit tests | frontend-tests | ... |
| OpenAPI types | frontend-validate-openapi-types | ... |
| Frontend GraphQL types | frontend-validate-graphql-types | ... |
| Error catalogue bindings | frontend-validate-error-catalogue | ... |
| Python format (`ruff format --check`) | python-lint | ... |
| Main Python lint | python-lint | ... |
| Ruff (CI parity) | python-lint | ... |
| Lockfiles (root + testcontainers) | infrahub-uv-check, infrahub-testcontainers-uv-check | ... |
| YAML lint (`yamllint -s .`) | yaml-lint | ... |
| Type check (`ty check .`) | python-lint | ... |
| Backend lint (mypy) | backend-tests-integration, backend-tests-functional | ... |
| Generated files | backend-validate-generated | ... |
| GraphQL schema validation | graphql-schema | ... |
| JSON schema validation | json-schema | ... |
| Docs lint (markdownlint + vale) | markdown-lint, validate-documentation-style | ... |
| Generated docs validation | validate-generated-documentation | ... |
| Backend unit tests | backend-tests-unit | ... |
| Testcontainers unit tests | backend-testcontainers-unit | ... |

Then state one of:

- **All applicable checks passed — safe to push.** Name the areas that were skipped and why.
- **Failed.** List each failure with the exact command and suggested fix. Do not describe the
  branch as ready to push.
