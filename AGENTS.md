# Infrahub

Infrahub is a graph-based infrastructure data management platform by OpsMill. It combines Git-like branching and version control with a flexible graph database (Neo4j) and a modern UI/API layer.

## Conversation Style

Responses must be direct and substantive. Do not use filler phrases, compliments, or social pleasantries.

**Prohibited phrases** (including variations):

- "You're right", "You're absolutely right", "Great question", "Good idea"
- "I apologize", "I'm sorry", "Sorry about that"
- "Let me explain", "Let me walk you through", "I'd be happy to"

**Required behavior:**

- Do not use introductory or transitional filler of any kind
- Get to the point immediately — no preamble
- Challenge ideas and assumptions when warranted
- Ask clarifying questions rather than guessing intent
- Offer direct criticism when an approach has flaws

## Tech Stack

- **Backend:** Python 3.13, FastAPI 0.131.0, Neo4j 2025.10 (driver 6.0), Pydantic 2.12
- **Frontend:** TypeScript 5.9, React 19.2, Vite 8.0, Tailwind CSS 4.2
- **Testing:** pytest 9.0, Vitest 4.1, Playwright 1.60
- **Linting:** ruff 0.15, mypy 1.15, Biome 2.4
- **Package Managers:** uv (Python), pnpm (Frontend)
- **Task Runner:** Invoke 2.2.1

## File Structure

- `backend/` – Python backend (FastAPI, GraphQL, core logic) - see [backend/AGENTS.md](backend/AGENTS.md)
- `frontend/app/` – React frontend - see [frontend/app/AGENTS.md](frontend/app/AGENTS.md)
- `docs/` – Docusaurus documentation - see [docs/AGENTS.md](docs/AGENTS.md)
- `python_sdk/` – Python SDK (Git submodule)
- `tasks/` – Invoke task definitions
- `schema/` – JSON/GraphQL schema definitions
- `changelog/` – Towncrier changelog fragments
- `dev/` – Internal developer documentation - see [dev/README.md](dev/README.md)

## Commands

### Setup

```bash
uv sync --all-groups                  # Install Python dependencies
cd frontend/app && pnpm install       # Install frontend dependencies
```

### Testing

```bash
uv run invoke backend.test-unit       # Backend unit tests
uv run invoke backend.test-integration # Backend integration tests
cd frontend/app && pnpm test          # Frontend unit tests
cd frontend/app && pnpm test:e2e      # Frontend E2E tests (legacy TS suite)
uv run pytest -c tests/e2e/pytest.ini tests/e2e  # E2E tests (pytest, testcontainers)
```

#### Debugging e2e tests with `--pdb`

**Always run `tests/e2e/` tests with `--pdb` when debugging locally.**
Re-running the suite just to attach a debugger after a failure wastes minutes
per iteration (stack boot + data load); with `--pdb` a failure freezes the
session at the failure line with the testcontainers stack, the SDK clients,
the browser page and every fixture still alive. If the test passes, `--pdb`
costs nothing.

```bash
uv run pytest -c tests/e2e/pytest.ini tests/e2e/<node_id> -s --pdb
```

While paused, inspect the live stack from a second shell:

```bash
docker ps --filter name=infrahub-test          # the session's compose project
PROJECT=$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep infrahub-test | head -1)
docker compose -p $PROJECT port infrahub-server-lb 8000   # API/UI address on localhost
docker compose -p $PROJECT logs infrahub-server task-worker --tail 100
```

When running through a non-interactive shell (background job, agent tool),
prefix the command with `sleep infinity |` so pdb's stdin stays open instead
of hitting EOF and exiting (which tears the stack down):

```bash
sleep infinity | uv run pytest -c tests/e2e/pytest.ini tests/e2e/<node_id> -s --pdb 2>&1 | tee /tmp/pdb.log
```

Pytest then stays paused indefinitely on failure (`-s` keeps pdb's output
unbuffered through the pipe). Inspect with docker/curl from a separate shell,
then kill the process once done — pdb cannot receive commands over the dummy
stdin. Match the node id, not the literal shell line (a bare
`pkill -f <pattern>` kills your own shell if the pattern appears in its
command line). Killing pytest skips the fixture teardown, so sweep the
leftover stack afterwards: `docker compose -p $PROJECT down -v
--remove-orphans`.

See `tests/e2e/README.md` for the suite architecture and data fixtures.

### Linting & Formatting

```bash
uv run invoke format                  # Format all Python code
uv run invoke lint                    # Lint all Python code
cd frontend/app && pnpm biome:fix     # Format/lint frontend
uv run invoke docs.lint               # Lint documentation
```

### Build

```bash
uv run invoke dev.build               # Build Docker containers
cd frontend/app && pnpm build         # Build frontend
cd docs && npm run build              # Build documentation
```

## Coding Standards

- Backend: `dev/guidelines/backend/python.md`
- Frontend: `frontend/app/AGENTS.md`
- Git workflow: `dev/guidelines/git-workflow.md`
- Markdown: `dev/guidelines/markdown.md`

## Generated Files (Do Not Edit)

- `backend/infrahub/core/schema/generated/` – Schema definitions
- `backend/infrahub/core/protocols.py` – Protocol definitions
- `frontend/app/src/shared/api/graphql/generated/` – GraphQL types
- `frontend/app/src/shared/api/rest/types.generated.ts` – REST types
- `schema/schema.graphql` - GraphQL schema of the Core Schema
- `schema/openapi.json` - OpenAPI schema for the REST API
- `docs/docs/reference/{infrahub-cli,schema,infrahub-events}/`, `docs/docs/reference/{dotinfrahub,message-bus-events,configuration}.mdx` – Reference docs rendered from backend source (CLI, schema, events, repository config, message-bus events, configuration)

Regenerate backend (offline): `uv run invoke backend.generate`
Export GraphQL schema: `uv run invoke schema.generate-graphqlschema`
Export OpenAPI schema: `uv run invoke schema.generate-jsonschema`
Regenerate frontend types (offline, reads local schema files): `cd frontend/app && pnpm codegen`
Regenerate reference docs (offline): `uv run invoke docs.generate`

CI validates that all generated files are committed — the `validate-generated-documentation` job runs `uv run invoke docs.validate` and fails when a generated doc is stale. After changing event classes, schema models, CLI commands, or config, regenerate and commit the affected files. See `dev/knowledge/backend/code-generation.md` for the full pipeline.

## Boundaries

### Always Do

- Before modifying code in any domain, read the relevant docs in `dev/knowledge/` for that domain
- Run formatters before committing (`uv run invoke format`, `pnpm biome:fix`)
- Write tests for new functionality
- Use type hints for Python (backend) and TypeScript types (frontend)
- Before pushing, run `/pre-ci` (`dev/commands/pre-ci.md`) — it runs the locally-executable CI checks, including generated-file and generated-doc validation (`docs.validate`); CI fails if any generated file is stale

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

## Navigation

| Question | Location |
|----------|----------|
| How does the system work? | `dev/knowledge/` |
| How do I do X? | `dev/guides/` |
| Why was this decided? | `dev/adr/` |
| What are we building? | `dev/specs/` |
| How should I write code? | `dev/guidelines/` |
| What commands are available? | `dev/commands/` |

## Component Maps

- Backend: `backend/AGENTS.md`
- Frontend: `frontend/app/AGENTS.md`
- Documentation: `docs/AGENTS.md`
- Python SDK: `python_sdk/AGENTS.md`
