# PR 2: Configuration - max_file_size Setting

**Jira:** IFC-2152
**Branch:** `feature/file-object-config`
**Dependencies:** None (can be developed in parallel with PR 1)

## Overview

Add `max_file_size` configuration setting to StorageSettings to limit file upload sizes for FileObject types.

## Tasks

### Configuration Setting

- [ ] Modify `backend/infrahub/config.py`
  - [ ] Add `max_file_size` field to `StorageSettings` class:
    ```python
    max_file_size: int = Field(
        default=50,
        ge=1,
        description="Maximum file size in MB for file object uploads"
    )
    ```
  - [ ] Ensure the setting is documented in the class docstring

### Tests

- [ ] Create `backend/tests/unit/test_config_storage.py`
  - [ ] Test default value is 50 MB
  - [ ] Test minimum value validation (ge=1)
  - [ ] Test loading from TOML configuration file
  - [ ] Test environment variable override (`INFRAHUB_STORAGE_MAX_FILE_SIZE`)
  - [ ] Test value is accessible via `config.SETTINGS.storage.max_file_size`

### Documentation

- [ ] Update configuration documentation if needed (check `docs/` folder)

### Verification

- [ ] Run `uv run invoke backend.test-unit` to run all unit tests including new ones
- [ ] Run `uv run invoke backend.test-component` to run all component tests
- [ ] Manually test with environment variable:
  ```bash
  INFRAHUB_STORAGE_MAX_FILE_SIZE=50 uv run python -c "from infrahub import config; print(config.SETTINGS.storage.max_file_size)"
  ```

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
