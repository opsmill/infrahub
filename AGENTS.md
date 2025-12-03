# AGENTS.md

## Project Overview

Infrahub is a graph-based infrastructure data management platform by OpsMill. It combines Git-like branching and version control with a flexible graph database (Neo4j) and a modern UI/API layer.

## Tech Stack

- **Backend:** Python 3.12, FastAPI 0.121.1, Neo4j 5.28, Pydantic 2.10
- **Frontend:** TypeScript 5.9, React 19.2, Vite 7.2, Tailwind CSS 4.1
- **Testing:** pytest 7.4, Vitest 4.0, Playwright 1.56
- **Linting:** ruff 0.14.5, mypy 1.15, Biome 2.3
- **Package Managers:** uv (Python), npm (Frontend)
- **Task Runner:** Invoke 2.2.0

## File Structure

- `backend/` – Python backend (FastAPI, GraphQL, core logic) - see [backend/AGENTS.md](backend/AGENTS.md)
- `frontend/app/` – React frontend - see [frontend/app/AGENTS.md](frontend/app/AGENTS.md)
- `docs/` – Docusaurus documentation - see [docs/AGENTS.md](docs/AGENTS.md)
- `python_sdk/` – Python SDK (Git submodule)
- `tasks/` – Invoke task definitions
- `schema/` – JSON/GraphQL schema definitions
- `changelog/` – Towncrier changelog fragments

## Commands

### Setup

```bash
uv sync --all-groups                  # Install Python dependencies
cd frontend/app && npm install        # Install frontend dependencies
```

### Testing

```bash
uv run invoke backend.test-unit       # Backend unit tests
uv run invoke backend.test-integration # Backend integration tests
cd frontend/app && npm run test       # Frontend unit tests
cd frontend/app && npm run test:e2e   # Frontend E2E tests
```

### Linting & Formatting

```bash
uv run invoke format                  # Format all Python code
uv run invoke lint                    # Lint all Python code
cd frontend/app && npm run biome:fix  # Format/lint frontend
uv run invoke docs.lint               # Lint documentation
```

### Build

```bash
uv run invoke dev.build               # Build Docker containers
cd frontend/app && npm run build      # Build frontend
cd docs && npm run build              # Build documentation
```

## Generated Files (Do Not Edit)

- `backend/infrahub/core/schema/generated/` – Schema definitions
- `backend/infrahub/core/protocols.py` – Protocol definitions
- `frontend/app/src/shared/api/graphql/generated/` – GraphQL types
- `frontend/app/src/shared/api/rest/types.generated.ts` – REST types
- `schema/schema.graphql` - GraphQL schema of the Core Schema
- `schema/openapi.json` - OpenAPI schema for the REST API

Regenerate with: `uv run invoke backend.generate` or `cd frontend/app && npm run codegen`

## Markdown Formatting

When editing markdown files (enforced by markdownlint):

- Use `-` for unordered lists
- Add blank line before/after headings, code blocks, and lists
- Use fenced code blocks with language identifier
- No trailing spaces or multiple consecutive blank lines
- No bare URLs (use `[text](url)` format)

## Towncrier for changelog

Towncrier is used to manage the changelog which is being published with every release.
Every issue that is being fixed, or new feature that gets implemented should be accompanied by a proper changelog entry.

The changelog message should be a short and user-facing. It should describe what has been fixed or implemented without focusing on the technical aspects of the implementation.

To create a new changelog entry use the following command.
The filename should be in the format `${ISSUE}.{ACTION}.md`:

- ${ISSUE}: the id of the GitHub issue or feature request, if you are not working on an issue or feature request use `+`.
- ${ACTION}: one of added, fixed, housekeeping

```bash
uv run towncrier -c "content of changelog entry" ${ISSUE}.{ACTION}.md
```

## Git Workflow

- **Main branches:** `stable` (production), `develop` (development), `release-*` (releases)
- **Commit messages:** Conventional commits; include issue references
- **Changelog:** Add fragment to `changelog/` using Towncrier format

## Boundaries

### Always Do

- Run formatters before committing (`uv run invoke format`, `npm run biome:fix`)
- Write tests for new functionality
- Use type hints for Python (backend) and TypeScript types (frontend)

### Ask First

- Database schema or migration changes
- GraphQL schema modifications
- New dependencies
- CI/CD workflow changes
- Authentication/authorization changes

### Never Do

- Commit secrets, API keys, or credentials
- Edit generated files manually
- Skip linting in CI
- Force push to `stable` or `develop`
