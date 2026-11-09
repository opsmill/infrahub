# Extraction Record

**Extracted on**: 2026-07-31
**Extracted by**: speckit.opsmill.extract

## ADRs Created

- None. The one decision this feature warrants (the `origin` provenance attribute on
  `CoreAccountGroup`) is already recorded in `dev/adr/0005-account-group-origin-attribute.md`.

## Knowledge Updated

- `dev/knowledge/backend/schema-definitions.md` (Read-only Attributes): documented the `read_only`
  attribute flag (with `allow_override=AllowOverrideType.NONE`) and how it gates GraphQL input
  generation and mutation, the reusable schema fact this feature exercised via
  `CoreAccountGroup.origin`.

The SSO group-resolution pipeline, auto-created-groups configuration, and the auto-create events are
already documented in `dev/knowledge/backend/authentication.md` and `dev/knowledge/backend/events.md`.

## Guidelines Updated

- None.

## Archive

Spec directory moved to `specs/archive/infp-556-auto-create-groups/` as a historical record.
