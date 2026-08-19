# Architecture Decision Records

We document significant architectural decisions using ADRs.

## Index

| Number | Title | Status | Date |
|--------|-------|--------|------|
| [0001](0001-context-nuggets-pattern.md) | Context Nuggets Pattern for Repository Organization | Accepted | 2024-12-24 |
| [0002](0002-events-system.md) | Prefect Events System | Accepted | 2024-12-26 |
| [0003](0003-asynchronous-tasks.md) | Asynchronous Tasks Execution with Prefect | Accepted | 2024-12-26 |
| [0004](0004-message-bus.md) | Message Bus Architecture | Accepted | 2024-12-26 |
| [0005](0005-account-group-origin-attribute.md) | `origin` Attribute for `CoreAccountGroup` Provenance Tracking | Accepted | 2025-05-13 |
| [0020](0020-analyzer-single-source-of-truth-for-query-targeting.md) | Analyzer is the single source of truth for query targeting | Accepted | 2026-08-14 |

## Creating a New ADR

1. Copy `template.md` to `NNNN-short-title.md`. Pick the next number that is free on **every** long-lived branch, not only the one you are on - `develop` and the `release-*` branches usually carry ADRs that have not reached `stable` yet, so the index here can have gaps.
2. Fill in all sections
3. Submit as PR for review
4. Update this index when merged

## ADR Status

- **Proposed**: Under discussion, not yet accepted
- **Accepted**: Decision made and implemented
- **Deprecated**: Superseded by a newer ADR or no longer applicable
- **Superseded**: Replaced by [link to newer ADR]
