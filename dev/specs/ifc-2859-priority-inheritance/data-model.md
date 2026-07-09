# Data Model: Priority Inheritance for Task Trees

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

No database entities are involved. The only model change is on an in-memory / serialized-payload Pydantic model.

## Changed Entities

### InfrahubContext (`backend/infrahub/context.py`) — existing, one field added

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `branch` | `BranchContext` | — | unchanged |
| `account` | `AccountSession` | — | unchanged |
| `priority` | `WorkflowPriority \| None` | `None` | **new** — the effective priority of the task tree this context travels through; `None` means "no priority signal" (tree roots before dispatch, pre-upgrade payloads) |

**Validation rules**:

- `priority` accepts only `WorkflowPriority` members (`high` / `medium` / `low`) or `None` — enforced by Pydantic against the typed enum (FR-001, Constitution III).
- Payloads serialized before this change (no `priority` key) MUST deserialize with `priority=None` — guaranteed by the field default.

**State transitions** (who writes the field):

1. Entry points (`InfrahubContext.init`) create contexts with `priority=None` — construction signature unchanged.
2. The dispatch adapter stamps the resolved effective priority into a **copy** (`model_copy(update=...)`) at every dispatch that carries an `InfrahubContext`; the caller's object is never mutated (FR-003).
3. Flows never write the field; they only forward the context they received.

**Boundary invariants**:

- `to_event_context()` → `EventContext` carries no priority (FR-005).
- `to_request_context()` → `RequestContext` carries no priority (FR-005).

## Consumed Entities (unchanged, from the foundation slice)

- **WorkflowPriority** (`backend/infrahub/workflows/constants.py`): tier vocabulary and tier-to-queue mapping — single source of truth.
- **WorkflowDefinition.default_priority** (`backend/infrahub/workflows/models.py`): the catalogue default, last link of the resolution chain.
- **Work queues** (`high` / `medium` / `low` on the `infrahub-worker` pool): routing targets; provisioning untouched.
