# FileObject Architecture & Storage Design

This document explains the storage architecture and version control design for the FileObject feature.

## Design Decisions

Based on requirements discussion:

1. **No deduplication**: Each upload creates a new storage entry (simpler implementation)
2. **Storage is branch-agnostic**: Storage is a simple key-value store, branch awareness is at the node level
3. **CoreFileObject tracks all metadata**: No separate storage metadata layer needed

## Storage System Overview

### Current Architecture

The existing storage system (`backend/infrahub/storage.py`) is a simple key-value store:

```python
class InfrahubObjectStorage:
    def store(identifier: str, content: bytes) -> None  # Stores bytes
    def retrieve(identifier: str) -> str                # Returns decoded string (text only!)
```

**Characteristics:**
- Synchronous methods (current API routes are also sync)
- No delete method - storage entries are immutable
- No branch awareness - flat key-value store by UUID
- No deduplication - each upload gets new UUID

### Storage Layer Change Required: Binary Retrieval

**Issue:** Current `retrieve()` decodes bytes to string, which corrupts binary files.

**Solution:** Add `retrieve_binary()` method that returns raw bytes:

```python
def retrieve_binary(identifier: str) -> bytes:
    with self._storage.open(identifier) as f:
        return f.read()  # No .decode() - returns raw bytes
```

This allows:
- ✅ Store binary files (images, PDFs, etc.)
- ✅ Retrieve binary files without corruption
- ✅ Backward compatibility (keep `retrieve()` for existing text-based artifacts)

### How Branch Awareness Works

Storage itself is branch-agnostic, but **CoreFileObject nodes are branch-aware**:

1. Upload file → get `storage_id` (just a UUID in storage)
2. Create CoreFileObject node on a specific branch
3. The node has `storage_id` attribute pointing to the storage entry
4. Branch isolation comes from querying nodes, not storage

```
Storage Layer (branch-agnostic):
  "abc-123" → file bytes
  "def-456" → file bytes

Database Layer (branch-aware):
  Branch "main":     NetworkCircuitContract { storage_id: "abc-123" }
  Branch "feature":  NetworkCircuitContract { storage_id: "def-456" }
```

## Version Control Flow

### How Version Control Works

Version control is handled by Infrahub's database, not storage.

1. **Storage entries are immutable** - once stored, never modified or deleted
2. **FileObject nodes track references** - the `storage_id` attribute points to storage
3. **Database tracks changes over time** - when `storage_id` changes, database records it
4. **Time navigation via database** - query at time T returns `storage_id` as of time T

### File Upload

```
1. User uploads file via REST API
2. System generates new UUID as storage_id
3. System calculates checksum (SHA-1)
4. System extracts file metadata (name, size, type from upload)
5. File stored in storage backend
6. Return: storage_id, checksum, file_name, file_size, file_type
7. User creates FileObject node with returned metadata
```

**Note:** Step 7 creates the FileObject node via GraphQL mutation, passing `storage_id` to link it to the uploaded file. The `storage_id` attribute is NOT read-only, so it can be set via mutations. The other metadata attributes (`file_name`, `checksum`, `file_size`, `file_type`) are read-only and populated by the system based on the `storage_id`.

### File Update (New Version)

```
1. User uploads NEW file via REST API
2. System generates NEW storage_id (different UUID)
3. New file stored in storage (old file remains!)
4. User updates FileObject node's storage_id attribute
5. Database records the attribute change with timestamp
```

**Result:** Both old and new files exist in storage. Database knows which storage_id was valid at each point in time.

### Time Navigation

```
Query FileObject at time T1:
  → Database returns storage_id = "abc123" (old version)
  → Storage retrieves file from "abc123"

Query same FileObject at time T2:
  → Database returns storage_id = "xyz789" (new version)
  → Storage retrieves file from "xyz789"
```

Both storage entries exist forever, enabling time travel.

### Branch Workflow

```
1. Create branch "feature-x"
2. Upload new file → gets storage_id = "new-123"
3. Create/update FileObject on "feature-x" with storage_id = "new-123"
4. Main branch FileObject still has storage_id = "old-456"

On merge:
  - Database merges FileObject node changes
  - Storage entries are untouched
  - Both "new-123" and "old-456" remain in storage
```

## Implementation Requirements

### Storage Layer

- No storage model changes to `InfrahubObjectStorage` - remains a simple key-value store
- Each upload creates a new entry (no deduplication)
- **New method required:** Implement `retrieve_binary()` on `InfrahubObjectStorage` to return raw bytes (current `retrieve()` decodes to string, corrupting binary files)

### REST API Must Handle

- [ ] Generate UUID for new uploads
- [ ] Calculate checksum (SHA-1)
- [ ] Extract file metadata (name, size, type)
- [ ] Enforce file size limits (`config.SETTINGS.storage.max_file_size`)
- [ ] Store file via `registry.storage.store()`
- [ ] Retrieve file via `registry.storage.retrieve_binary()`
- [ ] Check permissions on the node kind

### Database Handles Version Control

- FileObject nodes are branch-aware (existing infrastructure)
- `storage_id` attribute tracked over time (existing infrastructure)
- No additional metadata layer needed

## Storage Considerations

### File Size

- New `max_file_size` config setting enforces limits
- Checked in REST API before storage write
- Large file handling depends on storage backend

### Async/Sync

- Storage methods are synchronous (unchanged)
- Current API routes are sync, but new file object API routes should be async
- FastAPI handles calling sync storage code from async endpoints via thread pool
- Database queries are async

### Storage Cleanup (Future)

Storage entries are never deleted for now:
- Enables time travel
- Prevents data loss
- Simple implementation

Future garbage collection would need to:
- Check all branches for references
- Consider time navigation requirements
- Handle merged branches

## Summary

| Concern | Where Handled | Changes Needed |
|---------|---------------|----------------|
| File storage | `InfrahubObjectStorage` | Add `retrieve_binary()` (PR 3) |
| Binary file support | Storage + REST API | New `retrieve_binary()` method (PR 3) |
| Version control | Infrahub Database | None (automatic) |
| Branch isolation | CoreFileObject nodes | None (automatic) |
| Time navigation | Infrahub Database | None (automatic) |
| File size limits | REST API + Config | New (PR 2 + PR 3) |
| Permissions | REST API + GraphQL | New (PR 3 + PR 5) |
| File metadata | CoreFileObject schema | New (PR 1) |
| GraphQL upload | Custom Upload scalar | New (PR 5) |

## GraphQL File Upload

### Current State

Infrahub's GraphQL app (`backend/infrahub/graphql/app.py`) **already supports multipart/form-data** (lines 485-525). It implements the GraphQL Multipart Request Spec, parsing `operations`, `map`, and file fields.

However:
- **No `Upload` scalar defined** - Graphene doesn't have a built-in Upload type
- **graphene-file-upload library is unmaintained** - Not an option

### Decision

**Implement a custom `Upload` scalar for Graphene** (PR 5).

This provides:
1. Single API for all operations (upload, CRUD, download metadata)
2. Consistent with GraphQL-first approach
3. No unmaintained dependencies
4. Leverages existing multipart parsing in the GraphQL app

### Upload Approach

**Both GraphQL and REST are single-step workflows.** File + data payload are provided together, and the system creates the node with all attributes in one operation.

| Method | Endpoint | Use Case |
|--------|----------|----------|
| GraphQL | Create/Update mutations with `file` parameter | Primary - single-step file + node creation |
| REST (optional) | `POST /api/file-object/{kind}/` with file + JSON payload | Fallback if needed; may be removed |

**Note:** All FileObject attributes (including `storage_id`) are read-only - the system sets them automatically when a file is uploaded.

### Workflow

**GraphQL Mutation (Single Step)**
```
mutation Create(data: {...}, file: $file) → creates node with file in one operation
```

**REST Upload (Single Step)**
```
POST /api/file-object/{kind}/ with multipart: file + JSON data payload → creates node with file in one operation
```

Both methods validate the data payload against the schema for the expected type.

**Download: REST Only**
```
GET /api/file-object/{kind}/object/{id} → downloads file binary
```

GraphQL returns metadata only; binary download uses REST.

## Open Questions

1. **Storage cleanup**: When/how to delete unreferenced storage entries?
   - Out of scope for initial implementation

2. **Deduplication**: Should we add deduplication later to save storage space?
   - Can be added in a future iteration if needed
   - Would require lookup by checksum before storing

## Future Enhancements

1. **MIME type filtering**: Add configuration option to allow or exclude uploads based on MIME type
   - Could be global setting (e.g., `storage.allowed_mime_types` or `storage.blocked_mime_types`)
   - Could also be per-FileObject-type setting in schema (e.g., only allow PDFs for `NetworkCircuitContract`)
   - Would use `puremagic` detection to enforce rules based on actual content, not just extension
