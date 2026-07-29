# Developer Documentation

Internal documentation for contributors. For user-facing docs, see `/docs/`.

## Quick Navigation

| I want to... | Go to |
|--------------|-------|
| Understand the architecture | `knowledge/` |
| Follow coding standards | `guidelines/` |
| Learn why we made a decision | `adr/` |
| Complete a specific task | `guides/` |
| See what's being built | `specs/` |
| Explore rough ideas | `explorations/` |
| Use agent commands | `../.agents/commands/` |

## Directory Guide

- **explorations/**: Rough ideas, spikes, "what if" thinking. Not approved.
- **specs/**: Approved designs. Living during development, then archived.
- **guidelines/**: Prescriptive rules. How code should be written.
  - `backend/` - Python backend standards
  - `frontend/` - TypeScript/React frontend standards
- **knowledge/**: Descriptive reference. How the system works.
  - `backend/` - Backend architecture and patterns
  - `frontend/` - Frontend architecture and patterns
- **guides/**: Step-by-step procedures for specific tasks.
  - `backend/` - Backend-specific guides (events, tasks, messages)
  - `docs/` - Documentation-specific guides
  - `frontend/` - Frontend-specific guides
- **adr/**: Architecture Decision Records. Why we chose what we chose.
- **prompts/**: Prompt templates for common thinking tasks.

Agent commands and skills now live under [`../.agents/`](../.agents/) (the canonical
source of truth): `../.agents/commands/` and `../.agents/skills/`.

## Document Lifecycle

```text
explorations/ → specs/ → knowledge/ or guidelines/
   (rough)     (approved)      (stable)
```

Mark deprecated docs clearly. Don't delete—update with pointers to replacements.

## Current Guidelines

- **Repository Organization**: [guidelines/repository-organization.md](guidelines/repository-organization.md) - How to organize content in dev/
- **Python Backend**: [guidelines/backend/python.md](guidelines/backend/python.md)
- **TypeScript Frontend**: [guidelines/frontend/typescript.md](guidelines/frontend/typescript.md)
- **Git Workflow**: [guidelines/git-workflow.md](guidelines/git-workflow.md)
- **Markdown Formatting**: [guidelines/markdown.md](guidelines/markdown.md)
- **Writing Documentation**: [guidelines/documentation.md](guidelines/documentation.md) - How to write user-facing documentation

## Current Knowledge

Backend architecture documentation in [knowledge/backend/](knowledge/backend/):

- [architecture.md](knowledge/backend/architecture.md) - Backend architecture overview
- [testing.md](knowledge/backend/testing.md) - Testing infrastructure and patterns
- [events.md](knowledge/backend/events.md) - Events system
- [async-tasks.md](knowledge/backend/async-tasks.md) - Asynchronous tasks (Prefect)
- [message-bus.md](knowledge/backend/message-bus.md) - Message bus system
- [api-backpressure.md](knowledge/backend/api-backpressure.md) - Priority-aware load shedding and the database-stress signal
- [telemetry.md](knowledge/backend/telemetry.md) - Anonymous usage telemetry (categories, windowing, retention, degradation)

Frontend architecture documentation in [knowledge/frontend/](knowledge/frontend/):

- [architecture.md](knowledge/frontend/architecture.md) - Frontend architecture overview
- [entities-structure.md](knowledge/frontend/entities-structure.md) - Entity layers (`ui → domain → api`)
- [request-priority.md](knowledge/frontend/request-priority.md) - The `X-Priority` header the frontend emits

## Current ADRs

Architecture Decision Records in [adr/](adr/):

- [0001-context-nuggets-pattern.md](adr/0001-context-nuggets-pattern.md) - Context nuggets pattern
- [0002-events-system.md](adr/0002-events-system.md) - Events system
- [0003-asynchronous-tasks.md](adr/0003-asynchronous-tasks.md) - Asynchronous tasks
- [0004-message-bus.md](adr/0004-message-bus.md) - Message bus
- [0005-account-group-origin-attribute.md](adr/0005-account-group-origin-attribute.md) - `origin` attribute for `CoreAccountGroup` provenance
- [0006-frontend-entity-layers.md](adr/0006-frontend-entity-layers.md) - Frontend entity layers: `ui → domain → api` with api-owned mappers
- [0007-adaptive-retry-after-under-load.md](adr/0007-adaptive-retry-after-under-load.md) - Adaptive `Retry-After` under sustained load
- [0008-client-declared-request-priority.md](adr/0008-client-declared-request-priority.md) - Client-declared request priority, cooperatively trusted
- [0009-per-worker-coordination-free-admission.md](adr/0009-per-worker-coordination-free-admission.md) - Per-worker, coordination-free admission capacity
- [0010-generated-user-facing-schema-contract.md](adr/0010-generated-user-facing-schema-contract.md) - Generated user-facing schema contract, hosted in the SDK

## Current Guides

Backend guides in [guides/backend/](guides/backend/):

- [creating-events.md](guides/backend/creating-events.md) - How to create new events
- [creating-async-tasks.md](guides/backend/creating-async-tasks.md) - How to create async tasks
- [creating-messages.md](guides/backend/creating-messages.md) - How to create message bus messages

## Current Commands

Available agent commands in [../.agents/commands/](../.agents/commands/):

- [_shared.md](../.agents/commands/_shared.md) - Shared instructions for all flows
- [new-component.md](../.agents/commands/new-component.md) - React component creation flow
- [guided-task.md](../.agents/commands/guided-task.md) - General task flow
- [add-docs.md](../.agents/commands/add-docs.md) - Documentation flow
- [bug-analyze.md](../.agents/commands/bug-analyze.md) - Root cause analysis (`/bug-analyze <issue>`)
- [bug-tdd.md](../.agents/commands/bug-tdd.md) - Failing test from analysis (`/bug-tdd <issue>`)
- [bug-fix.md](../.agents/commands/bug-fix.md) - Fix implementation (`/bug-fix <issue>`)
- [fix-github-issue.md](../.agents/commands/fix-github-issue.md) - GitHub issue fixing
- [fix-mypy-module.md](../.agents/commands/fix-mypy-module.md) - Mypy type fixes
- [fix-ruff-rule.md](../.agents/commands/fix-ruff-rule.md) - Ruff linting fixes
