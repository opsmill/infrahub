# Contract — Schema Delta

## `CoreAccountGroup` (modified)

**Location**: `backend/infrahub/core/schema/definitions/core/permission.py:159–182`

### Attribute added

```python
SchemaAttribute(
    name="origin",
    kind=AttributeKind.Dropdown,
    optional=False,            # NOT nullable post-migration
    read_only=True,             # Read-only from every external write path (FR-021)
    description="Provenance of this group: which auth path created it, or 'manual' / 'system'.",
    choices=[
        DropdownChoice(name="oidc_provider1"),
        DropdownChoice(name="oidc_provider2"),
        DropdownChoice(name="oidc_google"),
        DropdownChoice(name="oauth2_provider1"),
        DropdownChoice(name="oauth2_provider2"),
        DropdownChoice(name="oauth2_google"),
        DropdownChoice(name="ldap"),
        DropdownChoice(name="manual"),
        DropdownChoice(name="system"),
    ],
)
```

> Field names (`read_only`, etc.) above are illustrative — implementation MUST use whatever fields the existing `SchemaAttribute` / `Dropdown` types in `permission.py` and adjacent definition files already expose for "system-managed" and "static enum" semantics. If no `read_only`-style flag exists today, enforcement falls to (a) the input-validation layer rejecting user-supplied values on create/update, and (b) the write layer always overriding `origin__value` from the server-determined origin per FR-021.

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

## Schema migration (new)

**File**: `backend/infrahub/core/migrations/graph/mNNN_set_account_group_origin.py`
**Template**: `m069_set_comment_thread_created_by_on_node.py`
**Trigger**: Runs as part of the 1.10 upgrade.

### Cypher

```cypher
MATCH (g:CoreAccountGroup)
WHERE g.origin__value IS NULL
SET g.origin__value = "manual"
```

### Validation step

```cypher
MATCH (g:CoreAccountGroup)
WHERE g.origin__value IS NULL
RETURN count(g) AS unset_count
```

The migration MUST assert `unset_count == 0` after the SET (SC-005 — no nulls).

### Notes

- Backfills every pre-existing `CoreAccountGroup` row with `origin = "manual"` (FR-014).
- Non-destructive (no row deletion, no attribute removal).
- Uses parameterized Cypher (Principle V); no string interpolation.
- Idempotent: re-running is a no-op because the `WHERE g.origin__value IS NULL` guard excludes already-backfilled rows.
