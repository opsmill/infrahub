# Quickstart: validating stored schema changes

**Feature**: `dev/specs/ifc-3614-store-schema-changes`

How to run the validation for this feature, and what each run must show. The test paths below are
planned: `tasks.md` creates them. The unit tests need no database. The component and functional
tests start Neo4j through testcontainers, so they need a running Docker daemon.

## Prerequisites

- A running Docker daemon.
- Python dependencies installed with `uv sync --all-groups`.
- No `INFRAHUB_*` variable set in the shell that would point the tests at another database.

## 1. The equivalence suite (user story 1)

```bash
uv run pytest backend/tests/unit/core/schema_change/
```

What it must show:

- Every case of FR-024 passes: the schema that the applier builds from the recorded operations has
  the same hash for every kind as the schema of a direct load, and the migrations and constraints
  are the same.
- Each of the four known-bug cases of FR-025 either passes or is reported as an expected failure
  that names its bug. An expected failure that starts to pass fails the run, so the marker is
  removed when the bug is fixed.
- No recorded operation holds an `id` or a `number_pool_id`.

This suite must pass before any other task of the feature starts, because the format of the
operations stays open until it does.

## 2. The records and the query against Neo4j (user stories 2 to 5)

Run one package for each pytest session.

```bash
uv run pytest backend/tests/component/core/schema_change/
uv run pytest backend/tests/component/graphql/queries/test_schema_change.py
uv run pytest backend/tests/component/api/test_40_schema.py
uv run pytest backend/tests/component/graphql/mutations/test_schema_dropdown_and_enum_history.py
uv run pytest backend/tests/component/core/test_branch.py
```

What they must show:

- The repository creates, reads, updates and deletes the four records, and reads schema changes
  and operations in pages.
- The first schema change of a branch gets main's version at `branched_from` plus 1, and has
  main's schema change at that version as its parent.
- The history query returns applied schema changes by version and the others by creation time,
  and the count of all pages.
- A schema load stores one schema change, a second load of the same file stores none, and a
  schema check stores none.
- A dropdown or enum mutation stores one schema change with one operation. A refused mutation
  stores none.
- Deleting a branch's data deletes its records and leaves the records of main.

## 3. Loads with data, in one process (user stories 2, 3 and 5)

```bash
uv run pytest backend/tests/functional/schema_change/
```

What it must show:

- Three loads on a branch with nodes give three applied schema changes with consecutive versions,
  each with the migrations that ran.
- A load whose migration fails leaves the schema and the data as they were, and the history shows
  the schema change and its application as failed, with the error and the status of each
  migration.
- A rebase and a merge leave every record unchanged.
- Deleting the branch deletes its records.

## 4. Migrations on a separate worker

```bash
uv run pytest backend/tests/integration_docker/test_schema_migration.py
```

What it must show: after a load whose migrations run on a task worker, the history query returns
the migration records with the status `applied`.

## 5. The existing behaviour is unchanged (SC-002)

```bash
uv run invoke backend.test-unit
uv run pytest backend/tests/integration/schema_lifecycle/
uv run pytest backend/tests/functional/schemas/ backend/tests/functional/api/test_load_schema.py
```

What it must show: every test passes with the expected results it had before this feature.

## 6. By hand, on a local instance

```bash
uv run invoke dev.build
uv run invoke dev.start
uv run invoke dev.load-infra-schema
```

Then, in the GraphQL sandbox of the instance, on the branch `main`:

```graphql
query {
  InfrahubSchemaChange {
    count
    edges {
      node {
        name
        version
        status
        operations(limit: 5) { count edges { node { operation_type kind element_name } } }
        applications { status migrations { migration_name path status } }
      }
    }
  }
}
```

What it must show: at least one applied schema change for the schema that was loaded. The first
one has the version 1 and a name that starts with `00001_`. Load the same schema again and run the
query again: `count` is unchanged.

The contract of the query is in
[contracts/schema-change-history.graphql](contracts/schema-change-history.graphql).

## 7. Generated files

```bash
uv run invoke schema.generate-graphqlschema
uv run invoke schema.validate-graphqlschema
uv run invoke docs.validate
(cd frontend/app && pnpm codegen:graphql)
```

What it must show: `schema/schema.graphql` and the generated front-end GraphQL types include the
new query, and the validation commands report no stale file.
