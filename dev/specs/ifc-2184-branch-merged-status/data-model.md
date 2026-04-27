# Data Model: Branch Freeze (MERGED Status)

**Feature**: IFC-2184 | **Date**: 2026-04-24

## Entities

### Branch

An isolated copy of the Infrahub data graph with version-controlled state. The `status` field governs what operations are permitted on the branch.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique branch identifier |
| `status` | `BranchStatus` | Current lifecycle state |
| `is_default` | boolean | True only for the main branch |
| `description` | string | Optional human-readable note |

**Status enum values:**

| Value | Meaning | Mutations allowed |
|-------|---------|-------------------|
| `OPEN` | Active, writable | All |
| `NEED_REBASE` | Behind main; must rebase before changes | BranchRebase, BranchDelete, BranchCreate, ProposedChangeCreate |
| `NEED_UPGRADE_REBASE` | Schema version behind; must upgrade | BranchDelete |
| `DELETING` | Deletion in progress | None (internal) |
| `MERGED` | Merged into main; read-only | BranchDelete only |

### Status Transitions

```text
OPEN ─────────────────────────────────────────► MERGED (terminal)
  │                                               ↑
  ├──► NEED_REBASE ──(after rebase)──► OPEN ──────┤
  │                                               │
  ├──► NEED_UPGRADE_REBASE                        │
  │                                               │
  └──► DELETING (on delete)          merge_branch() sets MERGED
                                     as final step
```

`MERGED` is a **terminal** state — no transition back to `OPEN`.

### BranchStatusChecker

Internal service class that enforces status constraints. Not a stored entity.

| Method | Raises | When |
|--------|--------|------|
| `check_merge_status(branch)` | `BranchAlreadyMergedError` | `branch.status == MERGED` |
| `check_needs_rebase_status(branch)` | `BranchNeedsRebaseError` | `branch.status == NEED_REBASE` |
| `check(branch)` | Either of the above | Either condition applies |

**Location**: `backend/infrahub/branch/status_checker.py`

### ProposedChange (relationship to Branch)

A proposed change references a `source_branch`. When the source branch transitions to `MERGED`:
- The proposed change is automatically moved to `cancelled` state.
- New proposed changes cannot be created with a `MERGED` source branch.

| Field | Type | Constraint added by this feature |
|-------|------|----------------------------------|
| `source_branch` | string | Must not reference a `MERGED` branch |
| `state` | enum | Auto-set to `cancelled` when source branch is merged |

## Enforcement Points

| Layer | File | What is enforced |
|-------|------|-----------------|
| GraphQL middleware | `graphql/middleware.py` | All mutations blocked except `BranchDelete` |
| BranchMerge mutation | `graphql/mutations/branch.py` | BranchMerge rejected for MERGED source |
| ProposedChangeCreate mutation | `graphql/mutations/proposed_change.py` | PC creation rejected for MERGED source branch |
| REST schema load | `api/schema.py` | 422 for MERGED branch |
| REST artifact generation | `api/artifact.py` | 422 for MERGED branch |
| Permission system | `permissions/report.py` | DENY returned for create/update/delete on MERGED branch |
| Frontend UI | `entities/branches/ui/` | Action buttons disabled; MERGED badge shown |
| Proposed change form | `entities/proposed-changes/ui/create-form.tsx` | MERGED branches excluded from source selector |
