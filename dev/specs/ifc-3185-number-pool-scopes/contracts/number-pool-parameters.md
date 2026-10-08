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

`parameters.allocation_scope` is an optional list of element names of the kind that declares the attribute (or of the generic, when the attribute is inherited from a generic). Absent, `null` or empty means the pool the schema creates is unscoped.

## Resolution and validation at load

- Names are resolved against the schema of the default branch. On the default branch, the candidate schema being loaded is the reference.
- The rules of [pool-allocation-scope.md](pool-allocation-scope.md) apply unchanged. A refusal fails the schema load with a message of the form `<kind>.<attribute>: allocation_scope: <reason>`.
- A schema loaded on a branch whose declared scope names an element absent from the default branch's schema is refused with `<kind>.<attribute>: allocation_scope: "<entry>" does not exist on <kind> on branch <default branch>`.

## Effect on the pool the schema creates

- The pool is created with the resolved scope stored as `[{id, name}, ...]`, in the declared order.
- The declared scope cannot change afterwards: the parameter carries the `not_supported` update marker, so a schema load that changes or clears it for an attribute whose pool exists is refused by the schema update validation, with the attribute named.
- Ranges and bounds keep their existing behaviour.

## Generated artifacts to regenerate

- `backend/infrahub/core/schema/generated/` and `backend/infrahub/core/protocols.py` (`uv run invoke backend.generate`)
- `schema/schema.graphql` (`uv run invoke schema.generate-graphqlschema`) and `schema/openapi.json` (`uv run invoke schema.generate-jsonschema`)
- `frontend/app/src/shared/api/graphql/generated/` and `frontend/app/src/shared/api/rest/types.generated.ts` (`cd frontend/app && pnpm codegen`)
- `docs/docs/schema/number-pool.mdx` (`uv run invoke docs.generate`)
- The Python SDK schema models under `python_sdk/infrahub_sdk/schema/generated/` are generated in the SDK repository from these definitions; the SDK change ships as its own pull request before the submodule pointer moves.
