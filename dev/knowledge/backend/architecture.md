# Backend Architecture

> Part of: `dev/knowledge/backend/` | Related: [AGENTS.md](../../../backend/AGENTS.md)

High-level overview of the Infrahub backend architecture.

## Tech Stack

- **Framework:** FastAPI 0.121.1 (async-first)
- **Database:** Neo4j 5.28 (graph database)
- **API:** GraphQL (primary) + REST
- **Python:** 3.12 with Pydantic 2.10

## Core Concepts

### Schema-Driven Architecture

Everything in Infrahub is defined by schemas. The schema system defines what nodes exist, their attributes, relationships, and constraints. See [schema.md](schema.md).

### Git-Like Branching

Infrahub provides version control for infrastructure data. Multiple branches can exist with different data states, and changes can be diffed and merged. See [branching.md](branching.md).

### Query Pattern

All database access goes through Query classes that encapsulate Cypher queries with proper parameterization. See [query-pattern.md](query-pattern.md).

### Proposed Changes

Similar to pull requests, proposed changes allow reviewing and approving data modifications before merging. See [proposed-change.md](proposed-change.md).

## Layer Responsibilities

| Layer | Responsibility | Key Directories |
|-------|----------------|-----------------|
| API | HTTP handling, serialization, auth | `api/`, `graphql/` |
| Core | Business logic, domain models | `core/` |
| Database | Query execution, connection mgmt | `database/` |
| Workers | Async task processing | `workers/`, `task_manager/` |
| Events | Pub/sub, triggers, webhooks | `events/`, `message_bus/` |

## Entry Points

- **Server:** `server.py` - FastAPI application factory
- **Config:** `config.py` - Pydantic settings management
- **Database:** `database/__init__.py` - `InfrahubDatabase` client
- **Registry:** `core/__init__.py` - Central node class registry

## See Also

### Related Knowledge

- [Testing](testing.md) - Testing infrastructure and patterns
- [Events System](events.md) - Event-driven architecture
- [Async Tasks](async-tasks.md) - Background task processing
- [Message Bus](message-bus.md) - Inter-service communication

### Guidelines

- [Python Coding Standards](../../guidelines/backend/python.md) - How to write backend code
- [Backend AGENTS.md](../../../backend/AGENTS.md) - Quick reference and commands
