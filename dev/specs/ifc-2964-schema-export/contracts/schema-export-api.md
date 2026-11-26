# Contract: `GET /api/schema/export`

Parameter names and mode values are working names (spec Assumptions).

## Request

| Parameter | In | Type | Default | Meaning |
| --- | --- | --- | --- | --- |
| `branch` | query | string | default branch | Branch whose schema is exported. Same handling as `GET /api/schema` (`get_branch_dep`). |
| `namespaces` | query, repeatable | list of strings | all user namespaces | Namespaces to export. A restricted namespace in the list is ignored, because the export never holds restricted namespaces (FR-003). `Ipam` returns the user kinds in `Ipam` and not `IpamNamespace`, which Infrahub defines (research R2). |
| `mode` | query | `BRIEF` or `FULL` | `BRIEF` | How much the export includes ([data-model.md](../data-model.md#schemaexportmode)). |

Authentication: any account that can call `GET /api/schema` (D10). No global permission is checked.

## Response 200

`application/json`, a `SchemaExportDocument` ([data-model.md](../data-model.md#schemaexportdocument)), serialized with `exclude_unset=True`. A field the export leaves out is absent from the body, not written with its default value ([data-model.md](../data-model.md#serialization)).

```json
{
  "version": "1.0",
  "infrahub_version": "1.13.0",
  "generics": [
    {
      "name": "Interface",
      "namespace": "Network",
      "human_friendly_id": ["device__name__value", "name__value"],
      "attributes": [{"name": "name", "kind": "Text"}],
      "relationships": [
        {"name": "device", "peer": "NetworkDevice", "cardinality": "one", "optional": false, "kind": "Attribute"}
      ]
    }
  ],
  "nodes": [
    {
      "name": "PhysicalInterface",
      "namespace": "Network",
      "inherit_from": ["NetworkInterface"],
      "human_friendly_id": ["device__name__value", "name__value"],
      "uniqueness_constraints": [["device", "name__value"]],
      "attributes": [{"name": "speed", "kind": "Number"}]
    }
  ]
}
```

With `namespaces=Network`, the document holds only `Network` kinds. A relationship to `LocationSite` is written as without the filter, and `LocationSite` itself is not in the document.

The document loads as one entry of `schemas` in `POST /api/schema/load` with no change.

## Errors

| Status | When | Body |
| --- | --- | --- |
| Same as `GET /api/schema` | Branch not found, or no valid session or token | Same as `GET /api/schema`. |
| 422 | `mode` is not a known value | FastAPI request validation error. |

The export has no other error response. When processing a `BRIEF` candidate fails validation, the response is the `FULL` document with status 200, and the server logs a warning (research R3).

An empty schema (no user-defined nodes or generics) returns 200 with `nodes` and `generics` empty. This includes an empty instance, whose `IpamNamespace` is not exported.

A server without the endpoint answers this URL with 422 and the message `Unable to find the schema 'export' in the registry`, because the request reaches `GET /api/schema/{schema_kind}`. The SDK reads only that response as "endpoint missing" (research R7).

## Route order

The route is declared before `GET /api/schema/{schema_kind}` in `backend/infrahub/api/schema.py` (research R7).

## Generated artifacts

- `schema/openapi.json`: `uv run invoke schema.generate-jsonschema`
- `frontend/app/src/shared/api/rest/types.generated.ts`: `cd frontend/app && pnpm codegen`
