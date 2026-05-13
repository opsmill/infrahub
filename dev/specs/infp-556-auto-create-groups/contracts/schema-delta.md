# Contract — Schema Delta

## `CoreAccountGroup` (modified)

**Location**: `backend/infrahub/core/schema/definitions/core/permission.py:159–182`

### Attribute added

```python
SchemaAttribute(
    name="origin",
    kind=AttributeKind.Dropdown,
    optional=True,              # Nullable — only the auto-creation path writes a value (FR-012, clarification 2026-05-13)
    read_only=True,             # Read-only from every external write path (FR-021)
    branch=BranchSupportType.AGNOSTIC,
    # UI-hidden — schema-driven UI MUST NOT render `origin` on default CoreAccountGroup views (FR-012, clarification 2026-05-13).
    # Use whichever existing "hidden" / "internal" attribute flag the schema definition framework already exposes
    # (e.g., `inherited=False, branch=AGNOSTIC, order_weight=...` plus the project's UI-hidden flag — confirm against
    # how other system-managed attributes (e.g., `member_of_groups` internal fields) suppress UI rendering today).
    description="Auth path that auto-created this group; unset for manually-created and platform-seeded groups.",
    choices=[
        DropdownChoice(name="oidc_provider1"),
        DropdownChoice(name="oidc_provider2"),
        DropdownChoice(name="oidc_google"),
        DropdownChoice(name="oauth2_provider1"),
        DropdownChoice(name="oauth2_provider2"),
        DropdownChoice(name="oauth2_google"),
        DropdownChoice(name="ldap"),
        # NOTE: `manual` and `system` literals were dropped per clarification 2026-05-13.
        # Those creation paths leave `origin` unset instead of writing a literal.
    ],
)
```

> Field names (`read_only`, `optional`, the UI-hidden flag, etc.) above are illustrative — implementation MUST use whatever fields the existing `SchemaAttribute` / `Dropdown` types in `permission.py` and adjacent definition files already expose for "system-managed", "optional/nullable", "UI-hidden", and "static enum" semantics. If no `read_only`-style flag exists today, enforcement falls to (a) the input-validation layer rejecting user-supplied values on create/update, and (b) the write layer always overriding `origin__value` from the server-determined origin per FR-021. If no native UI-hidden flag exists, the implementation MUST add one (or extend the schema definition framework) — surfacing `origin` in the schema-driven UI is explicitly out of scope (clarification 2026-05-13).

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
- Every new `CoreAccountGroup` row created via the auto-creation path has `origin` set to the corresponding enum literal (FR-013).

The previous Cypher backfill (`SET g.origin__value = "manual"`) is intentionally not implemented — the `manual` enum value no longer exists in the schema, and unset is a valid state.
