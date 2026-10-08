# Contract: `allocation_scope` in NumberPool attribute parameters (published schema, ADR 0010)

**Feature**: [spec.md](../spec.md) | **Data model**: [data-model.md](../data-model.md)

**Status**: published-contract change. One review shared with P1's `ranges` and P2's query-surface
changes; one SDK type regeneration.

## Declaration shapes accepted

```yaml
- name: vlan_id
  kind: NumberPool
  read_only: true
  parameters:
    start_range: 100
    end_range: 200
    allocation_scope: ["site"]            # one relationship

- name: vlan_id
  kind: NumberPool
  read_only: true
  parameters:
    start_range: 100
    end_range: 200
    allocation_scope: ["site", "role"]    # a relationship and an attribute
```

| Declaration | Outcome |
|---|---|
| `allocation_scope` absent or `[]` | unscoped pool, as today |
| entry naming an optional field, a many relationship, a related-node path, a list or JSON attribute, the attribute itself, or a duplicate | refused at schema load, naming the entry (validated on the branch being loaded) |
| entry not defined on the kind in that branch's schema | refused at schema load, naming the entry |
| a declared scope on a `unique: true` attribute | refused at schema load, naming the attribute |
| entry not declared on the generic the attribute is inherited from | refused at schema load, naming the generic |
| scope changed on the default branch | the schema-created pool's `allocation_scope` is updated on load; no data moves |
| scope changed on another branch | validated there; the pool follows when the branch merges |
| a field the declared scope names is renamed | refused at schema load, naming the field and the pool: remove the entry from the declaration, rename, then declare the scope with the new name (FR-032) |
| scoped field made optional, removed, or made cardinality many while a pool names it, or the pool's attribute made `unique: true` while the pool carries a scope | refused at schema load, naming the pool |

## Generated contract changes

| Artefact | Change |
|---|---|
| `tasks/backend.py::SdkSchemaGenerator.number_pool_parameters_fields` | hand-maintained field list gains the `List` field; the generated models below are not introspected from the Pydantic class |
| `NumberPoolParametersWrite` / `Read` (SDK, OpenAPI, frontend REST types) | `allocation_scope: list[str] \| None`, default absent |
| Write JSON schema (`schema/`) | the new optional array of strings |
| `docs/docs/snippets/attribute-kind-params.mdx`, `docs/docs/reference/schema/attribute.mdx` | unchanged: the snippet generator (`tasks/docs.py`) lists only parameters with `update: validate_constraint`, and `attribute.mdx` documents `parameters` as one row; the field is documented by hand in `docs/docs/schema/number-pool.mdx` |
| `backend/infrahub/core/schema/generated/attribute_schema.py` | unchanged (the parameters union already names `NumberPoolParameters`) |

## Schema-change validation

| Change | Constraint identifier | Checker |
|---|---|---|
| `allocation_scope` on the parameters | none (`update: ALLOWED`; #10917 shipped `NOT_SUPPORTED`, switched by IFC-3351); entry validity is a schema-load validation | — |
| a scoped attribute's `optional` | `attribute.optional.update` | `ScopedPoolDependencyChecker` (new), beside the existing optional checker |
| a scoped relationship's `optional` / `cardinality` | `relationship.optional.update`, `relationship.cardinality.update` | same |
| a scoped field removed | `node.attribute.remove`, `node.relationship.remove` (new constraint entries beside the existing migrations) | same |
| the pool's own attribute made `unique: true` while the pool carries a scope | `attribute.unique.update` | same, beside the existing uniqueness checker |
| a scoped attribute renamed | `attribute.name.update` (existing migration name, added to the validator map so the migration also yields a constraint) | `ScopedPoolDependencyChecker`, refusing naming the field and the pools (FR-032) |
| a scoped relationship renamed | `relationship.name.update` (new constraint: the relationship's `name` moves from `update: allowed` to `validate_constraint`) | same |
| a scoped number-pool attribute added to a populated kind | `node.attribute.add` | `NodeAttributeAddChecker`, size against the largest division |

## Ordering of the two repositories

1. PR on `opsmill/infrahub-sdk-python` (branch tracked by this Infrahub branch) with the regenerated
   SDK models.
2. Once merged, bump the `python_sdk` submodule pointer in the Infrahub PR.
