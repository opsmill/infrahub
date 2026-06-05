# Backend Architecture

> Part of: `dev/knowledge/backend/` | Related: [AGENTS.md](../../../backend/AGENTS.md)

High-level overview of the Infrahub backend architecture.

## Tech Stack

- **Framework:** FastAPI (async-first)
- **Database:** Neo4j (graph database)
- **API:** GraphQL (primary) + REST
- **Python:** Python 3 with Pydantic

## Core Concepts

### Schema-Driven Architecture

Everything in Infrahub is defined by schemas. The schema system defines what nodes exist, their attributes, relationships, and constraints.

### Git-Like Branching

Infrahub provides version control for infrastructure data. Multiple branches can exist with different data states, and changes can be diffed and merged.

### Query Pattern

All database access goes through Query classes that encapsulate Cypher queries with proper parameterization. See [query-pattern.md](query-pattern.md).

### Database Schema

The Neo4j database uses a temporal graph structure with branch support. All vertices and edges include branch and timestamp metadata for version control. See [database-schema.md](database-schema.md).

### Proposed Changes

Similar to pull requests, proposed changes allow reviewing and approving data modifications before merging.

## Layer Responsibilities

| Layer | Responsibility | Key Directories |
|-------|----------------|-----------------|
| API | HTTP handling, serialization | `api/`, `graphql/` |
| Auth | Password/SSO/LDAP login, SSO group resolution, auto-create groups | `auth/`, `ldap_auth/` |
| Core | Business logic, domain models | `core/` |
| Database | Query execution, connection mgmt | `database/` |
| Workers | Async task processing | `workers/`, `task_manager/` |
| Events | Pub/sub, triggers | `events/`, `message_bus/` |
| Webhooks | HTTP notification delivery | `webhook/` |

## Entry Points

- **Server:** `server.py` - FastAPI application factory
- **Config:** `config.py` - Pydantic settings management
- **Database:** `database/__init__.py` - `InfrahubDatabase` client
- **Registry:** `core/__init__.py` - Central node class registry

## See Also

### Related Knowledge

- [Testing](testing.md) - Testing infrastructure and patterns
- [Authentication](authentication.md) - Login flow, SSO group resolution, auto-create groups
- [Events System](events.md) - Event-driven architecture
- [Async Tasks](async-tasks.md) - Background task processing
- [Message Bus](message-bus.md) - Inter-service communication
- [Computed Attributes](computed-attributes.md) - Jinja2 evaluation paths and schema registry
- [Object Templates](templates.md) - Template generation, application, and resource pool integration

### Guidelines

- [Python Coding Standards](../../guidelines/backend/python.md) - How to write backend code
- [Backend AGENTS.md](../../../backend/AGENTS.md) - Quick reference and commands
