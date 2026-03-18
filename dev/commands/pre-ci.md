---
description: Run all locally-executable CI checks (format, lint, unit tests)
argument-hint: "[--fast]"
allowed-tools:
  - Bash(uv run invoke:*)
  - Bash(uv run ruff check:*)
  - Bash(uv lock --check:*)
  - Bash(cd frontend*:*)
  - Bash(npm run codegen*:*)
  - Bash(npx biome*:*)
  - Bash(npx betterer*:*)
  - Bash(npx markdownlint*:*)
---

# Pre-CI

Run all locally-executable CI checks to catch issues before pushing.

**Options:**

- `--fast` — Run only formatting and fast lint checks (~20s). Skips backend lint (ty/mypy), Betterer, docs lint, generated file validation, schema validation, and unit tests.

## Phase 1 — Auto-fix formatting (sequential)

Run these **sequentially** — they modify files and must complete before lint checks.

### 1. Format all Python code

```bash
uv run invoke format
```

This auto-fixes formatting issues via ruff. Always run this first.

### 2. Format documentation

```bash
uv run invoke docs.format
```

Auto-fixes markdown formatting issues.

### 3. Format and lint frontend code (Biome)

```bash
cd frontend/app && npx biome check --write .
```

Auto-fixes formatting and lint issues in TypeScript/TSX files. If Biome reports errors that cannot be auto-fixed, report them to the user.

## Phase 2 — Fast checks (parallel)

**IMPORTANT: Send ALL 3 commands below in a SINGLE message with 3 parallel Bash tool calls.** Do NOT run them one at a time.

1. `uv run invoke main.lint` — If ruff reports issues, they were not auto-fixable — report them to the user.
2. `uv lock --check` — Ensures `uv.lock` matches `pyproject.toml`. If this fails, run `uv lock` and commit the updated lockfile.
3. `cd frontend/app && npm run codegen:graphql` — Regenerates `graphql-env.d.ts` and `graphql-cache.d.ts` from `schema/schema.graphql`. If the files change, they need to be staged and committed.

---

> **If `--fast` was specified, stop here** and report results. Show the summary table with slow checks marked as "skipped".

---

## Phase 3 — Slow checks (parallel)

**IMPORTANT: Send ALL 6 commands below in a SINGLE message with 6 parallel Bash tool calls.** Do NOT run them one at a time.

1. `uv run invoke backend.lint` — Run separately from main.lint to avoid `uv run invoke lint` which includes a `yamllint -s .` step that fails on vendored packages in `.venv`. If ruff reports issues, they were not auto-fixable — report them to the user.
2. `cd frontend/app && npx betterer` — Ensures no new TypeScript errors are introduced. The issue count must stay the same or decrease. If it increases, report the new issues to the user.
3. `uv run invoke docs.lint` — Report any errors. Note: some pre-existing errors in `docs/docs/` may exist — only flag errors in files the user has changed.
4. `uv run invoke backend.validate-generated` — Ensures generated schema and protocol files are up to date. If this fails, run `uv run invoke backend.generate` and report the regenerated files.
5. `uv run invoke schema.validate-graphqlschema` — Ensures `schema/schema.graphql` is up to date. Regenerates the file then checks for uncommitted diffs. If validation fails, the correct file is already on disk — just stage and commit it.
6. `uv run invoke schema.validate-jsonschema` — Ensures `schema/openapi.json` is up to date. Same approach as GraphQL schema validation.

## Phase 4 — Unit tests

Run after all lint/validation checks pass.

```bash
uv run invoke backend.test-unit
```

Report pass/fail summary.

## After All Checks

Summarize results in a table:

| Check | Status |
|-------|--------|
| Python format | ... |
| Docs format | ... |
| Frontend format/lint | ... |
| Main Python lint | ... |
| Lockfile sync | ... |
| Frontend GraphQL types | ... |
| Backend lint (ty/mypy) | ... |
| TS regressions (Betterer) | ... |
| Docs lint | ... |
| Generated files | ... |
| GraphQL schema validation | ... |
| JSON schema validation | ... |
| Unit tests | ... |

If `--fast` was used, show skipped checks as "skipped".
If everything passed (or was skipped), tell the user they're ready to push.
If anything failed, list the specific failures and suggest fixes.
