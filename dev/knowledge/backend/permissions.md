# Permissions and Authorization

> Part of: `dev/knowledge/backend/` | Related: [Backend Architecture](architecture.md)

How the Infrahub permission system works — data model, resolution logic, and enforcement.

## Overview

The permission system has three layers:

1. **Data layer** — Permission nodes stored in Neo4j, assigned through Account -> Group -> Role -> Permission chains
2. **Resolution layer** — `PermissionResolver` computes decisions from loaded permissions
3. **Enforcement layer** — GraphQL checker pipeline + ad-hoc `raise_for_permission()` calls in REST endpoints

## Permission Types

### Global Permissions

Gate workflow actions and operational scope. Defined in `GlobalPermissions` enum (`core/constants/__init__.py`):

| Permission | Purpose |
|---|---|
| `SUPER_ADMIN` | Bypasses all permission checks |
| `EDIT_DEFAULT_BRANCH` | Allows mutations on the default branch |
| `MERGE_BRANCH` | Allows merging branches directly (without proposed change) |
| `MERGE_PROPOSED_CHANGE` | Allows merging proposed changes |
| `REVIEW_PROPOSED_CHANGE` | Allows approving/rejecting proposed changes |
| `MANAGE_SCHEMA` | Allows schema modifications |
| `MANAGE_ACCOUNTS` | Allows mutations on Account, AccountGroup, AccountRole |
| `MANAGE_PERMISSIONS` | Allows mutations on permission objects and reading role-permission relationships |
| `MANAGE_REPOSITORIES` | Allows mutations on Repository and ReadOnlyRepository |
| `OVERRIDE_CONTEXT` | Allows overriding the execution context |
| `READ_TELEMETRY` | Allows reading telemetry data |
| `UPDATE_OBJECT_HFID_DISPLAY_LABEL` | Allows ad-hoc updates to HFIDs and display labels |

Global permission resolution: deny preempts allow. If any loaded permission for an action has decision=DENY, the permission is denied regardless of other ALLOW entries.

### Object Permissions

Gate CRUD operations on specific kinds. Defined by four fields:

- **namespace** — Schema namespace (e.g., `Infra`, `Core`, `*` for wildcard)
- **name** — Schema name (e.g., `Device`, `*` for wildcard)
- **action** — `view`, `create`, `update`, `delete`, or `any` (wildcard)
- **decision** — Bitflag: `DENY` (1), `ALLOW_DEFAULT` (2), `ALLOW_OTHER` (4), `ALLOW_ALL` (6)

The decision values are branch-relative:
- `ALLOW_DEFAULT` — Permission applies on the default branch only
- `ALLOW_OTHER` — Permission applies on non-default branches only
- `ALLOW_ALL` — Permission applies on all branches (`ALLOW_DEFAULT | ALLOW_OTHER`)

## Data Model

```
Account --[group_member]--> AccountGroup --[role__accountgroups]--> AccountRole --[role__permissions]--> Permission
```

- `CoreGlobalPermission` — Node with `action` (dropdown) and `decision` (number) attributes
- `CoreObjectPermission` — Node with `namespace`, `name`, `action`, `decision` attributes
- `CoreAccountRole` — Has a `permissions` relationship to `CoreBasePermission` (parent of both permission types)
- `CoreAccountGroup` — Has a `roles` relationship to `CoreAccountRole`

## Key Classes

### PermissionResolver (`permissions/resolver.py`)

Stateless decision engine. Takes loaded permissions as input, computes decisions. No I/O, no exceptions, no side effects. This is the **single source of truth** for all permission decisions.

Key methods:
- `resolve_global_permission(action: str) -> bool` — Checks if a global permission is granted
- `report_object_permission(namespace, name, action) -> PermissionDecisionFlag` — Returns the combined decision flag for a kind/action
- `has_permission(permission) -> bool` — Unified check with super admin bypass
- `get_branch_decision(branch, node, action) -> BranchRelativePermissionDecision` — Computes the full branch-relative decision for a kind/action, used by both the checker pipeline and permission reports
- `build_global_report() -> dict[GlobalPermissions, bool]` — Precomputes all global permission checks for batch operations

### PermissionManager (`permissions/manager.py`)

Per-request container. Handles permission loading from backends and enforcement (raising `PermissionDeniedError`). Delegates all resolution to `PermissionResolver` via the `resolver` property.

Key methods:
- `load_permissions(db, branch)` — Loads permissions from all configured backends
- `raise_for_permission(permission, message)` — Raises if permission is denied
- `raise_for_permissions(permissions, message)` — Raises if any permission is denied

### PermissionBackend (`permissions/backend.py`)

Abstract base class for permission loading. The only implementation is `LocalPermissionBackend` which loads from Neo4j. Multiple backends can be chained — each contributes permissions additively. Configured via `config.SETTINGS.main.permission_backends`.

## Specificity Algorithm

When multiple object permissions match a request, the most specific one wins. Specificity is scored 0-4:

- +1 if namespace is not `*`
- +1 if name is not `*`
- +1 if action is not `any`
- +1 if decision is `DENY` (deny bonus — DENY always wins at equal granularity)

At equal specificity, non-DENY permissions are OR'd together.

## Decision Priority Chain

`PermissionResolver.get_branch_decision()` encodes the full priority chain:

1. **Merged/need-rebase branches** — Deny ALL mutations, even for super admins
2. **Super admin** — Allow everything else
3. **Kind-specific global permissions** — For mutations on protected kinds (accounts, permissions, repositories), require the corresponding `MANAGE_*` permission
4. **Object permissions** — Apply specificity algorithm, convert to branch-relative decision

This chain is used by both the GraphQL permission report (UI display) and the checker pipeline (enforcement), ensuring they always agree.

## GraphQL Checker Pipeline

Registered in `graphql/api/dependencies.py`. Checkers run in order:

```
Anonymous -> SuperAdmin -> DefaultBranch -> MergeBranch -> AccountManager -> RepositoryManager -> PermissionManager -> ObjectPermission
```

Each checker returns `TERMINATE` (stop chain, authorized) or `NEXT_CHECKER` (continue). If no checker terminates, the request is denied.

**Checker categories** (by convention):

| Category | Behavior | Examples |
|---|---|---|
| Gate | May short-circuit (TERMINATE) or pass (NEXT_CHECKER). Never raises. | SuperAdmin |
| Pre-filter | Rejects unauthenticated requests with `AuthorizationError`. Runs first in the pipeline. | Anonymous |
| Enforcement | Raises `PermissionDeniedError` if violated, returns NEXT_CHECKER. | DefaultBranch, MergeBranch, AccountManager, RepositoryManager, PermissionManager |
| Terminal | Always returns TERMINATE. Must be last. | ObjectPermission |

## REST API Enforcement

REST endpoints have no pipeline. Each must manually call `raise_for_permission()`. Some endpoints (schema load, file object download, telemetry) do this correctly. Others only check authentication without authorization.

## Permission Loading (Neo4j Queries)

Four query classes in `core/account.py`:
- `AccountGlobalPermissionQuery` — Account -> Group -> Role -> GlobalPermission (4 hops)
- `AccountObjectPermissionQuery` — Account -> Group -> Role -> ObjectPermission (4 hops + 4 attribute subqueries)
- `AccountRoleGlobalPermissionQuery` — Role -> GlobalPermission (for anonymous access)
- `AccountRoleObjectPermissionQuery` — Role -> ObjectPermission (for anonymous access)

Permissions are loaded per-request with no caching.

## Helper Functions

- `get_global_permission_for_kind(schema)` — Maps a schema kind to its required global permission (e.g., `AccountGroup` -> `MANAGE_ACCOUNTS`). Returns `None` for unprotected kinds. Located in `permissions/types.py`.
- `define_object_permission_from_branch(schema, action, branch_name)` — Creates an `ObjectPermission` with the correct branch-relative decision for the given branch. Located in `permissions/types.py`.
- `define_global_permission_from_branch(permission, branch_name)` — Creates a `GlobalPermission` with the correct branch-relative decision. Located in `permissions/globals.py`.
