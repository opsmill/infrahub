# Phase 1: Configuration Settings

**Status:** ✅ Done
**Priority:** P1
**Requirements:** FR-001, FR-002, FR-011

---

## Goal

Add two global configuration settings to `MainSettings`. Both default to `False` to preserve backward compatibility (FR-011).

---

## Checklist

- [x] Add `delete_branch_after_merge` to `MainSettings`
- [x] Add `delete_git_branch_after_merge` to `MainSettings`
- [x] Add cross-field validator that rejects `delete_git_branch_after_merge=True` when `delete_branch_after_merge=False`
- [x] Write unit tests

---

## Implementation

### 1.1 Add settings and validator to MainSettings

**File:** `backend/infrahub/config.py`

Locate the `MainSettings` class and add two new fields plus a `@model_validator`:

```python
from pydantic import model_validator
from typing import Self

class MainSettings(BaseSettings):
    # ... existing fields ...
    delete_branch_after_merge: bool = False
    delete_git_branch_after_merge: bool = False

    @model_validator(mode="after")
    def validate_git_branch_deletion_requires_branch_deletion(self) -> Self:
        if self.delete_git_branch_after_merge and not self.delete_branch_after_merge:
            raise ValueError(
                "'delete_git_branch_after_merge' requires 'delete_branch_after_merge' to be enabled"
            )
        return self
```

Pydantic raises `ValidationError` on load, which `load_and_exit()` catches, prints a descriptive error, and calls `sys.exit(1)` — the application will not start.

---

## Tests

**File:** `backend/tests/unit/test_config.py`

- `test_delete_branch_after_merge_defaults_to_false` — assert `MainSettings().delete_branch_after_merge is False`
- `test_delete_git_branch_after_merge_defaults_to_false` — assert `MainSettings().delete_git_branch_after_merge is False`
- `test_delete_git_branch_after_merge_without_delete_branch_after_merge_raises` — assert `ValidationError` is raised when `delete_git_branch_after_merge=True, delete_branch_after_merge=False`

**Verification:**

```bash
uv run pytest backend/tests/unit/test_config.py -v -k "delete_branch"
```
