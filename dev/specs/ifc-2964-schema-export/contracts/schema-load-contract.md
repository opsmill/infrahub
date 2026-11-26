# Contract: the `infrahub_version` field, accepted and ignored by the schema load

Applies to `POST /api/schema/load`, `POST /api/schema/check` and the offline validation that `infrahubctl schema load` and `infrahubctl schema check` run (`infrahub_sdk/schema/validate.py::validate_schema`).

## Fields

| Field | Type | Effect on load |
| --- | --- | --- |
| `infrahub_version` | `str`, optional | None. Not passed to schema processing, merging or hashing. |

`version` stays required and keeps its meaning (the schema file format version).

## Where each change lives

| Change | Location |
| --- | --- |
| The field on the generated write root `InfrahubSchemaWrite` | `tasks/backend.py::_sdk_root`, regenerated into `python_sdk/infrahub_sdk/schema/generated/write.py` with `uv run invoke backend.generate` |
| Field excluded when the internal `SchemaRoot` is built | `backend/infrahub/api/schema.py::SchemaLoadAPI.build_internal_schema` |
| Schema-file JSON schema regenerated | built from `SchemaLoadAPI` by `backend/infrahub/cli/dev.py` |

`SchemaRoot` keeps `extra="forbid"` and gains no field.

## Compatibility

| Loader | Result for a document with `infrahub_version` |
| --- | --- |
| A release with this change | Accepted, field ignored. |
| An earlier release | Rejected: the offline validation and the server report the unknown root field as an error (D7). |
