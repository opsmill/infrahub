# Code Generation

> Part of: `dev/knowledge/backend/` | Related: [Schema Definitions](schema-definitions.md)

Infrahub uses a multi-stage code generation pipeline. All stages run offline — no running Infrahub instance is needed.

## Generation Pipeline

```text
Schema definitions (Python)
  backend/infrahub/core/schema/definitions/
       │
       ▼
  uv run invoke backend.generate          ← offline, no instance needed
       │
       ├──► backend/infrahub/core/schema/generated/   (Pydantic models)
       ├──► backend/infrahub/core/protocols.py         (Protocol types)
       ├──► backend/tests/protocols.py                 (Test protocols)
       ├──► python_sdk/infrahub_sdk/protocols.py       (SDK protocols)
       └──► python_sdk/infrahub_sdk/schema/generated/  (user-facing write/read models + enums)

       │
       ▼
  uv run invoke schema.generate-graphqlschema  ← offline, no instance needed
       │
       ├──► schema/schema.graphql
       └──► schema/openapi.json

       │
       ▼
  cd frontend/app && npm run codegen      ← offline, reads local files
       │
       ├──► frontend/app/src/shared/api/graphql/generated/types.ts
       └──► frontend/app/src/shared/api/rest/types.generated.ts
```

## When to Regenerate

| Change | Command |
|--------|---------|
| Added/modified schema definitions (attributes, relationships), or changed a field's `visibility` | `uv run invoke backend.generate`, then commit the regenerated files in the `python_sdk` submodule and bump its pointer |
| Changed GraphQL schema structure (new nodes, custom queries/mutations — **even backend-only PRs**) | `uv run invoke schema.generate-graphqlschema`, then `cd frontend/app && pnpm codegen:graphql` and commit `src/shared/api/graphql/generated/graphql-env.d.ts` + `graphql-cache.d.ts`. CI's `frontend-validate-graphql-types` job fails when these gql.tada files are stale. |
| New GraphQL queries/mutations in frontend | `pnpm codegen:graphql` (gql.tada types) and/or `pnpm codegen` (graphql-codegen `types.ts`) |
| New FastAPI route, changed request/response model, or added field on a response model | `uv run invoke schema.generate-jsonschema` (regenerates `schema/openapi.json`), then `cd frontend/app && pnpm codegen:openapi` to regenerate `src/shared/api/rest/types.generated.ts`. Note `pnpm codegen` alone only regenerates GraphQL types — it does **not** touch the REST types. |
| Changed event classes, schema docstrings, CLI commands, or config | `uv run invoke docs.generate` |

Changes that do **not** require regeneration:

- Modifying Python business logic
- Changing frontend components

## Validation

```bash
uv run invoke backend.validate-generated       # protocols + generated models
uv run invoke schema.validate-graphqlschema    # schema/schema.graphql
uv run invoke schema.validate-jsonschema       # schema/openapi.json
uv run invoke docs.validate                     # generated reference docs
```

Each validation task regenerates the files then checks for uncommitted diffs via `git diff --exit-code`. If validation fails, the correct file is already written to disk — just stage and commit it.

`backend.validate-generated` checks:

- `backend/infrahub/core/schema/generated/`
- `backend/infrahub/core/protocols.py`
- `backend/tests/protocols.py`
- `backend/infrahub/generators/graphql_queries/` and `backend/infrahub/computed_attribute/graphql_queries/`
- `python_sdk/infrahub_sdk/schema/generated/` and `python_sdk/infrahub_sdk/protocols.py`

The last two live in the `python_sdk` Git submodule. A `git diff` run from the superproject only
sees the submodule pointer, not the files inside it, so those two checks run as
`git -C python_sdk diff --exit-code`. A stale generated file in the submodule therefore fails the
same task — but committing the fix means a commit inside the submodule plus a pointer bump in the
superproject.

CI runs these checks to ensure generated files are committed.

## Documentation Generation

Reference documentation under `docs/docs/reference/` (and `docs/docs/reference/configuration.mdx`) is rendered from the backend source, not written by hand:

| Source | Output |
|--------|--------|
| CLI commands | `docs/docs/reference/infrahub-cli/` |
| Schema node/attribute/relationship/generic | `docs/docs/reference/schema/` |
| Repository config (`.infrahub.yml`) | `docs/docs/reference/dotinfrahub.mdx` |
| Message-bus events | `docs/docs/reference/message-bus-events.mdx` |
| Infrahub events (e.g. an event class and its fields) | `docs/docs/reference/infrahub-events/` |
| Server config | `docs/docs/reference/configuration.mdx` |

```bash
uv run invoke docs.generate    # regenerate all of the above
uv run invoke docs.validate    # regenerate, then fail on any uncommitted diff (run in CI)
```

Adding or changing a field on an event class, a schema model, a CLI command, or a config setting changes the rendered output. Regenerate and commit, or the `validate-generated-documentation` CI job fails. As with the other validators, when `docs.validate` fails the corrected files are already written to disk — just stage and commit them.

## Frontend Codegen

Configured in `frontend/app/graphql.config.ts`. Uses `@graphql-codegen/cli` with:

- **Source**: `schema/schema.graphql` (local file, no instance needed)
- **Documents**: `src/**/*.{ts,tsx}` (scans for GraphQL operations)
- **Output**: `src/shared/api/graphql/generated/types.ts`

## Compose Env Block

The root `docker-compose.yml` env block is rendered from the backend settings, so adding a
setting to `config.py` makes the committed compose file stale. Two traps:

- `release.gen-config-env` writes nothing by default. Its `update_docker_file` parameter is
  `False`, so the plain invocation silently no-ops — pass `-u` / `--update-docker-file`.
- `release.validate-dockercomposeenv` regenerates and then runs `git diff --exit-code`, so it
  reports failure for an *uncommitted* regeneration exactly as it does for a stale one. Commit
  the regenerated file, then re-run it.

The `update-compose-file-and-chart` workflow regenerates it with `-u` on a schedule, and
`ci.yml` runs the validation, so a stale file fails CI rather than drifting quietly. Prose that
describes which compose files carry a given variable goes stale on the same regeneration —
`dev/knowledge/frontend/theming.md` once claimed the root file had no dark-theme passthrough
after generation had added one.

## Key Locations

| Component | Path |
|-----------|------|
| Backend generation task | `tasks/backend.py` (`generate`, `validate_generated`) |
| Schema generation/validation tasks | `tasks/schema.py` (`generate_graphqlschema`, `validate_graphqlschema`, etc.) |
| Jinja2 templates | `backend/templates/` |
| Frontend codegen config | `frontend/app/graphql.config.ts` |

## See Also

- [Schema Definitions](schema-definitions.md) — How to define schemas that feed the pipeline
- [ADR 0010](../../adr/0010-generated-user-facing-schema-contract.md) — Why the user-facing schema
  contract is generated into the SDK submodule
