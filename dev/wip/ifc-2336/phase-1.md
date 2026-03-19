# Phase 1: Configuration Settings

**Status:** ✅ Done
**Priority:** P1
**Requirements:** FR-001, FR-002, FR-011

---

## Goal

Add `delete_branch_after_merge` to `MainSettings` and `delete_git_branch_after_merge` to `GitSettings`. Both default to `False` to preserve backward compatibility (FR-011). Cross-field validation lives at the top-level `Settings` class since the two fields are in different sub-settings.

---

## Checklist

- [x] Add `delete_branch_after_merge` to `MainSettings`
- [x] Add `delete_git_branch_after_merge` to `GitSettings`
- [x] Add cross-field validator on `Settings` that rejects `git.delete_git_branch_after_merge=True` when `main.delete_branch_after_merge=False`
- [x] Write unit tests

---

## Implementation

### 1.1 Add `delete_branch_after_merge` to `MainSettings`

**File:** `backend/infrahub/config.py`

```python
class MainSettings(BaseSettings):
    # ... existing fields ...
    delete_branch_after_merge: bool = Field(
        default=False,
        description="When enabled, the Infrahub branch is automatically deleted after a successful merge.",
    )
```

### 1.2 Add `delete_git_branch_after_merge` to `GitSettings`

```python
class GitSettings(BaseSettings):
    # ... existing fields ...
    delete_git_branch_after_merge: bool = Field(
        default=False,
        description="When enabled, the corresponding Git branch is deleted after the Infrahub branch is deleted. "
        "Requires main.delete_branch_after_merge to be enabled.",
    )
```

### 1.3 Add cross-field validator to `Settings`

```python
class Settings(BaseSettings):
    # ... existing fields ...

    @model_validator(mode="after")
    def validate_git_branch_deletion_requires_branch_deletion(self) -> Self:
        if self.git.delete_git_branch_after_merge and not self.main.delete_branch_after_merge:
            raise ValueError(
                "'git.delete_git_branch_after_merge' requires 'main.delete_branch_after_merge' to be enabled"
            )
        return self
```

Pydantic raises `ValidationError` on load, which `load_and_exit()` catches, prints a descriptive error, and calls `sys.exit(1)` — the application will not start.

---

## Tests

**File:** `backend/tests/unit/test_config.py`

- `test_delete_branch_after_merge_defaults_to_false` — assert `MainSettings().delete_branch_after_merge is False`
- `test_delete_git_branch_after_merge_defaults_to_false` — assert `GitSettings().delete_git_branch_after_merge is False`
- `test_delete_git_branch_after_merge_without_delete_branch_after_merge_raises` — assert `ValidationError` is raised when `Settings(git={"delete_git_branch_after_merge": True}, main={"delete_branch_after_merge": False})`

**Verification:**

```bash
uv run pytest backend/tests/unit/test_config.py -v -k "delete_branch"
```
