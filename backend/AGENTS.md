# AGENTS.md - Backend

> See [root AGENTS.md](../AGENTS.md) for project-wide commands and guidelines.

## Overview

FastAPI backend with GraphQL API, Neo4j database, and async-first architecture.

## File Structure

- `infrahub/` – Main application
  - `api/` – REST endpoints
  - `auth/` – Authentication (password, SSO, LDAP) and auto-create groups (`auth/auth_groups/`)
  - `graphql/` – GraphQL schema, mutations, resolvers
  - `core/` – Domain logic (nodes, schemas, branches, diff)
  - `branch/` – Branch lifecycle enforcement (`BranchStatusChecker`, merge mutation checker)
  - `database/` – Database utilities
  - `workers/` – Background tasks
- `tests/` – Test suites (unit, integration, functional, benchmark)
- `templates/` – Jinja2 code generation templates

## Commands

```bash
uv run invoke backend.test-unit        # Unit tests
uv run invoke backend.test-integration # Integration tests (needs Neo4j)
uv run invoke backend.format           # Format with ruff
uv run invoke backend.lint             # Lint with ruff + mypy
uv run invoke backend.generate         # Regenerate schemas/protocols
```

## Coding Standards

See `dev/guidelines/backend/python.md` for detailed coding standards including:

- Async-first patterns
- Pydantic models
- Docstring conventions
- Naming conventions
- Query patterns
- Type hints

### Neo4j/Cypher Queries

When writing or modifying Cypher queries, **read `dev/knowledge/backend/database-schema.md`** first. It documents:

- Vertex types (Root, Branch, Node, Relationship, Attribute, AttributeValue)
- Edge types and properties (branch, from, to, status)
- Temporal branching rules and valid path patterns
- Example queries for common operations

Also see `dev/knowledge/backend/query-pattern.md` for the Query class pattern used to execute Cypher queries.

## Testing

See `dev/knowledge/backend/testing.md` for detailed testing infrastructure documentation.

## Boundaries

### Always Do

- Use async/await for all I/O
- Type hint all function parameters and returns
- Use Pydantic models for data structures
- Use Query class pattern for database operations
- Create changelog fragments with `towncrier create` — never hand-write the file. See `dev/guidelines/changelog.md`.

### Ask First

- New database indexes
- Core schema definition changes
- New GraphQL mutations/queries

### Never Do

- Unparameterized Cypher queries
- Block event loop with sync I/O
- Edit files in `infrahub/core/schema/generated/`

## See Also

### Guidelines

- `dev/guidelines/backend/python.md` - Python coding standards
- `dev/guidelines/changelog.md` - Changelog fragment creation

### Knowledge (How the system works)

Each entry says *when* to load it — open the doc before working in that area.

- `dev/knowledge/backend/architecture.md` - Backend architecture overview; read first for layer responsibilities and entry points
- `dev/knowledge/backend/query-pattern.md` - Read/write Query classes, return-shape, pagination, read-vs-write routing; read before writing or changing any DB access
- `dev/knowledge/backend/database-schema.md` - Neo4j temporal graph (vertices, edges, branch/time metadata); read before writing Cypher
- `dev/knowledge/backend/schema-definitions.md` - Defining nodes/relationships (cardinality, `on_delete`, constraints); read before changing the core schema
- `dev/knowledge/backend/mutations.md` - GraphQL mutation flow, upsert and HFID derivation; read before adding or overriding a mutation
- `dev/knowledge/backend/permissions.md` - Global/object permission model and checker pipeline; read before touching authorization
- `dev/knowledge/backend/authentication.md` - Authentication flow, SSO group resolution, auto-create groups; read when touching login, SSO, or LDAP
- `dev/knowledge/backend/branch-status.md` - Branch status enforcement (`BranchStatusChecker`, middleware allowlists, permission integration); read when touching branch lifecycle or write-protection
- `dev/knowledge/backend/events.md` - Events system; read when adding or changing an event
- `dev/knowledge/backend/async-tasks.md` - Prefect workflows, priority lanes, failure/best-effort handling; read before creating or changing a workflow
- `dev/knowledge/backend/message-bus.md` - Message bus system; read when adding or changing a message
- `dev/knowledge/backend/telemetry.md` - Anonymous usage telemetry (categories, windowing, retention, degradation); read when adding or changing telemetry metrics or the collection window
- `dev/knowledge/backend/webhooks.md` - Webhook delivery and failure classification; read when touching webhook delivery
- `dev/knowledge/backend/computed-attributes.md` - Jinja2 computed attributes and their recompute paths; read when touching Jinja2 computed attributes
- `dev/knowledge/backend/display-labels-and-hfid.md` - Display-label and human-friendly-id derivation; read when touching either
- `dev/knowledge/backend/templates.md` - Object template generation and application; read when touching templates
- `dev/knowledge/backend/code-generation.md` - Generated-file pipeline (protocols, schema, SDK); read before/after changing event, schema, CLI, or config code

### Guides (How to do X)

- `dev/guides/backend/creating-events.md` - Creating new events
- `dev/guides/backend/creating-async-tasks.md` - How to create an async task, with a pre-submit checklist. Load when adding a `@task`/`@flow`.
- `dev/guides/backend/creating-messages.md` - Creating message bus messages

### ADRs (Why we decided)

- `dev/adr/0002-events-system.md` - Events system design
- `dev/adr/0003-asynchronous-tasks.md` - Async tasks design
- `dev/adr/0004-message-bus.md` - Message bus design
