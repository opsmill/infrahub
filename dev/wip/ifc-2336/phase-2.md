# Phase 2: Auto-delete Infrahub Branch After Merge

**Status:** ⬜ Todo
**Priority:** P1
**Requirements:** FR-003, FR-004, FR-006, FR-012, FR-014
**Depends on:** Phase 1

---

## Goal

After a successful merge (standard or proposed change), if `delete_branch_after_merge=True`, submit the existing `BRANCH_DELETE` workflow for the source branch. Reuse existing deletion infrastructure — no new deletion logic needed.

---

## Checklist

- [ ] Update `merge_branch()` to submit `BRANCH_DELETE` after successful merge
- [ ] Update `merge_proposed_change()` to submit `BRANCH_DELETE` after successful merge
- [ ] Guard against deleting the default branch (FR-014)
- [ ] Guard against deleting when other open proposed changes exist (edge case)
- [ ] Write functional tests

---

## Implementation

### 2.1 Standard branch merge

**File:** `backend/infrahub/core/branch/tasks.py`

In `merge_branch()`, after `obj.status = BranchStatus.MERGED` is saved and the registry is updated (the existing ifc-2184 block), add:

```python
from infrahub.config import get_settings

settings = get_settings()
if settings.main.delete_branch_after_merge and not obj.is_default:
    await get_workflow().submit_workflow(
        workflow=BRANCH_DELETE,
        context=context,
        parameters={"branch": obj.name},
    )
```

`BRANCH_DELETE` is already imported via the workflow catalogue. The existing `Branch.delete()` method already protects the default branch with a `ValidationError`, but `is_default` is checked here too as a defense-in-depth guard (FR-014).

### 2.2 Proposed change merge

**File:** `backend/infrahub/proposed_change/tasks.py`

In `merge_proposed_change()`, after the proposed change state transitions to `MERGED` and is saved, add:

```python
from infrahub.config import get_settings

settings = get_settings()
if settings.main.delete_branch_after_merge and not source_branch.is_default:
    # Only delete if no other open proposed changes still reference this branch
    open_pcs = await NodeManager.query(
        db=db,
        schema=InfrahubKind.PROPOSEDCHANGE,
        filters={
            "source_branch__value": source_branch.name,
            "state__value": ProposedChangeState.OPEN.value,
        },
    )
    if not open_pcs:
        await get_workflow().submit_workflow(
            workflow=BRANCH_DELETE,
            context=context,
            parameters={"branch": source_branch.name},
        )
```

The open PC check handles the edge case: a branch with multiple proposed changes should only be deleted after the last one merges.

---

## Tests

**New file:** `backend/tests/functional/branch/test_branch_delete_after_merge.py`

Pattern: `backend/tests/functional/branch/test_branch_merged.py`

- `test_branch_auto_deleted_after_standard_merge_when_config_enabled` — enable config, merge, assert branch gone
- `test_branch_not_deleted_after_standard_merge_when_config_disabled` — default config, merge, assert branch still exists with MERGED status
- `test_branch_auto_deleted_after_proposed_change_merge` — enable config, merge via PC, assert branch gone
- `test_branch_not_deleted_when_other_open_proposed_changes_exist` — enable config, create two PCs for same branch, merge one, assert branch still exists

**Verification:**

```bash
uv run pytest backend/tests/functional/branch/test_branch_delete_after_merge.py -v
```
