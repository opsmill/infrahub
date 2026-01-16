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
- Synchronous methods (called from async FastAPI endpoints)
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
3. System calculates checksum (MD5)
4. System extracts file metadata (name, size, type from upload)
5. File stored in storage backend
6. Return: storage_id, checksum, file_name, file_size, file_type
7. User creates FileObject node with returned metadata
```

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

- **No changes needed** to `InfrahubObjectStorage`
- Storage remains a simple key-value store
- Each upload creates a new entry (no deduplication)

### REST API Must Handle

- [ ] Generate UUID for new uploads
- [ ] Calculate checksum (MD5)
- [ ] Extract file metadata (name, size, type)
- [ ] Enforce file size limits (`config.SETTINGS.storage.max_file_size`)
- [ ] Store file via `registry.storage.store()`
- [ ] Retrieve file via `registry.storage.retrieve()`
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
- FastAPI handles calling sync code
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
| Permissions | REST API | New (PR 3) |
| File metadata | CoreFileObject schema | New (PR 1) |

## GraphQL File Upload Consideration

### Current State

Infrahub's GraphQL app (`backend/infrahub/graphql/app.py`) **already supports multipart/form-data** (lines 485-525). It implements the GraphQL Multipart Request Spec, parsing `operations`, `map`, and file fields.

However:
- **No `Upload` scalar defined** - Graphene doesn't have a built-in Upload type
- **graphene-file-upload library is unmaintained** - No updates in 12+ months
- Would need to define a custom `Upload` scalar to accept files in mutations

### Options

| Option | Pros | Cons |
|--------|------|------|
| **REST API only** | Simple, well-understood, already planned | Two APIs (REST for upload, GraphQL for CRUD) |
| **GraphQL with custom Upload scalar** | Single API, consistent with mutations | Extra work, custom scalar needed |
| **graphene-file-upload library** | Ready-made solution | Unmaintained dependency |

### Recommendation

**Use REST API for file upload/download, GraphQL for FileObject CRUD.**

Reasons:
1. REST is natural for file transfers (binary data, streaming, progress)
2. GraphQL mutations handle the FileObject metadata (storage_id, relationships)
3. Avoids adding unmaintained dependency
4. Simpler implementation

### Workflow with REST + GraphQL

```
1. POST /api/file-object/{kind}/upload → returns {identifier, checksum, ...}
2. mutation FileObjectCreate(data: {storage_id: "...", ...}) → creates node
3. GET /api/file-object/{kind}/object/{id} → downloads file
```

This is similar to how other systems (S3 + metadata DB, GitHub releases) work.

## Open Questions

1. **Storage cleanup**: When/how to delete unreferenced storage entries?
   - Out of scope for initial implementation

2. **GraphQL file upload**: Should we add a custom Upload scalar for GraphQL mutations?
   - Recommendation: Not for initial implementation, REST is sufficient
   - Can be added later if needed

3. **Deduplication**: Should we add deduplication later to save storage space?
   - Can be added in a future iteration if needed
   - Would require lookup by checksum before storing
