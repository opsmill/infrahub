# PR 4: GraphQL API Integration

**Jira:** IFC-XXXX
**Branch:** `feature/file-object-graphql`
**Dependencies:** PR 1 (schema)

## Overview

Verify and test that GraphQL queries, mutations, and filters are properly auto-generated for CoreFileObject types. The existing GraphQL schema manager already handles read-only attributes correctly, so this PR is primarily about adding tests.

## Background

The `GraphQLSchemaManager` in `backend/infrahub/graphql/manager.py` already:
- **Excludes read-only attributes from mutation inputs** (lines 763-866)
- **Includes read-only attributes in Query responses**
- **Auto-generates filters for all attributes**

No code changes should be needed - only tests to verify the behavior.

## Tasks

### Verification (No Code Changes Expected)

- [ ] Review `backend/infrahub/graphql/manager.py` to confirm:
  - [ ] `generate_graphql_mutation_create_input()` skips `read_only=True` attributes (line 763)
  - [ ] `generate_graphql_mutation_update_input()` skips `read_only=True` attributes (line 813)
  - [ ] `generate_graphql_mutation_upsert_input()` skips `read_only=True` attributes (line 865)
  - [ ] `generate_filters()` includes all attributes regardless of read_only status

### Tests

- [ ] Create `backend/tests/unit/graphql/test_file_object.py`
  - [ ] Test fixtures:
    - [ ] Define test schema with `TestFileContract` inheriting from `CoreFileObject`
    - [ ] Add custom attributes (e.g., `contract_start`, `contract_end`)
    - [ ] Add relationship (e.g., `signed_by`)
  - [ ] Query tests:
    - [ ] Test `CoreFileObject` query is generated
    - [ ] Test `TestFileContract` query includes all attributes (read-only + custom)
    - [ ] Test query returns `file_name`, `checksum`, `file_size`, `file_type`, `storage_id`
  - [ ] Mutation input tests:
    - [ ] Test `TestFileContractCreate` mutation exists
    - [ ] Test `TestFileContractCreate` input does NOT include read-only fields
    - [ ] Test `TestFileContractCreate` input DOES include custom fields
    - [ ] Test `TestFileContractUpdate` input does NOT include read-only fields
    - [ ] Test `TestFileContractUpsert` input does NOT include read-only fields
    - [ ] Test `TestFileContractDelete` mutation exists
  - [ ] Filter tests:
    - [ ] Test `file_name__value` filter exists
    - [ ] Test `file_name__values` filter exists
    - [ ] Test `checksum__value` filter exists
    - [ ] Test `file_size__value` filter exists
    - [ ] Test `file_type__value` filter exists
    - [ ] Test `storage_id__value` filter exists
  - [ ] Mutation execution tests:
    - [ ] Test Create mutation works (without read-only fields)
    - [ ] Test Update mutation works (without read-only fields)
    - [ ] Test Delete mutation works

### Verification

- [ ] Run `uv run invoke lint` to check for issues
- [ ] Run `uv run invoke backend.test-unit` to run all tests
- [ ] Manually inspect generated GraphQL schema

## Reference Files

- `backend/infrahub/graphql/manager.py` - GraphQL schema generation
- `backend/tests/unit/graphql/test_mutation_create.py` - Pattern for mutation tests
- `backend/tests/unit/graphql/test_query.py` - Pattern for query tests

## Expected GraphQL Schema

After PR 1 (schema) is merged, the following should be auto-generated:

### Query

```graphql
query {
  CoreFileObject {
    edges {
      node {
        id
        file_name { value }
        checksum { value }
        file_size { value }
        file_type { value }
        storage_id { value }
      }
    }
  }
}
```

### Mutation (for user-defined type)

```graphql
# Create - NO read-only fields
mutation {
  TestFileContractCreate(data: {
    contract_start: { value: "2026-01-01" }
    contract_end: { value: "2026-12-31" }
    signed_by: { id: "..." }
    # file_name, checksum, file_size, file_type, storage_id NOT HERE
  }) {
    ok
    object { id }
  }
}
```

### Filters

```graphql
query {
  TestFileContract(
    file_name__value: "contract.pdf"
    checksum__value: "abc123"
    file_size__value: 12345
    storage_id__values: ["uuid1", "uuid2"]
  ) {
    edges { node { id } }
  }
}
```

## Notes

- This PR adds tests to verify existing behavior - no code changes expected
- If tests fail, it indicates a bug in the GraphQL schema manager that needs fixing
- The pattern follows existing tests in `backend/tests/unit/graphql/`
