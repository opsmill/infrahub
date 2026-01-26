# PR 4: GraphQL File Upload Support

**Jira:** IFC-2174
**Branch:** `feature/file-object-graphql-upload`
**Dependencies:** PR 1 (schema), PR 2 (config), PR 3 (GraphQL tests)

## Overview

Add support for file uploads via GraphQL mutations using the GraphQL Multipart Request Spec. Files are attached directly when creating/updating FileObject nodes - no separate upload step required.

## Background

### Current State

Infrahub's GraphQL app (`backend/infrahub/graphql/app.py`, lines 485-525) **already supports multipart/form-data** parsing. It implements the GraphQL Multipart Request Spec, parsing `operations`, `map`, and file fields.

However:
- **No `Upload` scalar defined** - Graphene doesn't have a built-in Upload type
- **graphene-file-upload library is unmaintained** - Not an option

### Solution

Implement a custom `Upload` scalar for Graphene that:
1. Accepts file uploads in multipart/form-data requests
2. Integrates with existing multipart parsing in `app.py`
3. Can be used as a `file` parameter in Create/Update/Upsert mutations for FileObject types

## Tasks

### Custom Upload Scalar

- [ ] Create `backend/infrahub/graphql/types/upload.py`
  - [ ] Define `Upload` scalar class extending `graphene.Scalar`
  - [ ] Implement `serialize()` - not applicable for uploads (raise error)
  - [ ] Implement `parse_value()` - receives the file object from multipart parsing
  - [ ] Implement `parse_literal()` - not applicable for uploads (raise error)
  - [ ] Add type annotations and documentation

### Combined Create/Update Mutations with File Parameter

- [ ] Modify mutation generation in `backend/infrahub/graphql/manager.py`
  - [ ] Detect when a schema type inherits from CoreFileObject
  - [ ] Add optional `file: Upload` parameter to Create mutation input
  - [ ] Add optional `file: Upload` parameter to Update mutation input
  - [ ] Add optional `file: Upload` parameter to Upsert mutation input

- [ ] Implement file handling in mutation resolvers
  - [ ] Create helper function `process_file_upload(file, db, branch)` in a new file (e.g., `backend/infrahub/graphql/mutations/file_upload.py`):
    - [ ] Validate file size against `config.SETTINGS.storage.max_file_size`
    - [ ] Generate new UUID as `storage_id`
    - [ ] Calculate SHA-1 checksum
    - [ ] Detect MIME type using `puremagic` library (magic bytes, not extension)
    - [ ] Extract file metadata (name, size, type)
    - [ ] Store file via `registry.storage.store()`
    - [ ] Return dict with all file attributes
  - [ ] Modify Create mutation resolver to:
    - [ ] Check if `file` parameter is provided
    - [ ] If yes, call `process_file_upload()` and set all FileObject attributes
    - [ ] Proceed with normal node creation
  - [ ] Modify Update mutation resolver similarly
  - [ ] Modify Upsert mutation resolver similarly

- [ ] Handle read-only attribute population
  - [ ] When `file` is provided, system sets `file_name`, `checksum`, `file_size`, `file_type`, `storage_id`
  - [ ] These values override any user-provided values (if somehow passed)

### App Integration

- [ ] Modify `backend/infrahub/graphql/app.py`
  - [ ] Ensure uploaded files are passed to mutation resolvers via context
  - [ ] Verify existing multipart parsing works with new Upload scalar

### Dependencies

- [ ] Add `puremagic` to project dependencies (for MIME type detection from file content)

### Tests

- [ ] Create `backend/tests/unit/graphql/types/test_upload_scalar.py`
  - [ ] Test `Upload` scalar rejects serialization (output)
  - [ ] Test `Upload` scalar accepts file objects in `parse_value()`
  - [ ] Test `Upload` scalar rejects literal values

- [ ] Create `backend/tests/unit/graphql/mutations/test_file_upload.py`
  - [ ] Test fixtures:
    - [ ] Schema with type inheriting CoreFileObject (e.g., `TestFileContract`)
    - [ ] Test file content (both text and binary)
    - [ ] Mock storage
  - [ ] **Create mutation tests:**
    - [ ] Test Create with file creates node and stores file in one step
    - [ ] Test Create with file sets all FileObject attributes correctly
    - [ ] Test Create with file returns complete node with storage_id
    - [ ] Test Create without file fails (file is required for CoreFileObject types)
    - [ ] Test Create with file exceeding max_file_size returns error
    - [ ] Test Create with file and permission denied returns error
    - [ ] Test Create with file calculates correct SHA-1 checksum
    - [ ] Test Create with file detects correct MIME type via puremagic
  - [ ] **Update mutation tests:**
    - [ ] Test Update with file replaces stored file
    - [ ] Test Update with file updates all FileObject attributes
    - [ ] Test Update without file leaves FileObject attributes unchanged
  - [ ] **Upsert mutation tests:**
    - [ ] Test Upsert with file (create path) works correctly
    - [ ] Test Upsert with file (update path) works correctly
  - [ ] **Integration tests:**
    - [ ] Test multipart request with file upload
    - [ ] Test file stored correctly in storage backend
    - [ ] Test round-trip: create with file, query, verify attributes

### Verification

- [ ] Run `uv run invoke backend.test-unit` to run all unit tests
- [ ] Run `uv run invoke backend.test-component` to run all component tests
- [ ] Regenerate frontend GraphQL types: `cd frontend/app && npm run codegen:graphql`
- [ ] Manual testing with GraphQL client that supports file uploads

## Reference Files

- `backend/infrahub/graphql/app.py` - Existing multipart/form-data parsing (lines 485-525)
- `backend/infrahub/graphql/types/` - Existing custom scalar types
- `backend/infrahub/graphql/mutations/` - Existing mutation patterns
- [GraphQL Multipart Request Spec](https://github.com/jaydenseric/graphql-multipart-request-spec)

## API Design

### Create Mutation with File

```graphql
mutation($file: Upload!) {
  NetworkCircuitContractCreate(
    data: {
      contract_start: { value: "2026-01-01" }
      contract_end: { value: "2026-12-31" }
      signed_by: { id: "..." }
    }
    file: $file  # File upload - system sets storage_id, file_name, checksum, file_size, file_type
  ) {
    ok
    object {
      id
      storage_id { value }
      file_name { value }
      checksum { value }
      file_size { value }
      file_type { value }
    }
  }
}
```

When `file` is provided:
1. System stores the file in storage backend
2. System generates `storage_id`, calculates `checksum`, extracts `file_name`, `file_size`
3. System detects `file_type` using `puremagic` (magic bytes)
4. System sets all FileObject attributes internally
5. Node is created with all data in a single operation

### Update Mutation with File

```graphql
mutation($file: Upload!) {
  NetworkCircuitContractUpdate(
    data: {
      id: "..."
      contract_end: { value: "2027-12-31" }
    }
    file: $file  # Optional: upload new file version
  ) {
    ok
    object {
      id
      storage_id { value }
    }
  }
}
```

### Multipart Request Format

Following the GraphQL Multipart Request Spec:

```
POST /graphql
Content-Type: multipart/form-data; boundary=----boundary

------boundary
Content-Disposition: form-data; name="operations"

{"query":"mutation($file: Upload!) { NetworkCircuitContractCreate(data: {contract_start: {value: \"2026-01-01\"}, contract_end: {value: \"2026-12-31\"}, signed_by: {id: \"...\"}}, file: $file) { ok object { id storage_id { value } } } }","variables":{"file":null}}
------boundary
Content-Disposition: form-data; name="map"

{"0":["variables.file"]}
------boundary
Content-Disposition: form-data; name="0"; filename="contract.pdf"
Content-Type: application/pdf

<file content>
------boundary--
```

## Workflow

### Single-Step File Upload (This PR)

```
mutation Create(data: {...}, file: $file) → creates node with file in one operation
```

**Benefits:**
- Single API call for file + node creation
- No separate storage_id handling
- All FileObject attributes set automatically
- Simpler client implementation

### Download (REST Only)

```
GET /api/file-object/{kind}/object/{id} → downloads file binary
```

GraphQL returns metadata only; binary download uses REST (implemented in PR 5).

## Notes

- The `Upload` scalar is input-only - it cannot be used in query responses
- File size limits are enforced before storage write
- MIME type detection uses `puremagic` to analyze file content (magic bytes), not just extension
- The existing multipart parsing in `app.py` should work with minimal changes
- All FileObject attributes (including `storage_id`) are read-only - the system sets them automatically when a file is provided
