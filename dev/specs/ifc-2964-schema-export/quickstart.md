# Quickstart: validate the schema export

Scenarios that show the feature works end to end. The rules are in [data-model.md](data-model.md), the interfaces in [contracts/](contracts/).

## Prerequisites

- Dependencies installed: `uv sync --all-groups`
- Docker running (functional tests start Neo4j through testcontainers)
- The `python_sdk` submodule at the SDK commit that has the CLI change

## Automated checks

```bash
uv run pytest backend/tests/unit/schema/export/
uv run pytest backend/tests/functional/api/test_schema_export.py
cd python_sdk && uv run pytest tests/unit/sdk/test_schema_export.py tests/unit/ctl/
```

Expected:

- Unit tests: every variation schema round-trips in `BRIEF` and `FULL` mode, the field coverage test passes, and an export whose processing fails returns the `FULL` document without raising.
- Functional tests: `models/base/` and the combined variation schema load into an empty instance with no errors and no warnings other than `display_labels` and `default_filter` deprecations, and a second export is identical apart from `infrahub_version`.
- SDK tests: the CLI writes one file per namespace, or one file with `--single-file`, reports the error for a server without the endpoint, and reports any other error response as the server returned it.

## Manual scenario 1: copy the schema to an empty instance (User Story 1)

1. Start an instance: `uv run invoke dev.start`
2. Load the base schema: `infrahubctl schema load models/base`
3. Export: `infrahubctl schema export --directory /tmp/export-brief`
4. Check the files: no `id`, no `inherited` attributes, no `member_of_groups`, `profiles` or `object_template` relationships, no `Core` namespace file, no `IpamNamespace` node.
5. Destroy and start an empty instance: `uv run invoke dev.destroy dev.start`
6. Load the export: `infrahubctl schema load /tmp/export-brief`

Expected: the load succeeds with no warnings other than `display_labels` and `default_filter` deprecations. `infrahubctl schema export --directory /tmp/export-again` gives files identical to the first export apart from `infrahub_version`.

## Manual scenario 2: `FULL` mode (User Story 2)

1. `infrahubctl schema export --mode FULL --directory /tmp/export-full`
2. Compare with `/tmp/export-brief`.

Expected: the `FULL` files also hold `label`, `order_weight` and `branch` values that the `BRIEF` files leave out.

## Manual scenario 3: one namespace (User Story 3)

```bash
curl -s -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" \
  "http://localhost:8000/api/schema/export?namespaces=Location" | jq '[.nodes[].namespace, .generics[].namespace] | unique'
infrahubctl schema export --namespaces Location --directory /tmp/export-location
```

Expected: the namespace list is `["Location"]`. The relationships from `Location` kinds to `InfraDevice` and `InfraVLAN` are written as in a full export. The CLI writes one file, `location.yml`.

## Manual scenario 4: single file and older server (User Story 4)

1. `infrahubctl schema export --single-file --directory /tmp/export-one`: one `schema.yml` with every namespace.
2. Point `infrahubctl` at an instance on a release without the endpoint and run `infrahubctl schema export`.

Expected: the second command fails with a message that names the first release with the endpoint.
