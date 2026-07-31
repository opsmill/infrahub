Loading a schema now tells you about the fields it does not apply, instead of dropping them silently.

A read-only field — one Infrahub computes and returns itself, such as `inherited`, `used_by`, `hierarchy` or a derived `kind` — is still accepted, so a schema read back from Infrahub, edited and loaded again keeps working. It is now reported as a warning on the `POST /api/schema/load` and `POST /api/schema/check` response, one per distinct field, naming every kind and element that carried it. `infrahubctl schema load` and `infrahubctl schema check` print them, and `infrahubctl validate schema` reports them offline.

Any other unrecognized field is now **rejected** with a field-level error naming the path and the value, where earlier 1.x versions dropped it silently:

```text
nodes[0].attributes[0].optionl: Unknown field, it is not part of the schema (received: True)
```

This applies at every level of the payload and to every entry point — the API, `infrahubctl`, the Python SDK, and repository imports. Two shapes that previously loaded now fail: a misspelled field name, and attribute `parameters` belonging to a different attribute `kind` (for example `start_range` on a `Number` attribute), which configured nothing on the kind they were set on. Check a payload before submitting it with `infrahubctl validate schema <file>`, or with `infrahub_sdk.schema.validate_schema()` for the same verdict offline.

The SDK's `client.schema.validate()` reaches this same verdict and now raises `ValueError` rather than a pydantic `ValidationError`, returning the verdict — including the warnings — when the payload is accepted.
