# Phase 5: REST API Validation

**Reference:** [dev/specs/2026-01-branch-freeze.md](../../specs/2026-01-branch-freeze.md)

**Status:** ✅ Complete

---

## Checklist

- [x] Block schema loading on merged branches (`backend/infrahub/api/schema.py`)
- [x] Block artifact generation on merged branches (`backend/infrahub/api/artifact.py`)
- [x] Extend functional tests (`backend/tests/functional/branch/test_branch_merged.py`)

---

## Implementation

### 5.1 Block schema loading on merged branches

**File:** `backend/infrahub/api/schema.py:328`

```python
from infrahub.core.branch.merged_status import check_merged_status

# In load_schema function:
check_need_rebase_status(branch)
check_merged_status(branch)  # Add this
```

### 5.2 Block artifact generation on merged branches

**File:** `backend/infrahub/api/artifact.py:82`

```python
from infrahub.core.branch.merged_status import check_merged_status

# In generate_artifact function:
check_need_rebase_status(branch_params.branch)
check_merged_status(branch_params.branch)  # Add this
```

---

## Tests

**Extend:** `backend/tests/functional/branch/test_branch_merged.py`

```python
async def test_schema_load_blocked_on_merged_branch(db, default_branch, api_client):
    """Test that schema loading is blocked on merged branches."""
    branch = await create_branch(db=db, name="merged-branch")
    branch.status = BranchStatus.MERGED
    await branch.save(db=db)

    response = await api_client.post(
        f"/api/schema/load?branch={branch.name}",
        json={"schemas": [...]}
    )
    assert response.status_code == 400
    assert "read-only" in response.json()["detail"]


async def test_artifact_generation_blocked_on_merged_branch(db, default_branch, api_client):
    """Test that artifact generation is blocked on merged branches."""
    branch = await create_branch(db=db, name="merged-branch")
    branch.status = BranchStatus.MERGED
    await branch.save(db=db)

    response = await api_client.post(
        f"/api/artifact/generate?branch={branch.name}",
        json={...}
    )
    assert response.status_code == 400
    assert "read-only" in response.json()["detail"]
```

---

## Verification

```bash
uv run pytest backend/tests/functional/branch/test_branch_merged.py -v -k "schema_load or artifact"
```
