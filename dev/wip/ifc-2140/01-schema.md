# PR 1: CoreFileObject Schema Definition

**Jira:** IFC-2151
**Branch:** `feature/file-object-schema`
**Dependencies:** None

## Overview

Add the CoreFileObject generic schema definition to the core schema. This is the foundation PR that defines the new generic with read-only attributes for file metadata.

## Tasks

### Schema Definition

- [x] Create `backend/infrahub/core/schema/definitions/core/file_object.py`
  - [x] Import required modules (`GenericSchema`, `AttributeSchema`, `AllowOverrideType`)
  - [x] Define `core_file_object` GenericSchema with:
    - [x] `file_name` attribute (Text, read_only=True, optional=False)
    - [x] `checksum` attribute (Text, read_only=True, optional=False)
    - [x] `file_size` attribute (Number, read_only=True, optional=False)
    - [x] `file_type` attribute (Text, read_only=True, optional=False)
    - [x] `storage_id` attribute (Text, optional=False) - NOT read_only so users can set it via mutations
  - [x] Set `allow_override=AllowOverrideType.NONE` for all attributes
  - [x] Add appropriate description and label

### Registration

- [x] Modify `backend/infrahub/core/schema/definitions/core/__init__.py`
  - [x] Add import: `from .file_object import core_file_object`
  - [x] Add `core_file_object` to `core_models_mixed["generics"]` list

### Constants

- [x] Modify `backend/infrahub/core/constants/infrahubkind.py`
  - [x] Add `FILEOBJECT = "CoreFileObject"` constant

### Verification

- [x] Run `uv run invoke backend.generate` to regenerate backend schema files
- [x] Run `uv run invoke schema.generate-graphqlschema` to regenerate GraphQL schema
- [x] Run `uv run invoke backend.test-unit` to ensure no regressions
- [x] Run `uv run invoke backend.test-component` to ensure no regressions
- [x] Manually verify CoreFileObject appears in generated schema

## Reference Files

- `backend/infrahub/core/schema/definitions/core/artifact.py` - Pattern for GenericSchema with storage_id
- `backend/infrahub/core/schema/definitions/core/lineage.py` - Pattern for read-only attributes

## Tests

**No tests required** - Per spec, schema inheritance is already well-tested.

## Notes

- `file_name`, `checksum`, `file_size`, `file_type` are marked `read_only=True` because they are system-managed (computed from uploaded file)
- `storage_id` is NOT read_only - users must set it via mutations to link the node to an uploaded file
- All attributes are marked `optional=False` because they are required for a valid file object
- `allow_override=AllowOverrideType.NONE` prevents inheriting schemas from overriding these attributes

**Note:** The `storage_id` attribute only needs to remain writable (not read-only) if we keep the REST upload as an option. If we end up using only the GraphQL combined mutation approach (with `file` parameter), `storage_id` could be made read-only since the system would set it automatically.
