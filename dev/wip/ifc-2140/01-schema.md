# PR 1: CoreFileObject Schema Definition

**Jira:** IFC-2151
**Branch:** `feature/file-object-schema`
**Dependencies:** None

## Overview

Add the CoreFileObject generic schema definition to the core schema. This is the foundation PR that defines the new generic with read-only attributes for file metadata.

## Tasks

### Schema Definition

- [ ] Create `backend/infrahub/core/schema/definitions/core/file_object.py`
  - [ ] Import required modules (`GenericSchema`, `AttributeSchema`, `AllowOverrideType`, `BranchSupportType`)
  - [ ] Define `core_file_object` GenericSchema with:
    - [ ] `file_name` attribute (Text, read_only=True, optional=False)
    - [ ] `checksum` attribute (Text, read_only=True, optional=False)
    - [ ] `file_size` attribute (Number, read_only=True, optional=False)
    - [ ] `file_type` attribute (Text, read_only=True, optional=False)
    - [ ] `storage_id` attribute (Text, optional=False) - NOT read_only so users can set it via mutations
  - [ ] Set `allow_override=AllowOverrideType.NONE` for all attributes
  - [ ] Add appropriate description and label

### Registration

- [ ] Modify `backend/infrahub/core/schema/definitions/core/__init__.py`
  - [ ] Add import: `from .file_object import core_file_object`
  - [ ] Add `core_file_object` to `core_models_mixed["generics"]` list

### Constants

- [ ] Modify `backend/infrahub/core/constants/infrahubkind.py`
  - [ ] Add `FILEOBJECT = "CoreFileObject"` constant

### Verification

- [ ] Run `uv run invoke backend.generate` to regenerate backend schema files
- [ ] Run `uv run invoke schema.generate-graphqlschema` to regenerate GraphQL schema
- [ ] Run `uv run invoke backend.test-unit` to ensure no regressions
- [ ] Run `uv run invoke backend.test-component` to ensure no regressions
- [ ] Manually verify CoreFileObject appears in generated schema

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
