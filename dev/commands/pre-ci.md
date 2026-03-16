---
description: Run all locally-executable CI checks (format, lint, unit tests)
argument-hint:
allowed-tools:
  - Bash(uv run invoke:*)
  - Bash(uv run ruff check:*)
  - Bash(uv lock --check:*)
  - Bash(cd frontend*:*)
  - Bash(npx biome*:*)
  - Bash(npx betterer*:*)
  - Bash(npx markdownlint*:*)
---

# Pre-CI

Run all locally-executable CI checks to catch issues before pushing.

## Steps to Follow

Run these checks **sequentially** in the order below. Stop and report on first failure unless the failure is in formatting (which auto-fixes).

### 1. Format all Python code

```bash
uv run invoke format
```

This auto-fixes formatting issues via ruff. Always run this first.

### 2. Format documentation

```bash
uv run invoke docs.format
```

Auto-fixes Markdown formatting issues.

### 3. Format and lint frontend code (Biome)

```bash
cd frontend/app && npx biome check --write .
```

Auto-fixes formatting and lint issues in TypeScript/TSX files. If Biome reports errors that cannot be auto-fixed, report them to the user.

### 3b. Check TypeScript regressions (Betterer)

```bash
cd frontend/app && npx betterer
```

Ensures no new TypeScript errors are introduced. The issue count must stay the same or decrease. If it increases, report the new issues to the user.

### 4. Lint Python code (ruff + ty)

```bash
uv run invoke main.lint
uv run invoke backend.lint
```

Run these separately to avoid `uv run invoke lint` which includes a `yamllint -s .` step that fails on vendored packages in `.venv`. If ruff reports issues, they were not auto-fixable — report them to the user.

**Important:** `backend.lint` runs both ruff and ty together. The ty checker may panic with long tracebacks that bury ruff warnings. If `backend.lint` fails or has noisy output, **re-run ruff in isolation** on changed files to ensure no warnings were missed:

```bash
uv run ruff check <changed-files>
```

### 4b. Type-check with mypy

```bash
uv run invoke backend.mypy
```

Runs mypy on the backend. Report any errors — these are not auto-fixable.

### 5. Lint documentation (markdownlint + vale)

```bash
uv run invoke docs.lint
```

Report any errors. Note: some pre-existing errors in `docs/docs/` may exist — only flag errors in files the user has changed.

### 6. Check lockfile is in sync

```bash
uv lock --check
```

Ensures `uv.lock` matches `pyproject.toml`. If this fails, run `uv lock` and commit the updated lockfile.

### 7. Validate generated files

```bash
uv run invoke backend.validate-generated
```

Ensures generated schema and protocol files are up to date. If this fails, run `uv run invoke backend.generate` and report the regenerated files.

### 8. Validate GraphQL and JSON schemas

```bash
uv run invoke schema.validate-graphqlschema
uv run invoke schema.validate-jsonschema
```

Ensures `schema/schema.graphql` and `schema/openapi.json` are up to date. These regenerate the files then check for uncommitted diffs. If validation fails, the correct file is already on disk — just stage and commit it.

### 9. Run backend unit tests

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
| TS regressions (Betterer) | ... |
| Python lint | ... |
| mypy | ... |
| Docs lint | ... |
| Lockfile sync | ... |
| Generated files | ... |
| Schema validation | ... |
| Unit tests | ... |

If everything passed, tell the user they're ready to push.
If anything failed, list the specific failures and suggest fixes.
