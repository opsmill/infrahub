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

- [x] Create `backend/infrahub/graphql/types/upload.py`
  - [x] Define `Upload` scalar class extending `graphene.Scalar`
  - [x] Implement `serialize()` - raises `GraphQLError` (input-only type)
  - [x] Implement `parse_value()` - receives the file object from multipart parsing
  - [x] Implement `parse_literal()` - raises `GraphQLError` (must use multipart)
  - [x] Add type annotations and documentation
  - [x] Export from `backend/infrahub/graphql/types/__init__.py`

### Schema Property for FileObject Detection

- [x] Add `is_file_object` property to schema classes (consistent with `is_ip_address`, `is_ip_prefix`)
  - [x] `BaseNodeSchema.is_file_object` returns `False` by default
  - [x] `NodeSchema.is_file_object` checks `InfrahubKind.FILEOBJECT in self.inherit_from`

### Combined Create/Update Mutations with File Parameter

- [x] Modify mutation generation in `backend/infrahub/graphql/manager.py`
  - [x] Use `schema.is_file_object` property to detect CoreFileObject inheritance
  - [x] Import `Upload` scalar
  - [x] Add required `file: Upload!` parameter to Create mutation for FileObject types
  - [x] Add optional `file: Upload` parameter to Update mutation for FileObject types
  - [x] Add required `file: Upload!` parameter to Upsert mutation for FileObject types

- [x] Create `FileUploadProcessor` class in `backend/infrahub/core/file_processor.py`
  - [x] `_get_file_size()` - Get file size without loading into memory
  - [x] `_format_file_size()` - Human-readable size formatting for errors
  - [x] `_detect_mime_type()` - MIME type detection using `puremagic` (magic bytes)
  - [x] `_compute_checksum()` - Calculate SHA-1 checksum in 64KB chunks
  - [x] `process()` - Validate, extract metadata, and store file:
    - [x] Validate file size against `config.SETTINGS.storage.max_file_size`
    - [x] Generate new UUID as `storage_id` (stored on instance)
    - [x] Calculate SHA-1 checksum
    - [x] Extract file metadata (name, size, type)
    - [x] Store file in storage backend via `registry.storage.store()`
    - [x] Return `FileUploadResult` dataclass
  - [x] `delete_file()` - Delete file from storage backend (for cleanup on mutation failure)

- [x] Add `delete()` method to storage layer
  - [x] `InfrahubObjectStorage.delete()` - Delete file by identifier
  - [x] `InfrahubS3ObjectStorage.delete()` - S3-specific delete using `bucket.Object(name).delete()`
  - [x] FileSystemStorage delete uses `Path.unlink(missing_ok=True)`
  - [x] `DummyObjectStorage.delete()` - Test implementation

- [x] Implement file handling in `backend/infrahub/graphql/mutations/main.py`
  - [x] Process and store file in `mutate()` method before mutation runs
  - [x] Merge file metadata into `data` dict
  - [x] Use try/finally to clean up stored file on mutation failure via `processor.delete_file()`
  - [x] `mutate_create()`, `mutate_update()`, `mutate_upsert()` remain clean (no file parameter)

### App Integration

- [x] No changes needed to `backend/infrahub/graphql/app.py`
  - [x] Existing multipart parsing already injects files into variables

### Dependencies

- [x] Add `puremagic` to project dependencies (for MIME type detection from file content)

### Test Helpers

- [x] Create reusable test schema `FILE_CONTRACT` in `backend/tests/helpers/schema.py`
- [x] Create `DummyObjectStorage` in `backend/tests/adapters/storage.py` for testing file storage

### Tests

- [x] Create `backend/tests/unit/graphql/types/test_upload_scalar.py`
  - [x] `test_upload_serialize_raises_error` - Upload scalar rejects serialization (GraphQLError)
  - [x] `test_upload_parse_value_returns_file` - Upload scalar accepts real UploadFile objects
  - [x] `test_upload_parse_value_returns_none` - Upload scalar handles None
  - [x] `test_upload_parse_literal_raises_error` - Upload scalar rejects literal values (GraphQLError)

- [x] Create `backend/tests/unit/core/test_file_processor.py`
  - [x] Uses fixtures instead of mocking (`dummy_storage`, `max_file_size_50mb`, `max_file_size_1mb`)
  - [x] `test_processor_returns_file_result` - Returns correct FileUploadResult
  - [x] `test_processor_calculates_sha1_checksum` - SHA-1 checksum is correct
  - [x] `test_processor_detects_mime_type` - MIME type detected via puremagic
  - [x] `test_processor_fallback_mime_type` - Falls back to application/octet-stream
  - [x] `test_processor_exceeds_max_size` - ValidationError for large files
  - [x] `test_processor_stores_file` - File stored in storage backend
  - [x] `test_processor_unnamed_file` - Uses storage_id as filename when not provided

- [x] Create `backend/tests/component/graphql/mutations/test_file_object.py`
  - [x] Uses class-scoped fixtures (`TestFileObjectMutations` class) for efficient test setup
  - [x] `test_create_file_object_mutation` - Full create flow with file upload and checksum verification
  - [x] `test_create_file_object_without_file_fails` - Create without file returns specific error message
  - [x] `test_update_file_object_with_new_file` - Update with new file replaces storage
  - [x] `test_update_file_object_without_file_preserves_existing` - Update without file keeps existing
  - [x] `test_create_file_object_stores_correct_content` - File content correctly stored
  - [x] `test_create_file_object_node_persisted_in_database` - Node persisted with correct attributes and checksum
  - [x] `test_create_file_object_not_stored_on_mutation_failure` - File cleaned up from storage on mutation error

### Verification

- [x] Run `uv run pytest tests/unit/graphql/types/test_upload_scalar.py tests/unit/core/test_file_processor.py -v` - all 11 tests pass (4 + 7)
- [x] Run `uv run pytest tests/component/graphql/mutations/test_file_object.py -v` - all 7 tests pass
- [x] Run all file object tests together - all 18 tests pass

## Reference Files

- `backend/infrahub/graphql/app.py` - Existing multipart/form-data parsing (lines 485-525)
- `backend/infrahub/graphql/types/upload.py` - Upload scalar implementation
- `backend/infrahub/core/file_processor.py` - FileUploadProcessor class
- `backend/infrahub/graphql/mutations/main.py` - Mutation resolvers with file handling
- `backend/infrahub/storage.py` - Storage layer with delete method
- `backend/infrahub/core/schema/node_schema.py` - `is_file_object` property
- `backend/tests/adapters/storage.py` - DummyObjectStorage for testing
- `backend/tests/helpers/schema.py` - Reusable FILE_CONTRACT test schema
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
1. System validates file size and extracts metadata (`file_name`, `file_size`, `checksum`)
2. System detects `file_type` using `puremagic` (magic bytes)
3. System generates `storage_id` and stores file in storage backend
4. Mutation runs to create/update node in the database
5. On success, file remains in storage
6. On failure, file is deleted from storage (no orphaned files)

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
X-INFRAHUB-KEY: <api-token>

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

### Example curl Command

```bash
curl -X POST http://localhost:8000/graphql \
  -H "X-INFRAHUB-KEY: your-api-token" \
  -H "Content-Type: multipart/form-data" \
  -F 'operations={"query": "mutation CreateFile($file: Upload!) { TestFileContractCreate(data: { description: { value: \"My contract\" } }, file: $file) { ok object { id file_name { value } file_size { value } checksum { value } storage_id { value } } } }", "variables": { "file": null }}' \
  -F 'map={"0": ["variables.file"]}' \
  -F '0=@/path/to/your/file.pdf'
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
GET /api/CoreFileObject/{storage_id} → downloads file binary
```

GraphQL returns metadata only; binary download uses REST (implemented in PR 5).

## Notes

- The `Upload` scalar is input-only - it cannot be used in query responses
- File processing stores the file first, then runs the mutation - on failure, file is cleaned up
- Files are cleaned up via `processor.delete_file()` in a try/finally block if mutation fails
- File size limits are enforced during `process()` before any storage write
- MIME type detection uses `puremagic` to analyze file content (magic bytes), not just extension
- The existing multipart parsing in `app.py` works without changes
- All FileObject attributes (including `storage_id`) are read-only - the system sets them automatically when a file is provided
- `storage_id` is a UUIDT that changes when a file is updated (enables branch-aware storage)
- For production deployment reverse proxy configuration, see the spec file: `dev/specs/2026-01-file-object.md`
