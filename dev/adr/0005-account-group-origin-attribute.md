# 5. `origin` Attribute for `CoreAccountGroup` Provenance Tracking

**Status:** Accepted
**Date:** 2026-05-13
**Author:** @opsmill-team

## Context

The auto-create account groups feature (INFP-556) introduces a need to record, on every `CoreAccountGroup`, which identity provider — if any — triggered its creation. Administrators and compliance reviewers need to answer "what caused this group to exist?" from the group itself rather than only from the auto-creation event log.

The semantically correct place to record this provenance is **metadata about the group**, not data on the group. Infrahub already exposes per-attribute metadata (e.g., `source`, `owner`) that points at another node. Recording group-level provenance via the same mechanism would let any future provenance use case (not just account groups) plug into one platform feature.

Two prerequisites for the metadata-framework approach do not exist in the codebase today:

1. **No object-level `source` metadata property.** Today `source` exists only as a property on attributes, not on the object as a whole. Surfacing it at the object level requires a non-trivial platform change (schema, storage, GraphQL exposure, UI, permissions).
2. **No `CoreNode` representation of an identity provider.** OIDC, OAuth2 and LDAP providers are pure configuration (`SecuritySettings` entries). There is no node to point a `source` metadata reference at. Introducing one is itself a multi-week effort with its own data model and lifecycle questions.

INFP-556 ships in Infrahub 1.10. Blocking it on those two platform investments is not acceptable. We need a minimal stand-in that captures the same provenance signal for the only use case that is in flight today (auto-creation from an external IdP), without committing to a long-term shape that the platform cannot yet support.

## Decision

For 1.10, record provenance of auto-created account groups as a regular schema **attribute** on `CoreAccountGroup`, named `origin`, with the following shape:

- **Kind:** `Text` (free-form, no enum).
- **Optionality:** Optional / nullable.
- **Write semantics:** Read-only from every external write path. Only Infrahub's auto-creation flow may set the value.
- **UI visibility:** Declared with the schema property `display: extra` so the schema-driven UI hides it from the default group view but lets a user reveal it via the existing extra/advanced-attributes toggle. The GraphQL API exposes it unconditionally.
- **Value:** The configured name of the identity provider that triggered auto-creation.
- **Population scope:** Set **only** at auto-creation time. **Not** populated for groups created manually and **not** populated for groups seeded by the infrahub-server at startup. Existing groups are **not** backfilled on upgrade.

The long-term direction remains: replace `origin` with an object-level `source` metadata property that references a `CoreNode` representing the identity provider. When both prerequisites exist, the `origin` attribute is expected to be retired in favor of the metadata-framework approach.


## Alternatives Considered

### Object-level `source` metadata referencing a `CoreNode` identity provider (long-term target)

The conceptually correct shape: every node carries `source` metadata in the same uniform way attributes do today, pointing at a `CoreNode` that represents the identity provider. This is the eventual destination. It is rejected for 1.10 because both prerequisites (object-level `source` metadata; `CoreNode` for IdPs) are missing and either one is multi-week work in its own right.

### Provenance only in the auto-creation event log (no group-level attribute)

Cheaper still — just emit FR-015 and rely on log queries. Rejected because audit consumers reasonably expect to see provenance on the group object itself; forcing them to join against an event log to answer "what created this group?" was the gap the clarification work was trying to close.


## Implementation Notes

- Spec: [`specs/infp-556-auto-create-groups/spec.md`](../../specs/infp-556-auto-create-groups/spec.md), specifically FR-012, FR-013, FR-014, FR-021, and Session 2026-05-13 in Clarifications.
- Schema migration: definition-only (adds the attribute); does **not** run any data migration to populate values on existing rows.
- Read-only enforcement applies even when a user reveals the attribute via the `display: extra` toggle — the UI must still treat it as non-editable.
