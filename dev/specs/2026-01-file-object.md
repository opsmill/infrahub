---
Title: File object feature
Author:
  - Wim Van Deun
  - Yvonne Jouffrault
  - Guillaume Mazoyer
Status: implemented
JPD: INFP-403
---

# File object feature

## Overview

The FileObject feature allows users to upload files and link them to other objects in Infrahub. Users define their own file object types by inheriting from `CoreFileObject`, which provides automatic file metadata tracking (filename, size, checksum, MIME type) and integration with Infrahub's version control and permission systems.

## Backend

### Schema

#### CoreFileObject generic

The `CoreFileObject` generic provides the base attributes for all file objects. Custom file object types must inherit from this generic.

```yaml
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
---
version: "1.0"
generics:
  - name: FileObject
    namespace: Core
    attributes:
      - name: file_name
        kind: Text
        read_only: true
        optional: false
      - name: checksum
        kind: Text
        read_only: true
        optional: false
      - name: file_size
        kind: Number
        read_only: true
        optional: false
      - name: file_type
        kind: Text
        read_only: true
        optional: false
      - name: storage_id
        kind: Text
        read_only: true
        optional: false
```

**Attributes:**

| Attribute | Description |
|-----------|-------------|
| `file_name` | Original filename as uploaded by the user |
| `checksum` | SHA-1 checksum calculated on the uploaded file |
| `file_size` | File size in bytes |
| `file_type` | MIME type detected from file content using magic bytes (via `puremagic`) |
| `storage_id` | UUID of the file in Infrahub's storage system (UUIDT format) |

All attributes are read-only and system-managed. When a file is uploaded, the system automatically populates all attributes.

#### User-defined file object type

Users define their own file object types in their schema by inheriting from `CoreFileObject`:

```yaml
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
---
version: "1.0"
nodes:
  - name: CircuitContract
    namespace: Network
    inherit_from:
      - CoreFileObject
    attributes:
      - name: contract_start
        kind: DateTime
        optional: false
      - name: contract_end
        kind: DateTime
        optional: false
    relationships:
      - name: signed_by
        peer: CoreAccount
        kind: Attribute
        cardinality: one
        optional: true
      - name: circuit
        peer: NetworkCircuit
        kind: Attribute
        cardinality: one
        optional: true
```

FileObjects can be related to other objects using standard Infrahub relationships:

```yaml
  - name: Circuit
    namespace: Network
    attributes:
      - name: circuit_id
        kind: Text
        optional: false
    relationships:
      - name: contracts
        peer: NetworkCircuitContract
        kind: Generic
        cardinality: many
        optional: true
```

### Storage Architecture

#### Design Principles

1. **Immutable storage**: Once stored, files are never modified or deleted (enables time travel)
2. **Branch-agnostic storage**: Storage is a simple key-value store; branch awareness is at the node level
3. **No deduplication**: Each upload creates a new storage entry with a unique UUID

#### How Branch Awareness Works

Storage itself is branch-agnostic, but **CoreFileObject nodes are branch-aware**:

```
Storage Layer (branch-agnostic):
  "abc-123" → file bytes (original version)
  "def-456" → file bytes (updated version)

Database Layer (branch-aware):
  Branch "main":     NetworkCircuitContract { storage_id: "abc-123" }
  Branch "feature":  NetworkCircuitContract { storage_id: "def-456" }
```

When a file is updated on a branch:
1. New file is stored with a new `storage_id` (UUID)
2. The node's `storage_id` attribute is updated on that branch
3. Main branch still references the original `storage_id`
4. Both files remain in storage, enabling version control and time travel

#### Time Navigation

Both storage entries exist forever, enabling time travel:

```
Query FileObject at time T1:
  → Database returns storage_id = "abc123" (old version)
  → Storage retrieves file from "abc123"

Query same FileObject at time T2:
  → Database returns storage_id = "xyz789" (new version)
  → Storage retrieves file from "xyz789"
```

### Version Control

File objects support full version control:

- **Branching**: Create/update file objects on branches; changes isolated until merged
- **Time travel**: Query file objects at any point in time using the `at` parameter
- **Proposed changes**: File object changes can be reviewed and merged via proposed changes
- **Branch-agnostic option**: Users can define file objects as branch-agnostic if needed

**Known limitation**: Merge conflicts on file objects work at the attribute level, not object level. It's possible to select mismatched `checksum` and `storage_id` values during conflict resolution. Object-level conflict resolution is planned for a future release.

### Permission System

File objects integrate with Infrahub's permission system:

- VIEW permission required to download files via REST API
- CREATE/UPDATE permissions required for mutations
- The legacy `/api/storage/object/` endpoint rejects FileObject access, directing users to the permission-checked endpoints

### File Size Limitation

Configure maximum file size in `infrahub.toml`:

```toml
[storage]
driver = "local"
max_file_size = 50  # in MB, default is 50
```

File size is validated before storage. Uploads exceeding the limit are rejected with a clear error message.

#### Production Deployment: Reverse Proxy Limits

For production, configure file size limits at the reverse proxy level:

**nginx:**
```nginx
client_max_body_size 200M;
```

**Traefik:**
```yaml
http:
  middlewares:
    limit-body:
      buffering:
        maxRequestBodyBytes: 209715200  # 200MB
```

### GraphQL API

#### Querying File Objects

Query all file objects using the generic:

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

Query specific file object types:

```graphql
query {
  NetworkCircuitContract {
    edges {
      node {
        id
        file_name { value }
        file_size { value }
        file_type { value }
        checksum { value }
        contract_start { value }
        contract_end { value }
        circuit {
          node { id }
        }
      }
    }
  }
}
```

#### Mutations

##### Create with File Upload

```graphql
mutation($file: Upload!) {
  NetworkCircuitContractCreate(
    data: {
      contract_start: { value: "2026-01-01" }
      contract_end: { value: "2026-12-31" }
      signed_by: { id: "account-uuid" }
    }
    file: $file
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

##### Update with New File

```graphql
mutation($file: Upload!) {
  NetworkCircuitContractUpdate(
    data: {
      id: "contract-uuid"
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

##### Upsert with File

```graphql
mutation($file: Upload!) {
  NetworkCircuitContractUpsert(
    data: {
      hfid: ["contract-2026.pdf"]
      contract_start: { value: "2026-01-01" }
      contract_end: { value: "2026-12-31" }
    }
    file: $file
  ) {
    ok
    object {
      id
      storage_id { value }
    }
  }
}
```

**Note:** Upsert is idempotent - if the uploaded file has the same checksum as the existing file, no new storage entry is created.

#### GraphQL Multipart Request Format

File uploads use the [GraphQL Multipart Request Spec](https://github.com/jaydenseric/graphql-multipart-request-spec):

```bash
curl -X POST http://localhost:8000/graphql \
  -H "X-INFRAHUB-KEY: your-api-token" \
  -F 'operations={"query": "mutation($file: Upload!) { NetworkCircuitContractCreate(data: { contract_start: { value: \"2026-01-01\" }, contract_end: { value: \"2026-12-31\" } }, file: $file) { ok object { id file_name { value } checksum { value } } } }", "variables": { "file": null }}' \
  -F 'map={"0": ["variables.file"]}' \
  -F '0=@/path/to/contract.pdf'
```

### REST API

#### Download Endpoints

Three download endpoints are available, all requiring VIEW permission:

##### Download by Node ID (Primary)

```
GET /api/storage/files/{node_id}?branch={branch}&preview={true|false}

Response headers:
- Content-Type: <file_type from node>
- Content-Disposition: attachment; filename="<filename>"

Response: <binary content>
```

##### Download by HFID

```
GET /api/storage/files/by-hfid/{kind}?hfid={value1}&hfid={value2}&branch={branch}

Example: GET /api/storage/files/by-hfid/NetworkCircuitContract?hfid=contract-2026.pdf
```

##### Download by Storage ID

```
GET /api/storage/files/by-storage-id/{storage_id}?branch={branch}
```

**Query Parameters:**

| Parameter | Description |
|-----------|-------------|
| `branch` | Branch name (optional, defaults to current branch) |
| `preview` | If `true`, returns `Content-Disposition: inline` for browser preview |

**Response Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 401 | Unauthorized |
| 403 | Permission denied |
| 404 | Not found |

#### Download Examples

```bash
# Download by node ID
curl -H "X-INFRAHUB-KEY: your-token" \
  "http://localhost:8000/api/storage/files/abc123-node-uuid" \
  -o contract.pdf

# Download from a specific branch
curl -H "X-INFRAHUB-KEY: your-token" \
  "http://localhost:8000/api/storage/files/abc123-node-uuid?branch=feature-branch" \
  -o contract.pdf

# Preview in browser (inline disposition)
curl -H "X-INFRAHUB-KEY: your-token" \
  "http://localhost:8000/api/storage/files/abc123-node-uuid?preview=true"
```

## Python SDK

The Python SDK provides a streamlined API for working with file objects through methods on the node objects themselves.

### Creating a File Object

```python
from pathlib import Path
from infrahub_sdk import InfrahubClient

async def create_contract():
    client = InfrahubClient()

    # Create the file object node
    contract = await client.create(
        kind="NetworkCircuitContract",
        data={
            "contract_start": "2026-01-01",
            "contract_end": "2026-12-31",
        },
    )

    # Option 1: Upload from file path (streams from disk - memory efficient)
    contract.upload_from_path(path=Path("/tmp/contract.pdf"))

    # Option 2: Upload from bytes (for small files or dynamic content)
    # contract.upload_from_bytes(content=b"file content", name="contract.pdf")

    # Option 3: Upload from file-like object (streams)
    # with open("/tmp/contract.pdf", "rb") as f:
    #     contract.upload_from_bytes(content=f, name="contract.pdf")

    # Save uploads the file and creates the node
    await contract.save()

    print(f"Created contract: {contract.id}")
    print(f"File name: {contract.file_name.value}")
    print(f"Checksum: {contract.checksum.value}")
```

### Downloading a File

```python
from pathlib import Path
from infrahub_sdk import InfrahubClient

async def download_contract(contract_id: str):
    client = InfrahubClient()

    # Fetch the file object
    contract = await client.get(kind="NetworkCircuitContract", id=contract_id)

    # Option 1: Download to memory (for small files)
    content = await contract.download_file()
    print(f"Downloaded {len(content)} bytes")

    # Option 2: Stream to disk (memory efficient for large files)
    dest = Path("/tmp/downloaded-contract.pdf")
    bytes_written = await contract.download_file(dest=dest)
    print(f"Saved {bytes_written} bytes to {dest}")
```

### Updating a File

```python
from pathlib import Path
from infrahub_sdk import InfrahubClient

async def update_contract(contract_id: str):
    client = InfrahubClient()

    # Fetch existing contract
    contract = await client.get(kind="NetworkCircuitContract", id=contract_id)

    # Upload new file version
    contract.upload_from_path(path=Path("/tmp/updated-contract.pdf"))

    # Save updates the file and node
    await contract.save()

    print(f"Updated storage_id: {contract.storage_id.value}")
```

### Working with Branches

```python
from pathlib import Path
from infrahub_sdk import InfrahubClient

async def branch_workflow():
    client = InfrahubClient()

    # Create contract on main branch
    contract = await client.create(
        kind="NetworkCircuitContract",
        data={"contract_start": "2026-01-01", "contract_end": "2026-12-31"},
    )
    contract.upload_from_bytes(content=b"Main branch content", name="contract.pdf")
    await contract.save()
    contract_id = contract.id

    # Create a branch
    branch = await client.branch.create(branch_name="update-contract")

    # Update contract on the branch
    branch_client = client.clone(branch=branch.name)
    branch_contract = await branch_client.get(kind="NetworkCircuitContract", id=contract_id)
    branch_contract.upload_from_bytes(content=b"Branch content", name="updated.pdf")
    await branch_contract.save()

    # Verify isolation: main branch still has original file
    main_contract = await client.get(kind="NetworkCircuitContract", id=contract_id)
    main_content = await main_contract.download_file()
    assert main_content == b"Main branch content"

    # Branch has updated file
    branch_content = await branch_contract.download_file()
    assert branch_content == b"Branch content"
```

### Complete Example Script

```python
#!/usr/bin/env python3
"""Example script demonstrating FileObject operations with the Infrahub SDK."""

import asyncio
from pathlib import Path
from infrahub_sdk import InfrahubClient


async def main():
    client = InfrahubClient()

    # 1. Create a file object with upload
    print("Creating contract...")
    contract = await client.create(
        kind="NetworkCircuitContract",
        data={
            "contract_start": "2026-01-01",
            "contract_end": "2026-12-31",
        },
    )
    contract.upload_from_bytes(
        content=b"Service Level Agreement\n\nTerms and conditions...",
        name="sla-2026.txt",
    )
    await contract.save()

    print(f"  ID: {contract.id}")
    print(f"  File: {contract.file_name.value}")
    print(f"  Size: {contract.file_size.value} bytes")
    print(f"  Type: {contract.file_type.value}")
    print(f"  Checksum: {contract.checksum.value}")

    # 2. Download the file
    print("\nDownloading contract...")
    content = await contract.download_file()
    print(f"  Content: {content.decode()[:50]}...")

    # 3. Update with a new file
    print("\nUpdating contract with new file...")
    contract_to_update = await client.get(kind="NetworkCircuitContract", id=contract.id)
    contract_to_update.upload_from_bytes(
        content=b"Updated Service Level Agreement\n\nRevised terms...",
        name="sla-2026-v2.txt",
    )
    await contract_to_update.save()

    # Re-fetch to see updated values
    updated = await client.get(kind="NetworkCircuitContract", id=contract.id)
    print(f"  New file: {updated.file_name.value}")
    print(f"  New checksum: {updated.checksum.value}")

    # 4. Download to disk
    print("\nDownloading to disk...")
    dest = Path("/tmp/downloaded-sla.txt")
    bytes_written = await updated.download_file(dest=dest)
    print(f"  Saved {bytes_written} bytes to {dest}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Synchronous API

The SDK also provides synchronous methods:

```python
from pathlib import Path
from infrahub_sdk import InfrahubClientSync

client = InfrahubClientSync()

# Create
contract = client.create(kind="NetworkCircuitContract", data={...})
contract.upload_from_path(path=Path("/tmp/contract.pdf"))
contract.save()

# Download
content = contract.download_file()
# or
contract.download_file(dest=Path("/tmp/output.pdf"))
```

### SDK Method Reference

| Method | Description |
|--------|-------------|
| `node.upload_from_path(path)` | Select file from disk for upload (streamed) |
| `node.upload_from_bytes(content, name)` | Set content for upload (bytes or BinaryIO) |
| `node.download_file()` | Download to memory, returns `bytes` |
| `node.download_file(dest=Path)` | Stream to disk, returns bytes written |
| `node.is_file_object()` | Check if node inherits from CoreFileObject |
| `node.clear_file()` | Clear pending file content before save |

## Future Considerations

- **External storage**: Support FileObjects where the actual file is stored in an external system
- **Permission inheritance**: Automatically inherit permissions from related objects
- **Artifacts consolidation**: Explore overlap with the existing Artifacts feature
- **MIME type filtering**: Per-type restrictions (e.g., only PDFs for contracts)
- **Global MIME filters**: `storage.allowed_mime_types` or `storage.blocked_mime_types` config options
- **Storage cleanup**: Garbage collection for unreferenced storage entries
- **Deduplication**: Optional deduplication by checksum to save storage space

## Frontend Scope

> **Status:** Not yet implemented. This section contains requirements and placeholders for frontend work.

### Requirements

#### Schema-Driven Display

- FileObjects behave like standard Infrahub objects (list view, detail view)
- Detail view renders file content preview for supported types (similar to artifacts)
- Create/update forms include a file upload widget

#### Key Considerations

- **Permission-aware**: Show Upload/Edit/Delete based on user permissions
- **Branch-aware**: Display file objects for current branch context
- **Error handling**: File size exceeded, upload failures, permission denied
- **Loading states**: Upload progress, file preview loading

### Implementation Details

<!-- TODO: Update this section when frontend implementation is complete -->

#### Components

<!-- TODO: List the React components created for FileObject support -->

| Component | Location | Description |
|-----------|----------|-------------|
| <!-- TODO --> | <!-- TODO --> | <!-- TODO --> |

#### API Integration

The frontend uses the following APIs:

| Operation | API | Notes |
|-----------|-----|-------|
| Query file objects | GraphQL `CoreFileObject` / specific type queries | Standard GraphQL queries |
| Create with file | GraphQL mutation with `file: Upload!` parameter | Uses multipart/form-data |
| Update with file | GraphQL mutation with optional `file: Upload` | Uses multipart/form-data |
| Download file | `GET /api/storage/files/{node_id}` | Binary download |
| Preview file | `GET /api/storage/files/{node_id}?preview=true` | Inline display |

<!-- TODO: Document how multipart uploads are implemented in the frontend -->

#### File Upload Widget

<!-- TODO: Document the file upload widget implementation -->

- Drag and drop support: <!-- TODO -->
- File size validation (client-side): <!-- TODO -->
- Progress indicator: <!-- TODO -->
- Supported file types display: <!-- TODO -->

#### File Preview

<!-- TODO: Document file preview implementation -->

Supported preview types:
- Images (PNG, JPEG, GIF, SVG): <!-- TODO -->
- PDF documents: <!-- TODO -->
- Text files: <!-- TODO -->
- Other: <!-- TODO -->

#### Error Handling

<!-- TODO: Document error handling UI -->

| Error | User Message | UI Behavior |
|-------|--------------|-------------|
| File too large | <!-- TODO --> | <!-- TODO --> |
| Upload failed | <!-- TODO --> | <!-- TODO --> |
| Permission denied | <!-- TODO --> | <!-- TODO --> |
| Download failed | <!-- TODO --> | <!-- TODO --> |

### Open Questions

- Should "delete file" allow saving the FileObject without a file, or require deleting the entire object?
- What metadata to display (file size, upload date, type, uploader)?
- Should preview/replace/delete be available inline in detail view or only in edit modal?
- For cardinality "many" relationships, should min/max constraints be supported?

### Testing

<!-- TODO: Document frontend tests -->

#### Unit Tests

<!-- TODO: List unit test files -->

#### E2E Tests

<!-- TODO: List E2E test scenarios -->
