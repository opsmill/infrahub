# ADR-0007: Component-Based Services

## Status

Draft

## Context

Infrahub requires multiple services (cache, message bus, workflow, database) that may have different implementations. The system needs to support pluggable adapters, dependency injection, and service lifecycle management. Components must be testable in isolation.

## Decision

We use a component-based service architecture with adapter patterns and dependency injection. Services are abstracted behind interfaces, with concrete implementations injected at runtime. The component registry manages service instances and their lifecycle.

## Consequences

### Positive

- Pluggable service implementations
- Easy testing with mock services
- Clear separation of concerns
- Support for multiple implementations (Redis/NATS cache, RabbitMQ/NATS message bus)
- Dependency injection simplifies configuration
- Service lifecycle managed centrally

### Negative

- Additional abstraction layer
- More interfaces and adapters to maintain
- Configuration complexity increases
- Requires understanding of dependency injection patterns
- Service initialization order matters

## Notes

- Service interfaces in infrahub/services/adapters/
- Concrete implementations for Redis, NATS, RabbitMQ, etc.
- Dependency injection via FastAPI dependencies
- Component registry in infrahub/dependencies/registry.py
- Services initialized during application startup
- Override mechanism for testing
