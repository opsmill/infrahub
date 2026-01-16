# PR 3: REST API Endpoints for FileObject

**Jira:** IFC-2173, IFC-2176
**Branch:** `feature/file-object-rest-api`
**Dependencies:** PR 1 (schema), PR 2 (config)

## Overview

Add REST API endpoints for uploading and downloading file objects with:
- Permission checks (unlike existing `/api/storage` endpoints)
- File size validation
- File metadata extraction (name, size, type, checksum)

## Tasks

### Storage Layer - Binary Support

**Note:** Current `InfrahubObjectStorage.retrieve()` decodes to string, breaking binary files. Need to add binary retrieval.

- [ ] Modify `backend/infrahub/storage.py`
  - [ ] Add `retrieve_binary(identifier: str) -> bytes` method that returns raw bytes
  - [ ] Keep existing `retrieve()` for backward compatibility with artifacts

### API Module

- [ ] Create `backend/infrahub/api/file_object.py`
  - [ ] Define router with prefix `/file-object`
  - [ ] Define Pydantic models:
    - [ ] `FileObjectUploadResponse` (identifier, checksum, file_name, file_size, file_type)
  - [ ] Implement `GET /{node_kind}/object/{identifier}` endpoint (binary download)
    - [ ] Validate `node_kind` inherits from CoreFileObject
    - [ ] Check VIEW permission via `PermissionManager.raise_for_permission()`
    - [ ] Retrieve file as **binary** via `registry.storage.retrieve_binary()`
    - [ ] Return raw bytes in response body
    - [ ] Set response headers (Content-Type, Content-Length, Content-Disposition)
    - [ ] Handle 404 if identifier not found
  - [ ] Implement `POST /{node_kind}/upload` endpoint (binary upload)
    - [ ] Accept file via `UploadFile` (multipart/form-data)
    - [ ] Validate `node_kind` inherits from CoreFileObject
    - [ ] Check CREATE permission via `PermissionManager.raise_for_permission()`
    - [ ] Validate file size against `config.SETTINGS.storage.max_file_size`
    - [ ] Read file content as **bytes** (not decoded)
    - [ ] Generate new identifier (UUID)
    - [ ] Calculate checksum (MD5) from bytes
    - [ ] Extract file_name from upload
    - [ ] Detect file_type (MIME type) from upload or file extension
    - [ ] Calculate file_size from bytes length
    - [ ] Store file bytes via `registry.storage.store()`
    - [ ] Return upload response with all metadata

### Router Registration

- [ ] Modify `backend/infrahub/api/__init__.py`
  - [ ] Import `file_object` module
  - [ ] Register `file_object.router`

### Tests

- [ ] Create `backend/tests/unit/storage/test_storage_binary.py`
  - [ ] Test `retrieve_binary()` returns raw bytes
  - [ ] Test `retrieve_binary()` with binary file (e.g., PNG image)
  - [ ] Test `retrieve_binary()` raises NodeNotFoundError for missing identifier

- [ ] Create `backend/tests/unit/api/test_file_object.py`
  - [ ] Test fixtures:
    - [ ] Schema with type inheriting CoreFileObject
    - [ ] Test file content (both text and binary)
  - [ ] **Binary upload tests:**
    - [ ] Test upload binary file (e.g., PNG image) - file stored correctly
    - [ ] Test upload text file (e.g., JSON) - file stored correctly
    - [ ] Test upload returns correct checksum for binary file
  - [ ] Upload validation tests:
    - [ ] Test upload with file exceeding max_file_size - returns 400
    - [ ] Test upload permission denied - returns 403
    - [ ] Test upload with invalid node_kind (not inheriting CoreFileObject) - returns 400
    - [ ] Test upload extracts correct file_name from upload
    - [ ] Test upload detects correct file_type (MIME)
    - [ ] Test upload calculates correct file_size
  - [ ] **Binary download tests:**
    - [ ] Test download binary file - returns exact bytes uploaded
    - [ ] Test download text file - returns exact content uploaded
    - [ ] Test downloaded content matches uploaded content (round-trip)
  - [ ] Download validation tests:
    - [ ] Test download with invalid identifier - returns 404
    - [ ] Test download permission denied - returns 403
    - [ ] Test response headers (Content-Type, Content-Disposition, Content-Length)

### Verification

- [ ] Run `uv run invoke lint` to check for issues
- [ ] Run `uv run invoke backend.test-unit` to run all tests
- [ ] Manual API testing with curl/httpie

## Reference Files

- `backend/infrahub/api/artifact.py` - Pattern for permission checks and storage access
- `backend/infrahub/api/storage.py` - Existing storage endpoints (reference for upload pattern)
- `backend/infrahub/api/dependencies.py` - Available dependencies
- `backend/infrahub/storage.py` - Storage layer (needs `retrieve_binary()` method added)

## API Endpoints

### Upload File

```
POST /api/file-object/{node_kind}/upload
Content-Type: multipart/form-data

file: <binary>

Response 200:
{
  "identifier": "uuid",
  "checksum": "md5-hash",
  "file_name": "original-filename.pdf",
  "file_size": 12345,
  "file_type": "application/pdf"
}

Response 400: File too large or invalid node_kind
Response 403: Permission denied
```

### Download File

```
GET /api/file-object/{node_kind}/object/{identifier}

Response 200:
Content-Type: application/pdf
Content-Disposition: attachment; filename="original-filename.pdf"
Content-Length: 12345
<binary content>

Response 404: File not found
Response 403: Permission denied
```

## Permission Model

- **Upload**: Requires `CREATE` permission on the specific `node_kind`
- **Download**: Requires `VIEW` permission on the specific `node_kind`
- Super admin bypasses permission checks

## Storage & Version Control

See [00-architecture.md](./00-architecture.md) for detailed architecture.

**Key points for implementation:**

1. **Upload creates new storage entry**
   - Each upload gets a new UUID (`storage_id`)
   - Call `registry.storage.store(identifier=storage_id, content=file_bytes)`
   - Return metadata to client for use when creating FileObject node

2. **Download retrieves from storage**
   - Call `registry.storage.retrieve(identifier=storage_id)`
   - Storage layer returns the file content

3. **No deduplication**
   - Each upload creates a new storage entry
   - Simpler implementation, no lookup needed

4. **Storage is immutable**
   - Files are never deleted or modified
   - Enables time travel to historical versions

## Notes

- The `node_kind` must inherit from `CoreFileObject` - validated at runtime
- File size validation prevents DoS via large file uploads
- Unlike `/api/storage`, these endpoints enforce permissions
- The returned metadata (storage_id, checksum, etc.) is used to create the FileObject node
