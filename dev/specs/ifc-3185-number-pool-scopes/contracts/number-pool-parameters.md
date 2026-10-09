# Contract: `allocation_scope` in the parameters of the number-pool attribute kind

## Declaration

```yaml
nodes:
  - name: Device
    namespace: Infra
    attributes:
      - name: vlan_id
        kind: NumberPool
        read_only: true
        parameters:
          start_range: 1
          end_range: 100
          allocation_scope: ["site"]
    relationships:
      - name: site
        peer: LocationSite
        cardinality: one
        optional: false
```

`parameters.allocation_scope` exists today in `backend/infrahub/core/schema/attribute_parameters.py::NumberPoolParameters` as an optional list of element names of the kind that declares the attribute (or of the generic, when the attribute is inherited from a generic). Absent, `null` or empty means the pool the schema creates is unscoped. Its update marker changes from `not_supported` to `validate_constraint`.

## Resolution and validation at load

- Names are resolved against the schema of the default branch. On the default branch, the candidate schema being loaded is the reference.
- The rules of [pool-allocation-scope.md](pool-allocation-scope.md) apply unchanged. A refusal fails the schema load with a message of the form `<kind>.<attribute>: allocation_scope: <reason>`.
- A schema loaded on a branch whose declared scope names an element absent from the default branch's schema is refused with the messages of [pool-allocation-scope.md](pool-allocation-scope.md), each prefixed with `<kind>.<attribute>:` and a space:
  - `<kind>.<attribute>: allocation_scope: "<entry>" is not an attribute or a relationship of <kind> on branch <default branch>`
  - `<kind>.<attribute>: allocation_scope: "<entry>" is not declared on the generic <kind>`, when the attribute is declared on a generic and only an implementing node declares the entry
  - `<kind>.<attribute>: allocation_scope: <kind> is not defined on branch <default branch>`, when the default branch's schema does not define the kind

## Comparison with the pool the schema already created

On every load, for an attribute whose pool exists, each declared name is resolved to an element id on the candidate schema and the list of ids is compared to the pool's stored scope. With a pool storing `[{id: X, name: "site"}]`:

| Schema change | Declaration | Outcome |
|---------------|-------------|---------|
| None | `["site"]` | Accepted, nothing changes |
| `site` renamed to `location` | `["site"]` | Refused: `<kind>.<attribute>: allocation_scope: "site" was renamed to "location"; update allocation_scope to the new name` |
| `site` renamed to `location` | `["location"]` | Accepted: same ids; the stored name becomes `location` in the same load |
| None | `["role"]` | Refused: `<kind>.<attribute>: allocation_scope can't be changed after the pool is created` |
| None | `[]` or absent | Refused with the same message |
| None | `["site", "role"]` | Refused with the same message |

The comparison runs in the schema constraint checker on the schema load and schema check endpoints, on every branch. A rename is a rename only when the loaded schema carries the element's id with its new name; without the id, the old element is removed and a new one added, which the removal rule refuses.

## Effect on the pool the schema creates

- The pool is created with the resolved scope stored as `[{id, name}, ...]`, in the declared order.
- Ranges and bounds keep their existing behaviour.

## Generated artifacts to regenerate

- `backend/infrahub/core/schema/generated/` and `backend/infrahub/core/protocols.py` (`uv run invoke backend.generate`): the update marker of the parameter and the update support of the relationship `name` field change
- `schema/schema.graphql` (`uv run invoke schema.generate-graphqlschema`) and `schema/openapi.json` (`uv run invoke schema.generate-jsonschema`): descriptions
- `frontend/app/src/shared/api/graphql/generated/` and `frontend/app/src/shared/api/rest/types.generated.ts` (`cd frontend/app && pnpm codegen`)
- `docs/docs/schema/number-pool.mdx` (`uv run invoke docs.generate`)
- The Python SDK schema models under `python_sdk/infrahub_sdk/schema/generated/` already carry `allocation_scope` as a list of strings (infrahub-sdk-python #1402); the type does not change here, so no new SDK generation is needed, only the submodule pointer.
