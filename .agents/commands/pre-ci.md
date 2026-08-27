---
description: Run all locally-executable CI checks (format, lint, unit tests) for the areas you changed
argument-hint: "[--fast] [--all]"
allowed-tools:
  - Bash(git fetch:*)
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

Run the locally-executable CI checks that apply to what you changed. **Every check below mirrors
a job in `.github/workflows/ci.yml` — keep them in parity.**

**Every command runs from the repository root and must leave the working directory unchanged.**
The parallel phases share a single shell, so a `cd` in one command silently changes where its
siblings run and the `invoke` tasks fail on relative paths. That is why the frontend checks use
`pnpm --dir` — do not rewrite them as `cd frontend/app && ...`.

**Options:**

- `--fast` — Formatting and fast lint only (~20s). Skips backend lint (ty/mypy), Betterer, docs
  lint, generated-file and doc validation, schema validation, and all unit tests.
- `--all` — Skip detection and run every phase regardless of what changed.

---

## Phase 0 — Detect what changed

Run this first. Everything after it is conditional on the result.

```bash
git fetch --quiet origin stable develop 2>/dev/null || echo "WARNING: base refs may be stale"

BASE_REF=""
for R in origin/stable origin/develop; do
  git rev-parse --verify --quiet "$R" >/dev/null || continue
  if [ -z "$BASE_REF" ] || git merge-base --is-ancestor \
       "$(git merge-base HEAD "$BASE_REF")" "$(git merge-base HEAD "$R")"; then
    BASE_REF=$R
  fi
done

if [ -z "$BASE_REF" ]; then
  echo "No base ref resolved - treat every area as changed"
else
  MERGE_BASE=$(git merge-base HEAD "$BASE_REF")
  { git diff --name-only --no-renames "$MERGE_BASE"...HEAD
    git diff --name-only --no-renames HEAD
    git ls-files --others --exclude-standard
  } | sort -u
fi
```

Each line of that block earns its place — do not simplify it:

- The winner is the candidate whose merge base sits **closer to HEAD**, the branch's real fork
  point. Preferring `develop` unconditionally diffs a `stable`-based branch tens of commits back.
- **Every** ref is existence-checked, including the first. An unguarded `git merge-base` aborts
  the block on a fork that carries only one branch, leaving `MERGE_BASE` empty and detecting
  *nothing*. An empty `BASE_REF` must reach the all-areas fallback instead.
- `git fetch` first: a stale ref can flip the choice between the two candidates. If it fails,
  the run is best-effort — prefer `--all`.
- `--no-renames` keeps both sides of a rename, so the area that *lost* a file is still flagged.
  Do not swap in `git status --porcelain`, whose `R  old -> new` collapses into one bogus path.
- The list covers **committed and uncommitted** work: CI sees the former, you are about to push
  the latter.

Classify the paths using the same globs as `.github/file-filters.yml`. Each area below is that
file's `<area>_all` list, so local gating matches the `files-changed` outputs CI branches on:

| Area | Paths | Enables |
|---|---|---|
| **frontend** | `frontend/app/**`, `frontend/packages/**`, `frontend/package.json`, `frontend/pnpm-workspace.yaml`, `frontend/pnpm-lock.yaml`, `schema/openapi.json`, `frontend/app/src/shared/api/rest/types.generated.ts`, `development/**`, `tasks/**`, `.github/workflows/ci.yml`, `.github/file-filters.yml` | Phases 1A, 3B |
| **backend** | `backend/**`, `python_sdk`, `development/**`, `tasks/**`, `**/pyproject.toml`, `**/uv.lock`, `.github/workflows/ci.yml`, `.github/file-filters.yml` | Phases 1B, 2B, 4B, 4D, 5 |
| **python** | any other `**/*.py` — `models/`, `utilities/`, `python_testcontainers/`, `tests/`, root scripts | Phases 1B, 2B |
| **testcontainers** | `python_testcontainers/**`, `.github/workflows/*.yml` (any workflow, not just `ci.yml`) | Phase 5.2 |
| **docs** | `docs/**`, `**/*.{md,mdx}`, `.vale/**`, `.vale.ini`, `package.json`, `package-lock.json`, `development/**`, `tasks/**`, `python_sdk` | Phases 1C, 4C |
| **schema** | `schema/**` | Phase 4D |
| **yaml** | `**/*.{yml,yaml}`, `**/pyproject.toml`, `**/uv.lock` | Phase 2C |

`python` is deliberately narrower than `backend`: `python-lint` fires on `backend || python`, but
`backend-tests-unit`, `graphql-schema` and `json-schema` gate on `backend` alone, so a `models/`
or root-script change must run the lint phases and **not** the slow ones.

Three frontend validation jobs gate on their own narrow filters rather than the whole frontend
area — check these paths separately:

| Trigger paths | Enables |
|---|---|
| `schema/openapi.json`, `frontend/app/src/shared/api/rest/types.generated.ts` | Phase 3C |
| `schema/schema.graphql`, `frontend/app/src/shared/api/graphql/generated/**` | Phase 3D |
| `schema/error-catalogue.json`, `frontend/app/src/shared/api/errors/catalogue.generated.ts`, `frontend/app/scripts/generate-error-bindings.mjs` | Phase 3E |

If `--all` was passed, or no base ref resolved, treat every area as changed.

**State the detected areas before running anything**, e.g.
`Detected changes: frontend, docs. Skipping backend phases.`

Sub-step letters encode the area — **A** = frontend, **B** = backend or python, **C** = docs
(yaml in Phase 2), **D** = schema — so a phase skips letters where an area has nothing to do.
Phase 3 is the exception: it is entirely frontend, so `3A`–`3E` enumerate its individual CI jobs.

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
5. `uv lock --check` — on failure run `uv lock` and commit the updated lockfile.

Steps 2–4 are CI's `python-lint` job verbatim, and none is redundant with step 1 or Phase 1B: the
`invoke` tasks only reach `tasks`, `models`, `utilities`, `python_testcontainers` and `backend`,
so a violation under `development/`, `tests/` or the repo root passes locally and fails CI. `ty`
is otherwise reachable only through Phase 4B, which the `python` area does not enable.

**2C. YAML** — *if yaml changed*

1. `uv run yamllint -s .` — CI's `yaml-lint` job verbatim. **Easy to miss**: it fires on any
   `**/*.{yml,yaml}` change, so a workflow or compose edit with no Python in it still has a check
   to pass. Call it directly, not via `uv run invoke lint`, which bundles unrelated steps.

---

> **If `--fast` was specified, stop here** and report results, marking slow checks as "skipped".

---

## Phase 3 — Frontend gate (CI parity)

The **complete** set of frontend checks CI runs. A partial pass here is what lets `frontend-lint`
and `frontend-tests` fail on the PR. If dependencies are stale, first run
`pnpm --dir frontend/app install --frozen-lockfile` (CI always does).

**3A. Lint trio — ALWAYS run, regardless of detected areas** (job `frontend-lint`). Send as
parallel Bash calls:

1. `pnpm --dir frontend/app exec biome ci .` — note `biome ci`, **not** `biome check --write`:
   the `ci` variant is check-only and is what the job asserts.
2. `pnpm --dir frontend/app run knip` — unused exports, files, and dependencies.
3. `pnpm --dir frontend/app exec betterer ci` — note `betterer ci`, **not** bare `betterer`,
   which rewrites the snapshot instead of failing. This is **not** the same as running `tsc`.

**3B. Unit tests — if frontend changed** (job `frontend-tests`). Sequential:

1. `pnpm --dir frontend/app exec playwright install chromium` — the suite runs in browser mode.
   One-off per machine; skip if already installed.
2. `pnpm --dir frontend/app run test:coverage` — as CI runs it; plain `pnpm test` skips coverage.
3. `pnpm --dir frontend/packages/graph run test` — the `@infrahub/graph` suite. **Easy to miss**:
   a separate step in the same job, living outside `frontend/app`.

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

1. `uv run invoke backend.lint` — call this task directly, not `uv run invoke lint`, which bundles
   `main.lint`, `backend.lint` and `yamllint` and so ignores the gating of Phases 2B and 2C. Its
   ruff and ty steps repeat those phases — **mypy is what this adds**. CI splits them: `ty` in
   `python-lint`, `mypy` inside `backend-tests-integration` and `backend-tests-functional`.
2. `uv run invoke backend.validate-generated` — on failure run `uv run invoke backend.generate`
   and report the regenerated files.

**4C. Docs** — *if docs changed*

1. `uv run invoke docs.lint` — markdownlint + vale, mirroring `markdown-lint` and
   `validate-documentation-style`. Pre-existing errors in `docs/docs/` may exist; only flag those
   in changed files. Does **not** cover the `documentation` job, which runs
   `uv run invoke docs.build` — run that manually if you touched the Docusaurus config.
2. `uv run invoke docs.validate` — generated reference docs (CLI, schema, events, repository
   config, config). On failure the correct files are already on disk; stage and commit them.

**4D. Schema** — *if backend or schema changed*

1. `uv run invoke schema.validate-graphqlschema` — regenerates, then checks for uncommitted
   diffs. On failure the correct file is already on disk; stage and commit it.
2. `uv run invoke schema.validate-jsonschema` — same, for `schema/openapi.json`.

Both jobs gate on the `backend` filter, which does **not** include `schema/**` — hence the
separate `schema` area. Running these on a schema-only change is deliberately stricter than CI.

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

5.1 does not reach 5.2's suite: `backend.test-unit` runs `backend/tests/unit` only, and
`python_testcontainers` is a separate uv project. CI runs it as a Python 3.10–3.14 matrix; one
interpreter is enough locally.

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
