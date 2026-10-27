# Contract: Schema Export (REST)

**Requirements**: FR-001 to FR-018 | **Status**: approved by Damien Garros on 2026-10-27 ("Ask First" API
change, root `AGENTS.md`). The design document chose a REST endpoint (D11).

## `GET /api/schema/export`

Returns the user-defined schema of a branch as one schema file document. It is in `schema/openapi.json`,
with a summary and a description, in the `schema` tag next to `GET /api/schema`.

### Query parameters

| Name | Type | Default | Rule |
|------|------|---------|------|
| `branch` | string | default branch | Same dependency as `GET /api/schema`. An unknown branch returns HTTP 400 (`BranchNotFoundError`). |
| `namespaces` | list of strings | all user namespaces | Exact match. Restricted namespaces in the list are ignored, because they contain no user-defined schema. A namespace that references another one outside the list is exported alone, with no warning (FR-017). |
| `mode` | `brief` or `full` | `brief` | Any other value returns HTTP 422. |

### Access

Same as `GET /api/schema`: an authenticated account, or an anonymous request when
`allow_anonymous_access` is on. No permission check (FR-018, D10).

### Response 200

`application/json`, an `InfrahubSchemaWrite` document (see [data-model.md](../data-model.md)):

```json
{
  "version": "1.0",
  "infrahub_version": "1.24.0",
  "generics": [
    {
      "name": "Interface",
      "namespace": "Network",
      "icon": "mdi:ethernet",
      "human_friendly_id": ["device__name__value", "name__value"],
      "display_label": "{{ device__name__value }} {{ name__value }}",
      "attributes": [{"name": "name", "kind": "Text"}],
      "relationships": [{"name": "device", "peer": "NetworkDevice", "cardinality": "one", "optional": false, "kind": "Attribute"}]
    }
  ],
  "nodes": [
    {"name": "Device", "namespace": "Network", "attributes": [{"name": "name", "kind": "Text", "unique": true}]}
  ]
}
```

The `infrahub_version` value above is an example.

- `generics` and `nodes` are always present, and empty when the selection has no user-defined schema. This
  answers the spec's assumption on an empty export: the document still loads (it changes nothing).
- The body loads as it is as one entry of the `schemas` list of `POST /api/schema/load`.
- Calling the endpoint twice on an unchanged schema returns the same body.

### Errors

| Status | When |
|--------|------|
| 400 | Unknown branch. |
| 401 | No account and anonymous access off. |
| 422 | Invalid `mode`. |
| 500 | The document fails validation against the write model. This is a defect in the export rules, never a user error; the message does not include the schema. |

## Change to `POST /api/schema/load` and `POST /api/schema/check`

The root of each entry of `schemas` accepts `infrahub_version` (string, optional) and ignores it. It gives
no warning (FR-011). A server on an earlier release rejects it as an unknown field.
