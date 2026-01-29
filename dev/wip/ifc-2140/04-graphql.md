# PR 3: GraphQL API Integration

**Jira:** IFC-XXXX
**Branch:** `feature/file-object-graphql`
**Dependencies:** PR 1 (schema)

## Overview

Verify that GraphQL queries, mutations, and filters are properly auto-generated for CoreFileObject types. The existing GraphQL schema manager already handles read-only attributes correctly.

## Background

The `GraphQLSchemaManager` in `backend/infrahub/graphql/manager.py` already:
- **Excludes read-only attributes from mutation inputs** (lines 763-866)
- **Includes read-only attributes in Query responses**
- **Auto-generates filters for all attributes**

## Tasks

### Verification (Manual)

- [x] Review `backend/infrahub/graphql/manager.py` to confirm:
  - [x] `generate_graphql_mutation_create_input()` skips `read_only=True` attributes
  - [x] `generate_graphql_mutation_update_input()` skips `read_only=True` attributes
  - [x] `generate_graphql_mutation_upsert_input()` skips `read_only=True` attributes
  - [x] `generate_filters()` includes all attributes regardless of read_only status

### Manual Verification Checklist

The following can be verified manually by inspecting the generated GraphQL schema:

- [x] Query type includes all FileObject attributes (`file_name`, `checksum`, `file_size`, `file_type`, `storage_id`)
- [x] Create mutation input excludes all FileObject attributes (all are read-only)
- [x] Update mutation input excludes all FileObject attributes
- [x] Upsert mutation input excludes all FileObject attributes
- [x] Filters exist for all attributes (`file_name__value`, `checksum__value`, etc.)

**Note:** Automated mutation tests with file upload are in PR 4 (`backend/tests/component/graphql/mutations/test_file_object.py`).

## Reference Files

- `backend/infrahub/graphql/manager.py` - GraphQL schema generation
- `backend/tests/component/graphql/mutations/test_file_object.py` - Mutation tests (PR 4)

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
# Create - all FileObject fields are read-only and excluded from data input
# The file parameter handles file upload and auto-populates these fields
mutation($file: Upload!) {
  TestFileContractCreate(
    data: {
      contract_start: { value: "2026-01-01" }
      contract_end: { value: "2026-12-31" }
      # file_name, checksum, file_size, file_type, storage_id NOT HERE (all read-only)
    }
    file: $file
  ) {
    ok
    object {
      id
      file_name { value }
      storage_id { value }
    }
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

- Schema generation behavior is verified through the mutation tests in PR 4
- The mutation tests implicitly verify that read-only attributes are excluded (mutations work correctly)
- Manual inspection of GraphQL schema can verify query fields and filters
