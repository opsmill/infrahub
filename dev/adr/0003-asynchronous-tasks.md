# 3. Asynchronous Tasks Execution with Prefect

**Status:** Accepted
**Date:** 2024-12-26
**Author:** @opsmill-team

## Context

Infrahub requires an asynchronous task execution framework to support:

1. **Task Reporting & Execution Tracking**: Centralized management of flow runs, state tracking, and log aggregation
2. **Asynchronous Execution**: Support for multiple worker types with future Kubernetes/Docker extensibility
3. **Event-Driven Automation**: React to system state changes with automated workflows
4. **Distributed Execution**: Scale task processing across multiple workers

The system must handle both internal infrastructure operations (branch merges, schema migrations) and user-defined workflows (transforms, generators) while maintaining observability and testability.

## Decision

We adopt **Prefect** as the asynchronous task orchestration framework. This pure-Python implementation enables seamless embedding within the application while simplifying testing and deployment.

### Core Architecture

The task system consists of:

- **Prefect Server**: Central orchestration hub for flow management
- **InfrahubWorkerAsync**: Custom async workers for task execution
- **WorkflowDefinition**: Declarative configurations registered in a catalogue
- **Flow Functions**: Async business logic decorated with `@flow`
- **Task Functions**: Discrete work units decorated with `@task`

### Declarative Workflow Catalogue

We adopt a declarative model where all workflows are centralized in a single catalogue. Every flow must be declared as a `WorkflowDefinition` in this catalogue, specifying its name, type, module path, and optional scheduling/concurrency configuration.

This centralized approach provides:

- **Single source of truth**: All available workflows discoverable in one location
- **Consistent configuration**: Uniform structure for workflow metadata and behavior
- **Automatic deployment**: Workflows are deployed to Prefect on system initialization
- **Extensibility**: Enterprise extensions can inject additional workflows via dependency injection

### Workflow Adapter Pattern

The system decouples execution from implementation:

- **WorkflowWorkerExecution**: Production mode submitting flows to Prefect servers
- **WorkflowLocalExecution**: Testing mode executing flows in-process without infrastructure

This pattern enables identical code across environments while avoiding Prefect dependencies in unit tests.

## Consequences

### Positive

- **Robust observability**: Centralized logging, state tracking, and execution history via Prefect UI/API
- **Scalable execution**: Distributed task processing across multiple workers
- **Pure-Python simplicity**: No external DSLs or configuration languages
- **Testability**: Local execution mode enables unit testing without infrastructure
- **Event integration**: Workflows can be triggered by Prefect Events (see ADR-0002)
- **Concurrency control**: Built-in support for concurrency limits and collision strategies
- **Cron scheduling**: Native support for scheduled workflow execution
- **Centralized catalogue**: Single location for all workflow definitions improves discoverability and maintainability
- **Import isolation**: Using string module paths in the catalogue avoids circular import issues that would occur if all workflows were imported in a single file

### Negative

- **Prefect dependency**: Tight coupling to Prefect infrastructure
- **Worker management**: Requires deploying and managing worker processes
- **Deployment complexity**: More complex than in-process task handling
- **Learning curve**: Developers must understand Prefect concepts (flows, tasks, deployments)

### Neutral

- **Tagging system**: Workflows receive metadata tags for organization and filtering
- **Dependency injection**: Services injected via `fast-depends` pattern

## Implementation Notes

Key implementation locations:

- Workflow definitions: [`backend/infrahub/workflows/catalogue.py`](../../../backend/infrahub/workflows/catalogue.py)
- Workflow models: [`backend/infrahub/workflows/models.py`](../../../backend/infrahub/workflows/models.py)
- Constants & types: [`backend/infrahub/workflows/constants.py`](../../../backend/infrahub/workflows/constants.py)
- Initialization: [`backend/infrahub/workflows/initialization.py`](../../../backend/infrahub/workflows/initialization.py)
- Task functions: Various `tasks.py` files across the codebase

See also:

- [Async Tasks Knowledge](../knowledge/backend/async-tasks.md) - How the async task system works
- [Creating Workflows Guide](../guides/backend/creating-async-tasks.md) - How to create a new workflow
- [ADR-0002: Events System](0002-events-system.md) - Event-driven automation triggers
