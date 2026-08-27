---
description: Run all locally-executable CI checks (format, lint, unit tests) for the areas you changed
argument-hint: "[--fast] [--all]"
allowed-tools:
  - Bash(git merge-base:*)
  - Bash(git diff:*)
  - Bash(git ls-files:*)
  - Bash(git rev-parse:*)
  - Bash(sort:*)
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

Run the locally-executable CI checks that apply to what you changed, so a push does not fail
remotely. **Every check below mirrors a job in `.github/workflows/ci.yml` — keep them in
parity.**

**Every command runs from the repository root and must leave the working directory unchanged.**
The parallel phases below share a single shell, so a `cd` in one command silently changes where
its siblings run, and the `invoke` tasks then fail on relative paths such as
`schema/schema.graphql`. The frontend checks use `pnpm --dir` for that reason - do not rewrite
them as `cd frontend/app && ...`.

**Options:**

- `--fast` — Formatting and fast lint only (~20s). Skips backend lint (ty/mypy), Betterer, docs
  lint, generated-file and doc validation, schema validation, and all unit tests.
- `--all` — Skip detection and run every phase regardless of what changed.

---

## Phase 0 — Detect what changed

Run this first. Everything after it is conditional on the result.

```bash
BASE_REF=origin/stable
if git rev-parse --verify --quiet origin/develop >/dev/null 2>&1; then
  git merge-base --is-ancestor "$(git merge-base HEAD origin/stable)" \
    "$(git merge-base HEAD origin/develop)" && BASE_REF=origin/develop
fi
MERGE_BASE=$(git merge-base HEAD "$BASE_REF")
{ git diff --name-only --no-renames "$MERGE_BASE"...HEAD
  git diff --name-only --no-renames HEAD
  git ls-files --others --exclude-standard
} | sort -u
```

Both `develop` and `stable` exist, and a branch may be cut from either, so pick the candidate
whose merge base sits **closer to HEAD** — that is the one this branch actually forked from.
Preferring `develop` unconditionally would diff a `stable`-based branch against a merge base tens
of commits back and report every area as changed.

The list covers **both committed and uncommitted** work — CI sees the former, you are about to
push the latter, so both must pass. `--no-renames` matters: with rename detection on, a moved
file reports only its new path, so the area that lost the file is never flagged. Every command
here is in `allowed-tools`; keep it that way, and do not reach for `git status --porcelain`
parsing, whose `R  old -> new` form collapses into one bogus path.

Classify the paths using the same globs as `.github/file-filters.yml`. Each area below is that
file's `<area>_all` list, so local gating matches the `files-changed` outputs CI branches on:

| Area | Paths | Enables |
|---|---|---|
| **frontend** | `frontend/app/**`, `frontend/packages/**`, `frontend/package.json`, `frontend/pnpm-workspace.yaml`, `frontend/pnpm-lock.yaml`, `schema/openapi.json`, `frontend/app/src/shared/api/rest/types.generated.ts`, `development/**`, `tasks/**`, `.github/workflows/ci.yml`, `.github/file-filters.yml` | Phases 1A, 3B |
| **backend** | `backend/**`, `python_sdk`, `development/**`, `tasks/**`, `**/pyproject.toml`, `**/uv.lock`, `.github/workflows/ci.yml`, `.github/file-filters.yml` | Phases 1B, 2B, 4B, 4D, 5 |
| **python** | any other `**/*.py` — `models/`, `utilities/`, `python_testcontainers/`, `tests/`, root scripts | Phases 1B, 2B |
| **testcontainers** | `python_testcontainers/**`, `.github/workflows/*.yml` (any workflow, not just `ci.yml`) | Phase 5.2 |
| **docs** | `docs/**`, `**/*.{md,mdx}`, `.vale/**`, `.vale.ini`, `package.json`, `package-lock.json`, `development/**`, `tasks/**`, `python_sdk` | Phases 1C, 4C |
| **yaml** | `**/*.{yml,yaml}`, `**/pyproject.toml`, `**/uv.lock` | Phase 2C |

`python` is deliberately narrower than `backend`. The `python-lint` job fires on `backend ||
python`, but `backend-tests-unit`, `graphql-schema` and `json-schema` gate on `backend` alone —
so a change to `models/` or a root script must run the lint phases and **not** the slow ones.

Three frontend validation jobs are gated on their own narrow filters rather than the whole
frontend area — check these paths separately:

| Trigger paths | Enables |
|---|---|
| `schema/openapi.json`, `frontend/app/src/shared/api/rest/types.generated.ts` | Phase 3C |
| `schema/schema.graphql`, `frontend/app/src/shared/api/graphql/generated/**` | Phase 3D |
| `schema/error-catalogue.json`, `frontend/app/src/shared/api/errors/catalogue.generated.ts`, `frontend/app/scripts/generate-error-bindings.mjs` | Phase 3E |

If `--all` was passed, or if you cannot determine the base ref, treat every area as changed.

**State the detected areas before running anything**, e.g.
`Detected changes: frontend, docs. Skipping backend phases.`

In Phases 1, 2 and 4 the sub-step letter encodes the area — **A** = frontend, **B** = backend or
python, **C** = docs (yaml in Phase 2), **D** = schema — so a phase skips letters where an area
has nothing to do at that stage. Phase 2 has no `2A` because the frontend has no fast check of
its own. Phase 3 is the exception: it is entirely frontend, so `3A`–`3E` enumerate its individual
CI jobs.

> **Phase 3A always runs, even with no frontend changes.** The `frontend-lint` job in
> `ci.yml` has **no path filter** — it runs on every PR. A backend-only change still fails CI if
> frontend lint is broken on your branch. Only the frontend *tests* (Phase 3B) are path-gated.

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

**Send all applicable commands in a SINGLE message as parallel Bash calls.** Do not run them one
at a time.

**2B. Python** — *if backend or python changed*

1. `uv run invoke main.lint` — report any ruff issues.
2. `uv run ruff check . --exclude python_sdk` — the exact command CI's `python-lint` job runs.
   Not redundant with `main.lint`: that task lints only `tasks`, `models`, `utilities`, and
   `python_testcontainers`, and `backend.lint` only `backend`, so a violation anywhere else
   (`development/`, root-level scripts, `tests/`) passes locally and fails in CI. Only the
   whole-repo check proves CI will pass.
3. `uv run ruff format --check --diff --exclude python_sdk .` — the `python-lint` job's format
   step. Phase 1B does **not** make this redundant: `invoke format` only reformats `tasks`,
   `models`, `utilities`, `python_testcontainers` and `backend`, so an unformatted file under
   `development/`, `tests/` or the repo root survives it and fails CI. Same coverage gap as
   step 2, one step later in the job.
4. `uv run ty check .` — the job's third step, whole-repo like CI. **Easy to miss**: `ty` is
   otherwise only reachable through Phase 4B `backend.lint`, which the `python` area does not
   enable, so a `models/` or root-script change would clear pre-ci and still fail CI's ty step.
5. `uv lock --check` — ensures `uv.lock` matches `pyproject.toml`. If it fails, run `uv lock` and
   commit the updated lockfile.

**2C. YAML** — *if yaml changed*

1. `uv run yamllint -s .` — the exact command CI's `yaml-lint` job runs. **Easy to miss**: that
   job fires on any `**/*.{yml,yaml}` change, so a workflow, compose file or schema YAML edit
   with no Python in it still has a check to pass. Run the command directly rather than
   `uv run invoke lint`, which bundles unrelated steps; `.yamllint.yml` already ignores `.venv`,
   `node_modules` and the vendored submodules.

---

> **If `--fast` was specified, stop here** and report results, marking slow checks as "skipped".

---

## Phase 3 — Frontend gate (CI parity)

This is the **complete** set of frontend checks CI runs. Do not run a subset — a partial pass
here is what lets `frontend-lint` and `frontend-tests` fail on the PR.

All commands run from the repository root via `pnpm --dir`, per the note at the top of this
file. If dependencies are stale, first run `pnpm --dir frontend/app install --frozen-lockfile`
(CI always does).

**3A. Lint trio — ALWAYS run, regardless of detected areas** (mirrors job `frontend-lint`).
Send as parallel Bash calls:

1. `pnpm --dir frontend/app exec biome ci .` — format + lint. Note `biome ci`, **not**
   `biome check --write`: the `ci` variant is check-only and is what the job asserts.
2. `pnpm --dir frontend/app run knip` — unused exports, files, and dependencies.
3. `pnpm --dir frontend/app exec betterer ci` — TypeScript regression gate. Note `betterer ci`,
   **not** bare `betterer`: the `ci` variant fails on any increase instead of rewriting the
   snapshot. This is **not** the same as running `tsc`.

**3B. Unit tests — if frontend changed** (mirrors job `frontend-tests`). Sequential:

1. `pnpm --dir frontend/app exec playwright install chromium` — the suite runs in browser mode
   and needs the browser present. One-off per machine; skip if already installed.
2. `pnpm --dir frontend/app run test:coverage` — the app suite, as CI runs it. Plain `pnpm test`
   passes the same specs but skips coverage collection.
3. `pnpm --dir frontend/packages/graph run test` — the `@infrahub/graph` package suite. **Easy to
   miss**: it is a separate step in the same CI job and lives outside `frontend/app`.

**3C. OpenAPI types** — *if the Phase 0 OpenAPI trigger paths changed* (mirrors job
`frontend-validate-openapi-types`):

```bash
pnpm --dir frontend/app run codegen:openapi && git diff --exit-code frontend/app/src/shared/api/rest/types.generated.ts
```

Regenerates the REST types from `schema/openapi.json`, then makes the same assertion CI does. A
non-empty diff means the types were out of sync — stage and commit the regenerated file.

**3D. GraphQL types** — *if the Phase 0 GraphQL trigger paths changed* (mirrors job
`frontend-validate-graphql-types`):

```bash
pnpm --dir frontend/app run codegen:graphql && git diff --exit-code frontend/app/src/shared/api/graphql/generated/graphql-env.d.ts frontend/app/src/shared/api/graphql/generated/graphql-cache.d.ts
```

Regenerates the gql.tada output from `schema/schema.graphql`. On a non-empty diff, stage and
commit both generated files.

**3E. Error catalogue bindings** — *if the Phase 0 error-catalogue trigger paths changed*
(mirrors job `frontend-validate-error-catalogue`):

```bash
pnpm --dir frontend/app run check:error-bindings
```

Verifies the generated bindings match `schema/error-catalogue.json`. On failure, run
`pnpm --dir frontend/app run generate:error-bindings` and commit the result.

---

## Phase 4 — Slow backend and docs checks

**Send all applicable commands in a SINGLE message as parallel Bash calls.**

**4B. Backend** — *if backend changed*

1. `uv run invoke backend.lint` — call this task directly rather than `uv run invoke lint`, which
   bundles `main.lint`, `backend.lint` and `yamllint` into one run and so ignores the area gating
   Phases 2B and 2C apply. Its ruff step covers `backend` only, the same coverage gap noted in
   Phase 2B, and its ty step repeats Phase 2B's — **mypy is what this check adds**. CI splits
   them: `ty` runs in `python-lint`, while
   `mypy` runs as a step inside `backend-tests-integration` and `backend-tests-functional`.
2. `uv run invoke backend.validate-generated` — ensures generated schema and protocol files are
   current. If it fails, run `uv run invoke backend.generate` and report the regenerated files.

**4C. Docs** — *if docs changed*

1. `uv run invoke docs.lint` — markdownlint + vale, mirroring the `markdown-lint` and
   `validate-documentation-style` jobs. Some pre-existing errors in `docs/docs/` may exist; only
   flag errors in files the user changed. This does **not** cover the `documentation` job, which
   runs `uv run invoke docs.build` — run that manually if you touched the Docusaurus config.
2. `uv run invoke docs.validate` — ensures generated reference documentation (CLI, schema,
   events, repository config, config) is current. If validation fails, the correct files are
   already on disk — stage and commit them.

**4D. Schema** — *if backend or `schema/**` changed*

1. `uv run invoke schema.validate-graphqlschema` — ensures `schema/schema.graphql` is current.
   Regenerates then checks for uncommitted diffs. On failure the correct file is already on disk;
   stage and commit it.
2. `uv run invoke schema.validate-jsonschema` — same approach for `schema/openapi.json`.

Both CI jobs gate on the `backend` filter, which does **not** include `schema/**`. Running them
on a schema-only change is deliberately stricter than CI, and cheap.

---

## Phase 5 — Slow unit tests

Run after all lint and validation checks pass.

**5.1** — *if backend changed* (mirrors job `backend-tests-unit`):

```bash
uv run invoke backend.test-unit
```

**5.2** — *if testcontainers changed* (mirrors job `backend-testcontainers-unit`):

```bash
uv run --directory python_testcontainers pytest --rootdir=. -c pyproject.toml -vs tests
```

`python_testcontainers` is a **separate uv project** with its own `pyproject.toml` and lockfile,
and 5.1 does not reach it — `backend.test-unit` runs `backend/tests/unit` only. CI runs this
suite as a Python 3.10–3.14 matrix; one interpreter is enough locally. Note the job also fires on
`.github/workflows/*.yml`, so a workflow edit alone puts it in scope.

---

## After all checks

Summarize in a table. Include **every** row; mark rows as `skipped (no <area> changes)` or
`skipped (--fast)` rather than omitting them, so it is obvious what was not covered.

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
| Lockfile sync | uv-check (`uv-check.yml`) | ... |
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
