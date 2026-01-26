# PR 2: Configuration - max_file_size Setting

**Jira:** IFC-2152
**Branch:** `feature/file-object-config`
**Dependencies:** None (can be developed in parallel with PR 1)

## Overview

Add `max_file_size` configuration setting to StorageSettings to limit file upload sizes for FileObject types.

## Tasks

### Configuration Setting

- [x] Modify `backend/infrahub/config.py`
  - [x] Add `max_file_size` field to `StorageSettings` class:
    ```python
    max_file_size: int = Field(default=50, ge=1, description="Maximum file size in MB for file uploads")
    ```

### Tests

- [x] Add tests to `backend/tests/unit/test_config.py`:
  - [x] `test_storage_max_file_size` - default value, custom value, minimum allowed
  - [x] `test_storage_max_file_size_rejects_invalid_values` - parametrized for 0 and -10
  - [x] `test_storage_max_file_size_environment_variable` - env var override and global settings access

### Documentation

- [x] Run `uv run invoke docs.generate` to regenerate configuration documentation

### Verification

- [x] Run `uv run pytest backend/tests/unit/test_config.py -v` - all tests pass
- [x] Run `uv run invoke backend.test-unit` to run all unit tests including new ones
- [x] Run `uv run invoke backend.test-component` to run all component tests

## Reference Files

- `backend/infrahub/config.py` - Existing configuration patterns
- `backend/tests/unit/test_config.py` - Existing config tests (if present)

## Configuration Example

After this PR, users can configure in `infrahub.toml`:

```toml
[storage]
driver = "local"
max_file_size = 50  # in MB
```

Or via environment variable:

```bash
export INFRAHUB_STORAGE_MAX_FILE_SIZE=50
```

## Notes

- Default of 50 MB aligns with spec recommendation for "small file objects"
- Minimum of 1 MB prevents misconfiguration
- This setting will be used by the REST API in PR 3 to validate upload size
