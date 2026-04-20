# Creating Permission Checkers

> Part of: `dev/guides/backend/` | Related: [Permissions Knowledge](../../knowledge/backend/permissions.md)

Step-by-step guide for adding a new permission checker to the GraphQL pipeline.

## When to Create a Checker

Create a new checker when you need to enforce a permission constraint that:

- Applies to GraphQL operations (queries or mutations)
- Cannot be expressed through existing object permissions alone
- Requires a global permission or custom logic before the `ObjectPermissionChecker` runs

If you only need to gate CRUD on a specific kind, object permissions already handle that via `ObjectPermissionChecker`. You do NOT need a new checker.

## Prerequisites

- Understanding of the permission system (see [Permissions Knowledge](../../knowledge/backend/permissions.md))
- Familiarity with the GraphQL query analyzer (`graphql/analyzer.py`)

## Checker Categories

Before writing a checker, decide which category it falls into:

| Category | When to use | Returns | Raises? |
|---|---|---|---|
| **Gate** | Short-circuit the entire pipeline for a class of users (e.g., super admin bypass) | `TERMINATE` or `NEXT_CHECKER` | Never |
| **Enforcement** | Validate a specific constraint and block if violated | `NEXT_CHECKER` always | `PermissionDeniedError` on violation |
| **Terminal** | Final authority — runs last, handles the general case | `TERMINATE` always | `PermissionDeniedError` on violation |

Most new checkers will be **enforcement** checkers. There should only be one terminal checker (`ObjectPermissionChecker`).

## Steps

### Step 1: Create the Checker Class

Create a new file in `backend/infrahub/graphql/auth/query_permission_checker/` or add to an existing file if closely related to an existing checker.

```python
# backend/infrahub/graphql/auth/query_permission_checker/my_checker.py
from infrahub import config
from infrahub.auth import AccountSession
from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.database import InfrahubDatabase
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class MyPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Describe what this checker enforces."""

    permission_required = GlobalPermission(
        action=GlobalPermissions.MY_PERMISSION.value,
        decision=PermissionDecision.ALLOW_ALL.value,
    )

    async def supports(
        self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch
    ) -> bool:
        # Return True if this checker should run for this request.
        # Most checkers use this pattern:
        return config.SETTINGS.main.allow_anonymous_access or account_session.authenticated

    async def check(
        self,
        db: InfrahubDatabase,
        account_session: AccountSession,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch,
    ) -> CheckerResolution:
        # 1. Determine if this request is relevant to your checker
        if not self._is_relevant(analyzed_query, db, branch):
            return CheckerResolution.NEXT_CHECKER

        # 2. If relevant and it's a mutation, enforce the permission
        if analyzed_query.contains_mutation:
            query_parameters.context.active_permissions.raise_for_permission(
                permission=self.permission_required
            )

        # 3. Enforcement checkers always return NEXT_CHECKER
        return CheckerResolution.NEXT_CHECKER
```

### Step 2: Implement the Relevance Check

The checker needs to determine whether the current query touches objects it cares about. Common patterns:

**Check by kind:**
```python
from infrahub.core.manager import get_schema
from infrahub.core.schema.node_schema import NodeSchema

# Check if any impacted model matches your target kinds
for kind in analyzed_query.query_report.impacted_models:
    schema = get_schema(db=db, branch=branch, node_schema=kind)
    if kind == InfrahubKind.MY_KIND or (
        isinstance(schema, NodeSchema) and InfrahubKind.MY_GENERIC in schema.inherit_from
    ):
        return True  # This query is relevant
```

**Check by operation name:**
```python
if "MyOperationName" in analyzed_query.operation_names:
    return True
```

**Check by relationship access:**
```python
if (
    kind in analyzed_query.query_report.requested_read
    and "my_relationship" in analyzed_query.query_report.requested_read[kind].relationships
):
    return True
```

### Step 3: Register the Checker

Add your checker to the pipeline in `backend/infrahub/graphql/api/dependencies.py`:

```python
from ..auth.query_permission_checker.my_checker import MyPermissionChecker

def build_graphql_query_permission_checker() -> GraphQLQueryPermissionChecker:
    return GraphQLQueryPermissionChecker(
        [
            AnonymousGraphQLPermissionChecker(get_anonymous_access_setting),
            SuperAdminPermissionChecker(),
            DefaultBranchPermissionChecker(),
            MergeBranchPermissionChecker(),
            AccountManagerPermissionChecker(),
            RepositoryManagerPermissionChecker(),
            PermissionManagerPermissionChecker(),
            MyPermissionChecker(),              # <-- Add here
            ObjectPermissionChecker(),          # Must remain last
        ]
    )
```

**Ordering rules:**
- Gate checkers go at the top (Anonymous, SuperAdmin)
- Enforcement checkers go in the middle, before `ObjectPermissionChecker`
- `ObjectPermissionChecker` must always be last (it's the terminal checker)

### Step 4: Update the Permission Report

If your checker enforces a global permission for specific kinds, update `get_global_permission_for_kind()` in `backend/infrahub/permissions/types.py` so the permission report stays in sync:

```python
def get_global_permission_for_kind(schema: MainSchemaTypes) -> GlobalPermissions | None:
    kind_permission_map = {
        InfrahubKind.GENERICACCOUNT: GlobalPermissions.MANAGE_ACCOUNTS,
        InfrahubKind.ACCOUNTGROUP: GlobalPermissions.MANAGE_ACCOUNTS,
        InfrahubKind.ACCOUNTROLE: GlobalPermissions.MANAGE_ACCOUNTS,
        InfrahubKind.BASEPERMISSION: GlobalPermissions.MANAGE_PERMISSIONS,
        InfrahubKind.GENERICREPOSITORY: GlobalPermissions.MANAGE_REPOSITORIES,
        InfrahubKind.MY_KIND: GlobalPermissions.MY_PERMISSION,  # <-- Add here
    }
    # ...
```

This ensures `PermissionResolver.get_branch_decision()` — which powers both the pipeline and the UI permission report — reflects your checker's constraint.

### Step 5: Add a Denial Message

If your checker uses a new global permission, add a human-readable denial message in `backend/infrahub/permissions/constants.py`:

```python
GLOBAL_PERMISSION_DENIAL_MESSAGE = {
    # ... existing entries ...
    GlobalPermissions.MY_PERMISSION.value: "You are not allowed to perform this action",
}

GLOBAL_PERMISSION_DESCRIPTION = {
    # ... existing entries ...
    GlobalPermissions.MY_PERMISSION: "Allow a user to perform this action",
}
```

### Step 6: Write Tests

Create tests in `backend/tests/component/graphql/auth/query_permission_checker/`. Follow the pattern in existing test files (e.g., `test_object_permission_checker.py`).

Test at minimum:
- `supports()` returns correct values for authenticated/unauthenticated users
- `check()` returns `NEXT_CHECKER` when the query is not relevant
- `check()` raises `PermissionDeniedError` when the permission is missing
- `check()` passes when the permission is present
- `check()` only enforces on mutations (if that's the intent)

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.auth.query_permission_checker.my_checker import MyPermissionChecker


class TestMyPermissionChecker:
    async def test_irrelevant_query_passes(self, db, branch):
        checker = MyPermissionChecker()
        # Set up analyzed_query that doesn't touch your kinds
        # ...
        result = await checker.check(db=db, ...)
        assert result == CheckerResolution.NEXT_CHECKER

    async def test_mutation_without_permission_raises(self, db, branch):
        checker = MyPermissionChecker()
        # Set up analyzed_query with mutation on your kind
        # Set up permission manager without the required permission
        # ...
        with pytest.raises(PermissionDeniedError):
            await checker.check(db=db, ...)

    async def test_mutation_with_permission_passes(self, db, branch):
        checker = MyPermissionChecker()
        # Set up analyzed_query with mutation on your kind
        # Set up permission manager WITH the required permission
        # ...
        result = await checker.check(db=db, ...)
        assert result == CheckerResolution.NEXT_CHECKER
```

## Checklist

- [ ] Checker class created with `supports()` and `check()` methods
- [ ] Registered in `dependencies.py` (before `ObjectPermissionChecker`)
- [ ] `get_global_permission_for_kind()` updated in `types.py` (if applicable)
- [ ] Denial message added to `constants.py` (if new global permission)
- [ ] Tests written and passing
- [ ] Existing tests still pass: `uv run pytest backend/tests/component/graphql/auth/ -v`
