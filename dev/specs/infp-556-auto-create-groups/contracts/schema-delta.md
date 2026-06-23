# Contract — Schema Delta

## `CoreAccountGroup` (modified)

**Location**: `backend/infrahub/core/schema/definitions/core/permission.py:159–182`

### Attribute added

```python
SchemaAttribute(
    name="origin",
    kind="Text",                # Free-form string (FR-012, clarification 2026-05-13)
    optional=True,              # Nullable — only the auto-creation path writes a value
    read_only=True,             # Read-only from every external write path (FR-021)
    branch=BranchSupportType.AGNOSTIC,
    display="extra",            # display: extra — hidden from default UI view, revealable via extra/advanced-attributes toggle (FR-012, clarification 2026-05-13)
    description="Configured name of the identity provider that auto-created this group; unset for manually-created and platform-seeded groups.",
)
# NOTE: No `choices=[...]` block — origin is free-form Text holding the configured provider name (e.g.,
#       "AzureAD-corp", "OktaProd", "corp-ldap"). The enum literals from the earlier reconcile
#       (oidc_provider1, oidc_provider2, oidc_google, oauth2_provider1, oauth2_provider2, oauth2_google, ldap)
#       are fully superseded by clarification 2026-05-13.
```

> Field names (`read_only`, `optional`, `display`, etc.) above MUST be matched to whatever the existing `SchemaAttribute` type in `permission.py` and adjacent definition files actually exposes. If the schema framework uses a different keyword for the `display: extra` capability (e.g., `display_mode`, `ui_visibility`, `extras=...`), use that. The contract here is the semantics, not the literal Python keyword. If no `read_only` flag exists, enforcement falls to (a) the input-validation layer rejecting user-supplied values on create/update, and (b) the write layer always sourcing `origin__value` from the auth-flow context per FR-021. The `display: extra` property is an **existing** schema capability — no extension to the schema definition framework is required (this is the key difference from the previous reconcile, which assumed a UI-hidden flag did not exist).

### Generated artifacts to regenerate

After editing `permission.py`, run:

```bash
uv run invoke backend.generate
```

This regenerates:

- `backend/infrahub/core/schema/generated/`
- `backend/infrahub/core/protocols.py`

And (after running a local instance):

- `schema/schema.graphql`
- `schema/openapi.json`
- `frontend/app/src/shared/api/graphql/generated/` (via `pnpm codegen`)
- `frontend/app/src/shared/api/rest/types.generated.ts`

These regenerations are required per Constitution Principle I; never hand-edit the generated files.

## Schema migration

**No data-migration script is required** (FR-014, clarification 2026-05-13). Because `origin` is optional, the schema change is purely a schema definition update — pre-existing `CoreAccountGroup` rows post-upgrade are valid with their `origin` attribute unset. Adding the attribute follows the standard non-destructive schema additive path used by the existing schema runtime; no Cypher MATCH/SET pass is needed.

### Post-upgrade invariant

After upgrading to 1.10:

- Every pre-existing `CoreAccountGroup` row has its `origin` attribute unset (no value written).
- Every new `CoreAccountGroup` row created via admin-facing paths (UI/GraphQL/REST/schema load) likewise has `origin` unset (FR-013).
- Every new `CoreAccountGroup` row created via the auto-creation path has `origin` set to the **configured name** of the identity provider that authenticated the triggering login (free-form string from settings — FR-013).

The previous Cypher backfill (`SET g.origin__value = "manual"`) is intentionally not implemented — `manual` is no longer a valid `origin` value, and unset is a valid state.
