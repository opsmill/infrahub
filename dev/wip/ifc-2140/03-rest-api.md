# PR 5: REST API Endpoints for FileObject

**Jira:** IFC-2173, IFC-2176
**Branch:** `feature/file-object-rest-api`
**Dependencies:** PR 1 (schema), PR 2 (config), PR 4 (GraphQL upload)

## Overview

Add REST API endpoint for **downloading** file objects by storage_id. Upload endpoint is **not implemented** - GraphQL is the primary upload method.

The endpoint uses `storage_id` (not node ID) because:
- `storage_id` is a UUIDT that changes when a file is updated
- Different branches have different `storage_id` values for modified files
- This makes the endpoint inherently branch-aware

**Note:** REST upload endpoint not implemented since GraphQL upload (PR 4) is sufficient.

## Tasks

### Storage Layer - Binary Support

- [x] Modify `backend/infrahub/storage.py`
  - [x] Add `retrieve_binary(identifier: str) -> bytes` method that returns raw bytes
  - [x] Keep existing `retrieve()` for backward compatibility with artifacts

### API Module

- [x] Create `backend/infrahub/api/storage/file_object.py`
  - [x] Define router with prefix `/files`
  - [x] Implement `GET /{storage_id}` endpoint (binary download)
    - [x] Look up FileObject node by storage_id using `NodeManager.query()`
    - [x] Check VIEW permission on the FileObject's actual kind using `define_object_permission_from_branch()`
    - [x] Retrieve file as binary via `registry.storage.retrieve_binary()`
    - [x] Return raw bytes with Content-Type from the node's `file_type` attribute
    - [x] Return Content-Disposition header with sanitized filename from the node
    - [x] Handle 404 if storage_id not found
    - [x] Handle 403 if permission denied
  - [x] Add `sanitize_filename()` and `build_content_disposition()` helpers
    - [x] Strip control characters (CR, LF, NULL) to prevent header injection
    - [x] Replace quotes and semicolons to prevent header parsing issues
    - [x] Truncate long filenames (max 255 chars) while preserving extension
    - [x] Support Unicode filenames with RFC5987 encoding

### Router Registration

- [x] Create `backend/infrahub/api/storage/__init__.py`
  - [x] Import `file_object` module from `infrahub.api.storage`
  - [x] Import `router` from `storage.py`
  - [x] Include `file_object.router` as a sub-router (routes appear under `/storage` namespace)


### Tests

- [x] Create `backend/tests/unit/storage/test_retrieve.py`
  - [x] Test `retrieve()` returns decoded string
  - [x] Test `retrieve()` with UTF-8 content
  - [x] Test `retrieve()` raises NodeNotFoundError for missing identifier
  - [x] Test `retrieve_binary()` returns raw bytes
  - [x] Test `retrieve_binary()` with binary file (e.g., PNG image)
  - [x] Test `retrieve_binary()` raises NodeNotFoundError for missing identifier
  - [x] Test `retrieve_binary()` vs `retrieve()` difference

- [x] Create `backend/tests/component/api/test_file_object.py`
  - [x] Test download returns correct content
  - [x] Test download binary file (PNG)
  - [x] Test download returns correct content type from node
  - [x] Test download returns Content-Disposition header with filename
  - [x] Test download nonexistent file returns 404
  - [x] Test download without VIEW permission returns 403
  - [x] Test download with VIEW permission succeeds

- [x] Create `backend/tests/unit/api/test_file_object.py`
  - [x] Test simple filename passes through unchanged
  - [x] Test control characters are stripped
  - [x] Test quotes and semicolons are replaced
  - [x] Test long filenames are truncated
  - [x] Test Unicode filenames are properly encoded
  - [x] Test Content-Disposition header format
  - [x] Test header injection prevention

### Verification

- [x] Run `uv run pytest tests/unit/storage/test_retrieve.py -v` - all 7 tests pass
- [x] Run `uv run pytest tests/unit/api/test_file_object.py -v` - all 13 tests pass
- [x] Run `uv run pytest tests/component/api/test_file_object.py -v` - all 7 tests pass
- [x] Run `uv run invoke schema.generate-jsonschema` - regenerate OpenAPI schema
- [x] Run `cd frontend/app && npm run codegen:openapi` - regenerate frontend REST types

## Reference Files

- `backend/infrahub/api/storage/file_object.py` - File object download endpoint with filename sanitization
- `backend/infrahub/api/storage/storage.py` - Legacy storage endpoints
- `backend/infrahub/api/storage/__init__.py` - Storage module router aggregation
- `backend/infrahub/storage.py` - Storage layer with `retrieve_binary()` method
- `backend/tests/adapters/storage.py` - DummyObjectStorage with `retrieve_binary()`
- `backend/tests/unit/storage/test_retrieve.py` - Unit tests for storage retrieval methods
- `backend/tests/unit/api/test_file_object.py` - Unit tests for filename sanitization
- `backend/tests/component/api/test_file_object.py` - Component tests for download endpoint
- `schema/openapi.json` - OpenAPI schema (regenerated with `uv run invoke schema.generate-jsonschema`)
- `frontend/app/src/shared/api/rest/types.generated.ts` - Frontend REST types (regenerated with `npm run codegen:openapi`)

## API Endpoint

### Download File

```
GET /api/storage/CoreFileObject/{storage_id}

Response 200:
Content-Type: <file_type from FileObject node, e.g., application/pdf, image/png>
Content-Disposition: attachment; filename="<sanitized_filename>"; filename*=UTF-8''<encoded_filename>
<binary content>

Response 404: Storage ID not found
Response 401: Unauthorized (when anonymous access disabled)
Response 403: Permission denied (user lacks VIEW permission on the FileObject)
```

## Design Rationale

### Why storage_id instead of node ID?

1. **Branch awareness**: The `storage_id` is a UUIDT that changes when a file is updated or modified in a branch. By using `storage_id` for downloads, the endpoint is inherently branch-aware without needing branch parameters.

2. **Immutability**: Each file version has a unique `storage_id`, enabling time travel to historical versions.

### How does permission checking work?

1. The endpoint looks up the FileObject node by `storage_id` using `NodeManager.query()`
2. Gets the actual schema/kind of the node (e.g., `TestingFileContract`)
3. Checks VIEW permission on that specific kind using `define_object_permission_from_branch()`
4. Returns 403 if the user lacks permission

### Why return the actual file_type?

The endpoint returns the actual Content-Type from the node's `file_type` attribute (e.g., `application/pdf`, `image/png`) rather than a generic `application/octet-stream`. This allows browsers to handle files appropriately (e.g., displaying images inline).

### How is the filename handled securely?

The filename from the FileObject node is sanitized before being included in the Content-Disposition header:
1. Control characters (CR, LF, NULL) are stripped to prevent CRLF injection attacks
2. Quotes and semicolons are replaced to prevent header parsing manipulation
3. Long filenames are truncated to 255 characters while preserving the extension
4. Unicode filenames are supported via RFC5987 encoding (`filename*=UTF-8''...`)

## Workflow

**GraphQL (primary upload method):**
- `mutation Create(data: {...}, file: $file)` → file uploaded and node created in one step
- Query returns `storage_id`, `file_name`, `file_type`, etc.

**REST (download only):**
- `GET /api/storage/files/{storage_id}` → downloads file binary (requires VIEW permission)
