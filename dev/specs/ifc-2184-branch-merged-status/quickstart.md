# Quickstart: Branch Freeze (MERGED Status)

**Feature**: IFC-2184 | **Date**: 2026-04-24

This guide shows how to verify the Branch Freeze feature end-to-end.

## Prerequisites

- A running Infrahub instance (local dev or Docker)
- Admin credentials

---

## 1. Verify Branch Status After Merge

Create a branch, make a change, then merge it.

```graphql
# Step 1: Create a branch
mutation {
  BranchCreate(data: { name: "test-freeze" }) {
    ok
    object { name status }
  }
}

# Step 2: Merge the branch
mutation {
  BranchMerge(data: { name: "test-freeze" }) {
    ok
  }
}

# Step 3: Query the branch status — should be MERGED
query {
  Branch(name: "test-freeze") {
    name
    status
  }
}
```

**Expected**: `status` is `"MERGED"`.

---

## 2. Verify Mutations Are Blocked

With the `test-freeze` branch now MERGED, attempt any mutation on it:

```graphql
mutation {
  CoreTagCreate(
    data: { name: { value: "blocked" } }
    branch: "test-freeze"
  ) {
    ok
  }
}
```

**Expected**: Error response containing `"has been merged and is read-only"`.

---

## 3. Verify BranchDelete Still Works

```graphql
mutation {
  BranchDelete(data: { name: "test-freeze" }) {
    ok
  }
}
```

**Expected**: `ok: true`.

---

## 4. Verify Re-merge Is Blocked

Re-create the branch and merge it again to test the double-merge guard:

```graphql
mutation {
  BranchCreate(data: { name: "test-remerge" }) { ok }
}
mutation {
  BranchMerge(data: { name: "test-remerge" }) { ok }
}
# Now try to merge again
mutation {
  BranchMerge(data: { name: "test-remerge" }) { ok }
}
```

**Expected**: Third mutation returns an error containing `"has already been merged"`.

---

## 5. Verify ProposedChange Is Blocked

```graphql
mutation {
  BranchCreate(data: { name: "test-pc-block" }) { ok }
}
mutation {
  BranchMerge(data: { name: "test-pc-block" }) { ok }
}
# Now try to create a proposed change for the merged branch
mutation {
  CoreProposedChangeCreate(data: {
    name: { value: "blocked-pc" }
    source_branch: { value: "test-pc-block" }
    destination_branch: { value: "main" }
  }) { ok }
}
```

**Expected**: Error containing `"has been merged"`.

---

## 6. Verify REST API Is Blocked

```bash
# Schema load on merged branch should return 422
curl -X POST "http://localhost:8000/api/schema/load?branch=test-freeze" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"schemas": []}'
```

**Expected**: HTTP 422 with `"read-only"` in the response body.

---

## 7. Run the Tests

```bash
# Unit tests
uv run pytest backend/tests/unit/core/branch/test_merged_status.py \
              backend/tests/unit/branch/test_status_checker.py \
              backend/tests/unit/permissions/test_merged_branch_permissions.py -v

# Functional tests
uv run pytest backend/tests/functional/branch/test_branch_merged.py -v

# Component tests (REST API)
uv run pytest backend/tests/component/api/test_40_schema.py -v -k "merged or rebase"
uv run pytest backend/tests/component/api/test_11_artifact.py -v -k "merged or rebase"
```

**Expected**: All tests pass.

---

## 8. Verify UI Behavior

1. Navigate to the Branches list in the UI.
2. Merge a branch via a proposed change or the `BranchMerge` mutation.
3. Refresh the branch list.

**Expected**:
- The branch shows a `MERGED` badge with distinct styling.
- Merge, Rebase, Validate, and Refresh Diff buttons are disabled or hidden.
- The Delete button remains active.
- When creating a new Proposed Change, the merged branch does not appear in the source branch dropdown.
