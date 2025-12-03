# ADR-0001: Async-First Architecture

## Status

Draft

## Context

Infrahub backend needs to handle high concurrency and I/O-bound operations efficiently. The system performs many database queries, external API calls, and file operations that can block execution.

## Decision

We will use async/await throughout the backend, making all I/O operations asynchronous. FastAPI is used as the web framework, and all database operations, message bus interactions, and external service calls use async patterns.

## Consequences

### Positive

- High concurrency without thread overhead
- Better resource utilization for I/O-bound workloads
- Natural fit with FastAPI and modern Python async libraries
- Scalable architecture for handling many concurrent requests

### Negative

- All code paths must be async-aware
- Requires async-compatible libraries
- More complex error handling and debugging
- Learning curve for developers unfamiliar with async patterns

## Notes

- All database queries use async Neo4j driver (`neo4j.AsyncDriver`)
- Message bus operations are async (NATS/RabbitMQ with async clients)
- Background tasks use Prefect flows which integrate with async
- Type hints required for all async functions
- Testing uses `pytest-asyncio` for async test support
- All FastAPI endpoints and GraphQL resolvers are async functions
- Database sessions are automatically closed via async context managers
- Transactions automatically rollback on exceptions via `__aexit__` implementation
