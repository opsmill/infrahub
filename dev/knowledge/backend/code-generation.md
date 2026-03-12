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
       └──► python_sdk/infrahub_sdk/protocols.py       (SDK protocols)

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
| Added/modified schema definitions (attributes, relationships) | `uv run invoke backend.generate` |
| Changed GraphQL schema structure | `uv run invoke schema.generate-graphqlschema` + `npm run codegen` |
| New GraphQL queries/mutations in frontend | `npm run codegen` |

Changes that do **not** require regeneration:
- Modifying Python business logic
- Changing frontend components

## Validation

```bash
uv run invoke backend.validate-generated       # protocols + generated models
uv run invoke schema.validate-graphqlschema    # schema/schema.graphql
uv run invoke schema.validate-jsonschema       # schema/openapi.json
```

Each validation task regenerates the files then checks for uncommitted diffs via `git diff --exit-code`. If validation fails, the correct file is already written to disk — just stage and commit it.

`backend.validate-generated` checks:
- `backend/infrahub/core/schema/generated/`
- `backend/infrahub/core/protocols.py`
- `backend/tests/protocols.py`

CI runs all three checks to ensure generated files are committed.

## Frontend Codegen

Configured in `frontend/app/graphql.config.ts`. Uses `@graphql-codegen/cli` with:
- **Source**: `schema/schema.graphql` (local file, no instance needed)
- **Documents**: `src/**/*.{ts,tsx}` (scans for GraphQL operations)
- **Output**: `src/shared/api/graphql/generated/types.ts`

## Key Locations

| Component | Path |
|-----------|------|
| Backend generation task | `tasks/backend.py` (`generate`, `validate_generated`) |
| Schema generation/validation tasks | `tasks/schema.py` (`generate_graphqlschema`, `validate_graphqlschema`, etc.) |
| Jinja2 templates | `backend/templates/` |
| Frontend codegen config | `frontend/app/graphql.config.ts` |

## See Also

- [Schema Definitions](schema-definitions.md) — How to define schemas that feed the pipeline
