# Quickstart: Validate the Schema Export

**Feature**: [spec.md](spec.md) | **Contracts**: [REST](contracts/rest-schema-export.md),
[CLI](contracts/cli-schema-export.md)

## Automated checks

```bash
# Backend: in-memory round trip over models/ and the rule schemas, both modes, plus field coverage
uv run pytest backend/tests/unit/core/schema/export/

# Backend: endpoint parameters, access, errors
uv run pytest backend/tests/component/api/test_40_schema.py -k export

# Backend: load the response into an empty database (US1, US3, US4, FR-015a)
uv run pytest backend/tests/functional/api/test_schema_export.py

# SDK: client, CLI, validation of infrahub_version
cd python_sdk && uv run pytest tests/unit/sdk/test_schema_export.py tests/unit/ctl/ tests/unit/test_schema_offline_validation.py

# Generated files and docs are current
uv run invoke backend.generate schema.generate-jsonschema docs.validate
cd frontend/app && pnpm codegen:openapi && git diff --exit-code src/shared/api/rest/types.generated.ts
```

Expected: all pass, and `git status` shows no change after the generation commands.

## Manual check on two instances

Prerequisites: two Infrahub instances on the branch, A with data and B empty, and `infrahubctl` from the
SDK branch. `INFRAHUB_ADDRESS` points at the instance each command targets.

1. On A, load `models/base/` and one example: `infrahubctl schema load models/base models/examples/security`.
2. Export from A: `infrahubctl schema export --directory /tmp/export`. Expect one file per namespace, each
   starting with `version: "1.0"` and `infrahub_version`.
3. Load into B: `infrahubctl schema load /tmp/export`. Expect success with no warning.
4. Export from B into `/tmp/export-b` and run `diff -r /tmp/export /tmp/export-b`. Expect no difference
   other than `infrahub_version` when A and B run different releases (SC-002).
5. `infrahubctl schema export --single-file --mode full --directory /tmp/full` on A. Expect one
   `schema.yml` with `label` and `order_weight` on every attribute.
6. `curl "$INFRAHUB_ADDRESS/api/schema/export?mode=other"`. Expect HTTP 422.
7. Point `INFRAHUB_ADDRESS` at an instance on a release without the endpoint and run step 2. Expect
   "Schema export requires Infrahub X or later." and no traceback.
