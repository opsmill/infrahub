`POST /api/schema/load` now validates every submitted node, generic, and extension against a user-facing *write* contract, and reports the fields it does not apply instead of ignoring them.

Constrained fields (for example an attribute `kind` or a relationship `cardinality`) set outside their allowed values, and out-of-range values, are rejected with a field-level error naming the field and the invalid value:

```text
nodes[0].relationships[0].cardinality: Input should be 'one' or 'many' (received: 'several')
```

Attribute `parameters` belonging to a different attribute `kind` are rejected too — for example `start_range` on a `Number` attribute, which earlier versions accepted and then discarded, so the setting silently had no effect.

Fields Infrahub computes and owns are accepted and reported as a warning, one per distinct field, naming every kind and element that carried it. These are `inherited`, `used_by`, `hierarchy`, a relationship's `hierarchical`, a node's derived `kind` and `hash`, and the bookkeeping a schema dumped from Infrahub carries on nested blocks such as `parameters`. The submitted value is ignored, so reading a schema back from Infrahub, editing it, and loading it again keeps working:

```text
'inherited' is a read-only field, the submitted value is ignored [InfraDevice.name, InfraDevice.interfaces]
```

`infrahubctl schema load` and `infrahubctl schema check` print these warnings; `infrahubctl validate schema` reports them offline. A field the contract does not recognize at all — a typo, or a field removed in a newer version — is rejected as before, now with the same field-level path.

`GET /api/schema` returns the same response body as before and still includes read-only fields such as `inherited` and `used_by`. Its OpenAPI component schemas are now named after the generated read models — `NodeSchemaRead`, `GenericSchemaRead`, `ProfileSchemaRead`, and `TemplateSchemaRead` in place of `APINodeSchema`, `APIGenericSchema`, `APIProfileSchema`, and `APITemplateSchema` — so a client generating types from `openapi.json` needs to update those type names.

The write contract is published as a committed model in the Python SDK (`infrahub_sdk.schema.generated.write`); the SDK `validate_schema()` helper reproduces the server verdict offline, including the warnings, so a payload can be checked before submission. `client.schema.validate()` reaches the same verdict and raises `ValueError` rather than a pydantic `ValidationError`.
