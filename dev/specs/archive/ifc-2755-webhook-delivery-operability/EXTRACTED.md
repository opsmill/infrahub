# Extraction Record

**Extracted on**: 2026-07-31
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- `dev/adr/0013-webhook-delivery-on-prefect-run-primitives.md` (from research.md D1, D3)
- `dev/adr/0014-generic-per-task-recovery-actions.md` (from research.md D6, D7, D8, D9)
- `dev/adr/0015-uniform-bounded-webhook-retry.md` (from research.md D2)

## Knowledge Updated

- `dev/knowledge/backend/async-tasks.md` (Task typing): added "Task typing (polymorphic)"
  documenting `TaskNodeInterface`, `resolve_type`, and the `TASK_TYPES` discriminant.
- `dev/knowledge/backend/webhooks.md` (Failure handling): corrected the retry paragraph, which
  described a `transient` flag that no longer exists in the code, to the uniform bounded retry the
  feature landed.

Delivery capture, logging, redaction, the failure-class table, and the operability actions were
already documented in `webhooks.md` by the implementation.

## Guidelines Updated

- None.

## Archive

Spec directory moved to `specs/archive/ifc-2755-webhook-delivery-operability/` as a historical
record.
