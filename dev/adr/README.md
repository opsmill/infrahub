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
| [0006](0006-frontend-entity-layers.md) | Frontend Entity Layers: `ui → domain → api` with API-owned Mappers | Accepted | 2026-07-03 |
| [0007](0007-adaptive-retry-after-under-load.md) | Adaptive `Retry-After` under Sustained Load | Accepted | 2026-07-24 |
| [0008](0008-client-declared-request-priority.md) | Client-declared Request Priority, Cooperatively Trusted | Accepted | 2026-07-26 |
| [0009](0009-per-worker-coordination-free-admission.md) | Per-worker, Coordination-free Admission Capacity | Accepted | 2026-07-26 |
| [0010](0010-generated-user-facing-schema-contract.md) | Generated User-Facing Schema Contract, Hosted in the SDK | Accepted | 2026-07-26 |
| [0011](0011-inline-local-computed-attributes.md) | Inline Evaluation of Local Jinja2 Computed Attributes During Update Mutations | Accepted | 2026-07-31 |
| [0012](0012-selective-post-merge-regeneration.md) | Selective Post-merge Regeneration Driven by the Captured Merge Diff | Accepted | 2026-07-31 |
| [0013](0013-webhook-delivery-on-prefect-run-primitives.md) | Webhook Deliveries as Retention-bounded Prefect-run Objects | Accepted | 2026-07-31 |
| [0014](0014-generic-per-task-recovery-actions.md) | Generic Per-task Recovery Actions with Polymorphic Task Typing | Accepted | 2026-07-31 |
| [0015](0015-uniform-bounded-webhook-retry.md) | Uniform Bounded Fixed-delay Auto-retry for Webhook Deliveries | Accepted | 2026-07-31 |

## Creating a New ADR

1. Copy `template.md` to `NNNN-short-title.md` (use next sequential number)
2. Fill in all sections
3. Submit as PR for review
4. Update this index when merged

## ADR Status

- **Proposed**: Under discussion, not yet accepted
- **Accepted**: Decision made and implemented
- **Deprecated**: Superseded by a newer ADR or no longer applicable
- **Superseded**: Replaced by [link to newer ADR]
