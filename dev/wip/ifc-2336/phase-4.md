# Phase 4: Manual Delete with Git Option

**Status:** ✅ Done
**Priority:** P3
**Requirements:** FR-008, FR-009
**Depends on:** Phase 3

---

## Goal

Expose `delete_from_git` as an optional parameter on the `BranchDelete` GraphQL mutation. This lets the UI pass `delete_from_git: true` on manual deletion, triggering Git branch deletion even when the global `delete_git_branch_after_merge` setting is disabled. The actual deletion logic is already handled by `delete_branch()` after Phase 3.

---

## Checklist

- [x] Add `BranchDeleteInput` class (new — `BranchNameInput` is unchanged)
- [x] Switch `BranchDelete.Arguments` and `mutate()` type hint from `BranchNameInput` to `BranchDeleteInput`
- [x] Pass `delete_from_git` through to the `BRANCH_DELETE` workflow parameters
- [x] Update `delete_branch()` to accept `delete_from_git: bool = False` and wire it into `should_delete_git`
- [x] Write tests

---

## Implementation

### 4.1 Add BranchDeleteInput

**File:** `backend/infrahub/graphql/mutations/branch.py`

`BranchNameInput` (line 108) is shared by `BranchRebase`, `BranchValidate`, and others — do not touch it. Add a new class immediately after it:

```python
class BranchDeleteInput(InputObjectType):
    name = String(required=False)
    delete_from_git = Boolean(required=False, default_value=False)
```

### 4.2 Switch BranchDelete to BranchDeleteInput

**File:** `backend/infrahub/graphql/mutations/branch.py`

`BranchDelete` currently uses `BranchNameInput` in two places (lines 120 and 132). Update both:

```python
class BranchDelete(Mutation):
    class Arguments:
        data = BranchDeleteInput(required=True)   # was BranchNameInput
        context = ContextInput(required=False)
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: BranchDeleteInput,               # was BranchNameInput
        context: ContextInput | None = None,
        wait_until_completion: bool = True,
    ) -> Self:
```

### 4.4 Update `delete_branch()` to accept `delete_from_git`

**File:** `backend/infrahub/core/branch/tasks.py`

Update the flow signature to accept the new parameter:

```python
@flow(name="branch-delete", flow_run_name="Delete branch {branch}")
async def delete_branch(
    branch: str,
    context: InfrahubContext,
    delete_from_git: bool = False,
) -> None:
```

Update the `should_delete_git` condition to include the explicit flag:

```python
should_delete_git = (config.SETTINGS.git.delete_git_branch_after_merge or delete_from_git) and obj.sync_with_git
```

---

### 4.3 Pass delete_from_git to the workflow

In the `mutate()` body, extract the flag and include it in both workflow call sites (execute and submit):

```python
graphql_context: GraphqlContext = info.context
obj = await Branch.get_by_name(db=graphql_context.db, name=str(data.name))
await apply_external_context(graphql_context=graphql_context, context_input=context)

parameters = {
    "branch": obj.name,
    "delete_from_git": bool(data.delete_from_git),
}

if wait_until_completion:
    await graphql_context.active_service.workflow.execute_workflow(
        workflow=BRANCH_DELETE, context=graphql_context.get_context(), parameters=parameters
    )
    return cls(ok=True)

workflow = await graphql_context.active_service.workflow.submit_workflow(
    workflow=BRANCH_DELETE, context=graphql_context.get_context(), parameters=parameters
)
return cls(ok=True, task={"id": str(workflow.id)})
```

---

## Tests

**File:** `backend/tests/functional/branch/test_delete_git_branch.py`

- `test_git_deletion_triggered_when_delete_from_git_true_and_config_disabled` — mutation with `delete_from_git: true`, config disabled, assert `GIT_REPOSITORIES_DELETE_BRANCH` is submitted
- `test_git_deletion_not_triggered_when_delete_from_git_false_and_config_disabled` — mutation with `delete_from_git: false`, config disabled, assert git workflow not submitted

**Verification:**

```bash
uv run pytest backend/tests/functional/branch/test_delete_git_branch.py -v
```
