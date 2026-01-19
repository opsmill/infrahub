# PR 5: GraphQL File Upload Support

**Jira:** IFC-2174
**Branch:** `feature/file-object-graphql-upload`
**Dependencies:** PR 1 (schema), PR 4 (GraphQL tests)

## Overview

Add support for file uploads via GraphQL mutations using the GraphQL Multipart Request Spec. This allows creating/updating FileObject nodes in a single mutation with the file included, rather than requiring a separate REST upload step.

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
3. Can be used in mutation inputs for FileObject types

## Tasks

### Custom Upload Scalar

- [ ] Create `backend/infrahub/graphql/types/upload.py`
  - [ ] Define `Upload` scalar class extending `graphene.Scalar`
  - [ ] Implement `serialize()` - not applicable for uploads (raise error)
  - [ ] Implement `parse_value()` - receives the file object from multipart parsing
  - [ ] Implement `parse_literal()` - not applicable for uploads (raise error)
  - [ ] Add type annotations and documentation

### Standalone Upload Mutation (Fallback)

- [ ] Create `backend/infrahub/graphql/mutations/file_object.py`
  - [ ] Define `FileObjectUpload` mutation class
  - [ ] Accept `file: Upload` parameter
  - [ ] Accept `node_kind: String` parameter to specify the FileObject type
  - [ ] Implement mutation resolver:
    - [ ] Validate `node_kind` inherits from CoreFileObject
    - [ ] Check CREATE permission on the node kind
    - [ ] Validate file size against `config.SETTINGS.storage.max_file_size`
    - [ ] Generate new UUID as `storage_id`
    - [ ] Calculate SHA-1 checksum
    - [ ] Extract file metadata (name, size, type)
    - [ ] Store file via `registry.storage.store()`
    - [ ] Return upload metadata (storage_id, checksum, file_name, file_size, file_type)

- [ ] Modify `backend/infrahub/graphql/mutations/__init__.py`
  - [ ] Register `FileObjectUpload` mutation

### Combined Create/Update Mutations (Primary Approach)

- [ ] Modify mutation generation in `backend/infrahub/graphql/manager.py`
  - [ ] Detect when a schema type inherits from CoreFileObject
  - [ ] Add optional `file: Upload` parameter to Create mutation input
  - [ ] Add optional `file: Upload` parameter to Update mutation input
  - [ ] Add optional `file: Upload` parameter to Upsert mutation input

- [ ] Implement file handling in mutation resolvers
  - [ ] Create helper function `process_file_upload(file, db, branch)` in `file_object.py`:
    - [ ] Validate file size against `config.SETTINGS.storage.max_file_size`
    - [ ] Generate new UUID as `storage_id`
    - [ ] Calculate SHA-1 checksum
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

### Tests

- [ ] Create `backend/tests/unit/graphql/types/test_upload_scalar.py`
  - [ ] Test `Upload` scalar rejects serialization (output)
  - [ ] Test `Upload` scalar accepts file objects in `parse_value()`
  - [ ] Test `Upload` scalar rejects literal values

- [ ] Create `backend/tests/unit/graphql/mutations/test_file_object_upload.py`
  - [ ] Test fixtures:
    - [ ] Schema with type inheriting CoreFileObject (e.g., `TestFileContract`)
    - [ ] Test file content (both text and binary)
    - [ ] Mock storage
  - [ ] **Standalone FileObjectUpload mutation tests:**
    - [ ] Test upload binary file returns correct metadata
    - [ ] Test upload text file returns correct metadata
    - [ ] Test upload calculates correct SHA-1 checksum
    - [ ] Test upload extracts correct file_name
    - [ ] Test upload detects correct file_type (MIME)
    - [ ] Test upload calculates correct file_size
    - [ ] Test upload with file exceeding max_file_size returns error
    - [ ] Test upload with invalid node_kind returns error
    - [ ] Test upload permission denied returns error
  - [ ] **Combined Create mutation tests (primary approach):**
    - [ ] Test Create with file creates node and stores file in one step
    - [ ] Test Create with file sets all FileObject attributes correctly
    - [ ] Test Create with file returns complete node with storage_id
    - [ ] Test Create without file works normally (storage_id must be provided)
    - [ ] Test Create with file exceeding max_file_size returns error
    - [ ] Test Create with file and permission denied returns error
  - [ ] **Combined Update mutation tests:**
    - [ ] Test Update with file replaces stored file
    - [ ] Test Update with file updates all FileObject attributes
    - [ ] Test Update without file leaves FileObject attributes unchanged
  - [ ] **Combined Upsert mutation tests:**
    - [ ] Test Upsert with file (create path) works correctly
    - [ ] Test Upsert with file (update path) works correctly
  - [ ] **Integration tests:**
    - [ ] Test multipart request with file upload
    - [ ] Test file stored correctly in storage backend
    - [ ] Test round-trip: create with file, query, verify attributes

### Verification

- [ ] Run `uv run invoke backend.test-unit` to run all unit tests
- [ ] Run `uv run invoke backend.test-component` to run all component tests
- [ ] Manual testing with GraphQL client that supports file uploads

## Reference Files

- `backend/infrahub/graphql/app.py` - Existing multipart/form-data parsing (lines 485-525)
- `backend/infrahub/graphql/types/` - Existing custom scalar types
- `backend/infrahub/graphql/mutations/` - Existing mutation patterns
- [GraphQL Multipart Request Spec](https://github.com/jaydenseric/graphql-multipart-request-spec)

## API Design

### Upload Mutation

```graphql
mutation {
  FileObjectUpload(
    node_kind: "NetworkCircuitContract"
    file: Upload!  # File from multipart/form-data
  ) {
    ok
    storage_id
    checksum
    file_name
    file_size
    file_type
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

{"query":"mutation($file: Upload!) { FileObjectUpload(node_kind: \"NetworkCircuitContract\", file: $file) { ok storage_id } }","variables":{"file":null}}
------boundary
Content-Disposition: form-data; name="map"

{"0":["variables.file"]}
------boundary
Content-Disposition: form-data; name="0"; filename="contract.pdf"
Content-Type: application/pdf

<file content>
------boundary--
```

### Combined Create Mutation (Primary Approach)

The Create/Update/Upsert mutations for types inheriting from CoreFileObject will accept an optional `file` parameter:

```graphql
mutation {
  NetworkCircuitContractCreate(
    data: {
      contract_start: { value: "2026-01-01" }
      contract_end: { value: "2026-12-31" }
      signed_by: { id: "..." }
    }
    file: Upload!  # Directly attach file - system sets storage_id and read-only attributes
  ) {
    ok
    object {
      id
      storage_id { value }
      file_name { value }
      checksum { value }
    }
  }
}
```

When `file` is provided:
1. System stores the file in storage backend
2. System generates `storage_id`, calculates `checksum`, extracts `file_name`, `file_size`, `file_type`
3. System sets all FileObject attributes internally
4. Node is created with all data in a single operation

This provides a **single-step workflow** for creating FileObjects.

## Workflow Comparison

### With REST API

```
1. POST /api/file-object/{kind}/upload  →  { storage_id, checksum, ... }
2. mutation Create(data: { storage_id: "...", ... })  →  { ok, object { id } }
```
Two steps required.

### With GraphQL Combined Mutation (This PR - Primary Approach)

```
1. mutation Create(data: { ... }, file: $file)  →  { ok, object { id, storage_id, ... } }
```
**Single step** - file upload and node creation in one mutation.

### With GraphQL Standalone Upload (Fallback)

```
1. mutation FileObjectUpload(file: $file)  →  { storage_id, checksum, ... }
2. mutation Create(data: { storage_id: "...", ... })  →  { ok, object { id } }
```
Two steps, but useful if user needs to upload file separately before creating node.

## Notes

- The `Upload` scalar is input-only - it cannot be used in query responses
- File size limits are enforced before storage write
- Permission checks use the `node_kind` parameter to determine access
- The existing multipart parsing in `app.py` should work with minimal changes
- Both REST and GraphQL upload will be available initially
- **If GraphQL upload proves better, the REST upload endpoint may be removed** - download will remain REST-only
