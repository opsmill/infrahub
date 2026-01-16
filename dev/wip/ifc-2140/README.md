# FileObject Feature Implementation

**Epic:** [IFC-2140](https://opsmill.atlassian.net/browse/IFC-2140)

This directory contains the implementation plan for the FileObject feature, divided into 4 independent bodies of work (PRs).

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
| 3 | [REST API](./03-rest-api.md) | IFC-2173, IFC-2176 | `feature/file-object-rest-api` | Upload/download endpoints | PR 1, PR 2 |
| 4 | [GraphQL](./04-graphql.md) | | `feature/file-object-graphql` | Tests for auto-generated API | PR 1 |

**Note:** Python SDK methods will be handled in a separate session.

## Dependency Graph

```
PR 1 (Schema) ──────────────┬────────────────► PR 4 (GraphQL Tests)
                            │
PR 2 (Config) ──────────────┴────────────────► PR 3 (REST API)
```

## Recommended Workflow

1. **Start PR 1 and PR 2 in parallel** - They have no dependencies
2. **Start PR 4 after PR 1 is merged** - Tests need the schema
3. **Start PR 3 after PR 1 and PR 2 are merged** - Needs schema and config

## Progress Tracking

Use the checkboxes in each PR file to track implementation progress.

## Related Documents

- [Feature Specification](../../specs/2026-01-file-object.md) - Full feature specification
- [Backend Guidelines](../../guidelines/backend/python.md) - Coding standards
- [Backend Testing Guidelines](../../knowledge/backend/testing.md) - Coding standards

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
```
