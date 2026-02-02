# PR 5: REST API Endpoints for FileObject

**Jira:** IFC-2173, IFC-2176
**Branch:** `feature/file-object-rest-api`
**Dependencies:** PR 1 (schema), PR 2 (config), PR 4 (GraphQL upload)

## Overview

Add REST API endpoints for **downloading** file objects. Three download methods are supported:
1. **By storage_id** - Direct download using the file's storage identifier
2. **By node ID** - Download using the FileObject node's UUID
3. **By HFID** - Download using the Human-Friendly ID

Upload endpoint is **not implemented** - GraphQL is the primary upload method.

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
  - [x] Implement `GET /id/{node_id}` endpoint (download by node UUID)
    - [x] Look up FileObject node by ID using `NodeManager.get_one()`
    - [x] Check VIEW permission on the FileObject's actual kind
    - [x] Retrieve file using the node's `storage_id` attribute
    - [x] Return raw bytes with Content-Type and Content-Disposition headers
    - [x] Handle 404 if node_id not found
    - [x] Handle 403 if permission denied
  - [x] Implement `GET /hfid/{kind}` endpoint (download by HFID)
    - [x] Accept `hfid` query parameters (repeatable for multi-component HFIDs)
    - [x] Look up FileObject node by HFID using `NodeManager.get_one_by_hfid()`
    - [x] Validate that the kind inherits from `CoreFileObject`
    - [x] Check VIEW permission on the FileObject's actual kind
    - [x] Retrieve file using the node's `storage_id` attribute
    - [x] Return raw bytes with Content-Type and Content-Disposition headers
    - [x] Handle 404 if HFID not found or kind doesn't exist
    - [x] Handle 403 if permission denied

### Router Registration

- [x] Create `backend/infrahub/api/storage/__init__.py`
  - [x] Import `file_object` module from `infrahub.api.storage`
  - [x] Import `router` from `storage.py`
  - [x] Include `file_object.router` as a sub-router (routes appear under `/storage` namespace)

### Legacy Storage Endpoint Protection

- [x] Modify `backend/infrahub/api/storage/storage.py`
  - [x] Update `GET /api/storage/object/{identifier}` to reject FileObject files
  - [x] Check if identifier belongs to a FileObject using `NodeManager.query()`
  - [x] Return 403 with message directing users to the proper endpoint
  - [x] Convert endpoint to async to support database queries

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
  - [x] Test download with preview=true returns Content-Disposition: inline
  - [x] Test download nonexistent file returns 404
  - [x] Test download without VIEW permission returns 403
  - [x] Test download with VIEW permission succeeds
  - [x] Test legacy storage endpoint rejects FileObject access
  - [x] Test download by node ID returns correct content
  - [x] Test download by node ID with nonexistent ID returns 404
  - [x] Test download by node ID without VIEW permission returns 403
  - [x] Test download by HFID returns correct content
  - [x] Test download by HFID returns correct headers
  - [x] Test download by HFID with nonexistent HFID returns 404
  - [x] Test download by HFID with invalid kind returns 404
  - [x] Test download by HFID with non-FileObject kind returns 400
  - [x] Test download by HFID without VIEW permission returns 403
  - [x] Test download by HFID with multi-value human_friendly_id

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
- [x] Run `uv run pytest tests/component/api/test_file_object.py -v` - all 18 tests pass
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

## API Endpoints

### Download File by Node ID (Main Endpoint)

```
GET /api/storage/files/{node_id}?branch={branch_name}&preview={true|false}

Query Parameters:
- branch (optional): Branch name, defaults to current branch
- preview (optional): If true, return file for inline display (Content-Disposition: inline) rather than as an attachment. Useful for previewing text, images, or videos in the browser. Defaults to false.

Response 200:
Content-Type: <file_type from FileObject node>
Content-Disposition: inline|attachment; filename="<sanitized_filename>"; filename*=UTF-8''<encoded_filename>
<binary content>

Response 404: Node ID not found
Response 401: Unauthorized (when anonymous access disabled)
Response 403: Permission denied (user lacks VIEW permission on the FileObject)
```

### Download File by HFID

```
GET /api/storage/files/by-hfid/{kind}?hfid={value1}&hfid={value2}&branch={branch_name}&preview={true|false}

Path Parameters:
- kind: The FileObject kind (e.g., NetworkCircuitContract)

Query Parameters:
- hfid (required, repeatable): HFID component values in order
- branch (optional): Branch name, defaults to current branch
- preview (optional): If true, return file for inline display rather than as an attachment. Defaults to false.

Response 200:
Content-Type: <file_type from FileObject node>
Content-Disposition: inline|attachment; filename="<sanitized_filename>"; filename*=UTF-8''<encoded_filename>
<binary content>

Response 404: HFID not found or kind doesn't exist/inherit from CoreFileObject
Response 401: Unauthorized (when anonymous access disabled)
Response 403: Permission denied (user lacks VIEW permission on the FileObject)
```

### Download File by Storage ID

```
GET /api/storage/files/by-storage-id/{storage_id}?branch={branch_name}&preview={true|false}

Query Parameters:
- branch (optional): Branch name, defaults to current branch
- preview (optional): If true, return file for inline display rather than as an attachment. Defaults to false.

Response 200:
Content-Type: <file_type from FileObject node, e.g., application/pdf, image/png>
Content-Disposition: inline|attachment; filename="<sanitized_filename>"; filename*=UTF-8''<encoded_filename>
<binary content>

Response 404: Storage ID not found
Response 401: Unauthorized (when anonymous access disabled)
Response 403: Permission denied (user lacks VIEW permission on the FileObject)
```

## Design Rationale

### Why multiple download endpoints?

1. **By node ID** (main endpoint): The primary way to download files. Use when you have a reference to the FileObject node. Resolves the storage_id for the specified branch.

2. **By HFID**: Useful for human-readable access when you know the node's human-friendly identifier. Supports multi-component HFIDs via repeated query parameters.

3. **By storage_id**: Best for direct file access when you have the storage identifier. Inherently branch-aware since `storage_id` changes when a file is updated.

### How does permission checking work?

1. The endpoint looks up the FileObject node by `storage_id` using `NodeManager.query()`
2. Gets the actual schema/kind of the node (e.g., `TestingFileContract`)
3. Checks VIEW permission on that specific kind using `define_object_permission_from_branch()`
4. Returns 403 if the user lacks permission

### Why return the actual file_type?

The endpoint returns the actual Content-Type from the node's `file_type` attribute (e.g., `application/pdf`, `image/png`) rather than a generic `application/octet-stream`. This allows browsers to handle files appropriately (e.g., displaying images inline).

### What does the preview parameter do?

The `preview` query parameter controls the `Content-Disposition` header:
- `preview=false` (default): Returns `Content-Disposition: attachment`, which forces browsers to download the file.
- `preview=true`: Returns `Content-Disposition: inline`, which allows browsers to display supported file types (images, PDFs, text, videos) directly in the browser window instead of downloading them.

### How is the filename handled securely?

The filename from the FileObject node is sanitized before being included in the Content-Disposition header:
1. Control characters (CR, LF, NULL) are stripped to prevent CRLF injection attacks
2. Quotes and semicolons are replaced to prevent header parsing manipulation
3. Long filenames are truncated to 255 characters while preserving the extension
4. Unicode filenames are supported via RFC5987 encoding (`filename*=UTF-8''...`)

### Why block the legacy storage endpoint for FileObject files?

The legacy `/api/storage/object/{identifier}` endpoint allows downloading files by their storage identifier without permission checks beyond authentication. To ensure FileObject permission checks cannot be bypassed, this endpoint now:
1. Checks if the requested identifier belongs to a FileObject
2. Returns 403 with a message directing users to the proper endpoint (`/api/storage/files/{storage_id}`)
3. Only allows access to non-FileObject files (e.g., artifacts)

## Workflow

**GraphQL (primary upload method):**
- `mutation Create(data: {...}, file: $file)` → file uploaded and node created in one step
- Query returns `storage_id`, `file_name`, `file_type`, etc.

**REST (download only):**
- `GET /api/storage/files/{storage_id}` → downloads file binary (requires VIEW permission)
