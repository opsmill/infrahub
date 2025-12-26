# 4. Message Bus Architecture

**Status:** Accepted
**Date:** 2024-12-26
**Author:** @opsmill-team

## Context

Infrahub requires asynchronous inter-component communication to support:

1. **Loose Coupling**: Components should communicate without direct dependencies
2. **Horizontal Scaling**: Workers should scale independently
3. **Rapid Response Operations**: Some operations require faster response times than workflow-based execution
4. **Broadcast Communication**: Ability to notify multiple workers simultaneously (e.g., registry refresh)

Historically, the message bus handled both task execution and broadcasts. With the adoption of Prefect (see ADR-0003), most asynchronous work migrated to workflows. The message bus now focuses on operations requiring rapid responses and broadcast notifications.

## Decision

We implement a message bus using **RabbitMQ** (primary) or **NATS** (alternative) for asynchronous inter-component communication.

### Core Principles

- **Typed Messages**: All messages are Pydantic models extending `InfrahubMessage`
- **Declarative Registration**: Messages map to routing keys via centralized `MESSAGE_MAP`
- **Two Messaging Patterns**: Support both broadcast (one-to-many) and RPC (request/reply)
- **Loop Prevention**: Initiator tracking prevents workers from processing their own broadcasts

### Message Patterns

**Broadcast Messaging**: One-to-many distribution using routing key patterns

- Used for notifications that all workers should process (e.g., `refresh.registry.branches`)
- Workers ignore messages originating from themselves via `initiator_id` check

**Request/Reply (RPC)**: Synchronous-style calls with response correlation

- Used when a response is required (e.g., `git.file.get`)
- Responses correlated via `correlation_id` in message metadata

### Scope of Message Bus vs Workflows

| Use Case | Message Bus | Prefect Workflow |
|----------|-------------|------------------|
| Rapid response needed | Yes | No |
| Broadcast to all workers | Yes | No |
| Long-running operations | No | Yes |
| User-visible execution | No | Yes |
| Requires observability/UI | No | Yes |
| Database modifications | Avoid | Yes |

## Consequences

### Positive

- **Decoupled communication**: Components interact without direct dependencies
- **Horizontal scaling**: Workers scale independently based on message load
- **Non-blocking execution**: Operations don't block HTTP request handling
- **Automatic retries**: Built-in retry logic with exponential backoff
- **Multiple broker support**: RabbitMQ and NATS implementations available
- **Priority support**: Messages can be prioritized (1-5 scale)

### Negative

- **Infrastructure overhead**: Requires deploying and managing message broker
- **Delivery guarantees**: Message ordering and delivery require careful configuration
- **Debugging complexity**: Distributed message flow harder to trace than direct calls
- **Monitoring needs**: Requires dedicated observability for message queues
- **Potential message loss**: Without proper configuration, messages may be lost

### Neutral

- **Reduced scope**: Most task execution now handled by Prefect workflows
- **Specialized use cases**: Message bus reserved for specific patterns (broadcast, rapid RPC)

## Implementation Notes

Key implementation locations:

- Base message classes: `backend/infrahub/message_bus/__init__.py`
- Message definitions: `backend/infrahub/message_bus/messages/`
- Operation handlers: `backend/infrahub/message_bus/operations/`
- Message registry: `backend/infrahub/message_bus/messages/__init__.py`

See also:

- `dev/knowledge/backend/message-bus.md` - How the message bus works
- `dev/guides/backend/creating-messages.md` - How to create a new message
- `dev/adr/0002-events-system.md` - Event system (uses message bus for internal dispatch)
- `dev/adr/0003-asynchronous-tasks.md` - Workflow system (preferred for most async operations)
