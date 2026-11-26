# Contract: `infrahubctl schema export`

Option names other than the existing ones are working names.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `--directory PATH` | `infrahub-schema-export-<timestamp>` | Directory the files are written to. Unchanged. |
| `--branch NAME` | client default | Passed to the endpoint as `branch`. Unchanged. |
| `--namespaces NAME` (repeatable) | all user namespaces | Passed to the endpoint as `namespaces`. Unchanged. |
| `--mode [BRIEF\|FULL]` | `BRIEF` | Passed to the endpoint as `mode` (FR-013). |
| `--single-file` | off | Write one file for all namespaces (FR-014, D9). |

## Output files

- Default: one file per namespace, `<namespace in lower case>.yml`, as today. The CLI splits the endpoint's document by the `namespace` of each node and generic, with `split_by_namespace` (see SDK methods). Each file has `version` and `infrahub_version`, then `generics`, then `nodes`.
- `--single-file`: one file, `schema.yml`, holding the endpoint's document.

The files are YAML, written with `sort_keys=False` as today, from `model_dump(exclude_unset=True)`, so a file holds only the keys of the endpoint's response.

## Console output

| Case | Output |
| --- | --- |
| Success | One line per file written, then the directory. Unchanged. |
| No user-defined schema | `No user-defined schema found to export.` Unchanged. |
| Server without the endpoint | Error that names the first release with the endpoint, exit code 1 (FR-016, research R7). |
| Any other error response | The error as the server returned it, with no mention of a release, exit code 1 (research R7). |

## SDK methods

`InfrahubSchema.export` and `InfrahubSchemaSync.export` keep their names and take `mode`. They call the endpoint and return its document unchanged, as a `SchemaExportDocument` (working name): a subclass of the SDK `InfrahubSchemaWrite` with `infrahub_version: str` required, and `nodes` and `generics` typed as the write models. `--single-file` writes this document.

A function `split_by_namespace(document)` (working name) in `infrahub_sdk/schema/export.py` returns one `SchemaExportDocument` per namespace, keyed by namespace. Each holds the same `version` and `infrahub_version` and the nodes and generics of that namespace, in the order of the endpoint's document. The CLI uses it for the default layout.

The client-side export rules (`infrahub_sdk/schema/export.py::schema_to_export_dict` and the constants it uses) are removed (D8). `schema_to_export_dict`, `RESTRICTED_NAMESPACES`, `NamespaceExport` and `SchemaExport` are removed from the public `infrahub_sdk.schema` module with no deprecation period, and a `removed` changelog fragment names each one (decided on 2026-11-23). The return type of `export` changes from `SchemaExport` to `SchemaExportDocument` (decided on 2026-11-25), and the `changed` changelog fragment states it. The SDK maintainers agree to this public API change before the SDK pull request merges (SDK `AGENTS.md`, Ask first).
