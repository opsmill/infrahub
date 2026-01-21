# FileObject Feature Implementation

**Epic:** [IFC-2140](https://opsmill.atlassian.net/browse/IFC-2140)

This directory contains the implementation plan for the FileObject feature, divided into 5 independent bodies of work (PRs).

## Overview

The FileObject feature allows users to upload files and link them to other objects in Infrahub. Users define their own file object types by inheriting from `CoreFileObject`.

## Architecture

**Read [00-architecture.md](./00-architecture.md) first** to understand:
- How the storage system works (immutable, key-value)
- Why no storage layer changes are needed
- How version control works through the database
- How branch isolation and time navigation work

## PRs

| Order | PR | Jira | Branch | Description | Dependencies |
|-------|-----|------|--------|-------------|--------------|
| 1 | [Schema](./01-schema.md) | IFC-2151 | `feature/file-object-schema` | CoreFileObject generic definition | None |
| 2 | [Config](./02-config.md) | IFC-2152 | `feature/file-object-config` | max_file_size setting | None |
| 3 | [GraphQL Tests](./04-graphql.md) | | `feature/file-object-graphql` | Tests for auto-generated API | PR 1 |
| 4 | [GraphQL Upload](./05-graphql-upload.md) | IFC-2174 | `feature/file-object-graphql-upload` | Custom Upload scalar, file parameter in mutations | PR 1, PR 2, PR 3 |
| 5 | [REST API](./03-rest-api.md) | IFC-2173, IFC-2176 | `feature/file-object-rest-api` | Download endpoint (upload optional) | PR 1, PR 2, PR 4 |

**Note:** Python SDK methods will be handled in a separate session.

**Note:** GraphQL upload is the primary file upload method. REST upload may be removed if GraphQL proves sufficient.

## Dependency Graph

```
PR 1 (Schema) ──────────────┬────────────────► PR 3 (GraphQL Tests) ────► PR 4 (GraphQL Upload)
                            │                                                       │
PR 2 (Config) ──────────────┴───────────────────────────────────────────────────────┴────► PR 5 (REST API)
```

## Recommended Workflow

1. **Start PR 1 and PR 2 in parallel** - They have no dependencies
2. **Start PR 3 after PR 1 is merged** - GraphQL tests need the schema
3. **Start PR 4 after PR 1, PR 2, and PR 3 are merged** - Needs schema, config, and GraphQL foundation
4. **Start PR 5 after PR 4 is merged** - REST download; upload optional if GraphQL is sufficient

## Progress Tracking

Use the checkboxes in each PR file to track implementation progress.

## Related Documents

- [Feature Specification](../../specs/2026-01-file-object.md) - Full feature specification
- [Backend Guidelines](../../guidelines/backend/python.md) - Coding standards
- [Backend Testing Guidelines](../../knowledge/backend/testing.md) - Testing standards

## Commands

```bash
# Run backend tests
uv run invoke backend.test-unit

# Run backend linting
uv run invoke lint

# Format code
uv run invoke format

# Generate backend code (after schema changes)
uv run invoke backend.generate

# Generate GraphQL schema (after schema changes)
uv run invoke schema.generate-graphqlschema

# Generate frontend GraphQL types (after GraphQL schema changes)
cd frontend/app && npm run codegen:graphql
```
