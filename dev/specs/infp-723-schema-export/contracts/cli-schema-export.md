# Contract: `infrahubctl schema export` and the SDK Client

**Requirements**: FR-011, FR-019 to FR-022 | **Repository**:
[infrahub-sdk-python](https://github.com/opsmill/infrahub-sdk-python), branch `infrahub-develop`

## `infrahubctl schema export`

```text
infrahubctl schema export [--directory PATH] [--branch NAME] [--namespaces NS ...]
                          [--mode brief|full] [--single-file] [--debug]
```

| Option | Default | Effect |
|--------|---------|--------|
| `--directory` | `infrahub-schema-export-<timestamp>` | Unchanged. Created when missing. |
| `--branch` | default branch | Passed as `branch`. |
| `--namespaces` | all user namespaces | Passed as `namespaces`. |
| `--mode` | `brief` | New. Passed as `mode`. |
| `--single-file` | off | New. Writes the whole document to `<directory>/schema.yml` instead of one file per namespace. |

Output:

- Default: one `<namespace lower case>.yml` per namespace, as today. Each file has `version`,
  `infrahub_version`, then `generics` and `nodes` of that namespace, in the order of the response.
- `--single-file`: one `schema.yml` with the response as it is, converted to YAML.
- When the response has no generics and no nodes: prints "No user-defined schema found to export." and
  writes no file, as today.
- Against a server without the endpoint: prints "Schema export requires Infrahub X or later." with no
  traceback, and exits with code 1. X is 1.13.0, the release that ships the endpoint.

## SDK client

```python
async def export(
    self,
    branch: str | None = None,
    namespaces: list[str] | None = None,
    mode: Literal["brief", "full"] = "brief",
) -> InfrahubSchemaWrite: ...
```

Same signature on `InfrahubSchemaSync.export`. Returns the response body parsed into the generated
`infrahub_sdk.schema.generated.write::InfrahubSchemaWrite`; `model_dump(mode="json", exclude_unset=True)`
gives back the response. Raises
`VersionNotSupportedError` when the server answers 404 or 422 on `/api/schema/export`, and
`BranchNotFoundError` on 400. The type of `mode` stops the client from sending an invalid mode, so a 422 on
that URL means an older server.

## Removed public symbols

`infrahub_sdk.schema.SchemaExport`, `NamespaceExport`, `schema_to_export_dict`, the module
`infrahub_sdk.schema.export` and its `RESTRICTED_NAMESPACES`. The SDK changelog lists them in a `removed`
fragment.

## Schema validation

`infrahub_sdk.schema.validate::validate_schema`, used by `infrahubctl schema load` and `schema check`,
accepts `infrahub_version` at the root with no warning, through the regenerated
`infrahub_sdk.schema.generated.write::InfrahubSchemaWrite`. `infrahubctl schema format` keeps
`infrahub_version` right after `version`.
