from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.permissions.constants import GLOBAL_PERMISSION_DENIAL_MESSAGE
from tests.helpers.permissions import define_permissions

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

BRANCH_NAME = "escalation"


async def _create_account_with_token(db: InfrahubDatabase, name: str) -> tuple[Node, dict[str, str]]:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name=name, password=f"{name}-password")
    await account.save(db=db)

    token = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
    await token.new(db=db, token=f"{name}-token", account=account)
    await token.save(db=db)

    return account, {"X-INFRAHUB-KEY": token.token.value}


async def _create_administrators_group(db: InfrahubDatabase) -> Node:
    permission = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
    await permission.new(db=db, action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value)
    await permission.save(db=db)

    role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role.new(db=db, name="administrators", permissions=[permission])
    await role.save(db=db)

    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="administrators", roles=[role])
    await group.save(db=db)
    return group


async def test_branch_merge_refused_after_joining_administrators_on_branch(
    db: InfrahubDatabase,
    client: TestClient,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    account, headers = await _create_account_with_token(db=db, name="account-manager")
    await define_permissions(
        account=account,
        db=db,
        object_permissions=[
            ObjectPermission(
                namespace="*",
                name="*",
                action=PermissionAction.ANY.value,
                decision=PermissionDecision.ALLOW_OTHER.value,
            )
        ],
        global_permissions=[
            GlobalPermission(
                action=GlobalPermissions.MANAGE_ACCOUNTS.value, decision=PermissionDecision.ALLOW_ALL.value
            )
        ],
    )
    administrators = await _create_administrators_group(db=db)
    await create_branch(db=db, branch_name=BRANCH_NAME)

    join_administrators = """
    mutation ($group: String!, $account: String!) {
        CoreAccountGroupUpdate(data: { id: $group, members: [{ id: $account }] }) {
            ok
        }
    }
    """
    merge_branch = """
    mutation ($branch: String!) {
        BranchMerge(data: { name: $branch }) {
            ok
        }
    }
    """

    # Must execute in a with block to execute the startup/shutdown events
    with (
        client,
        patch(
            "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.execute_workflow"
        ) as mock_execute_workflow,
    ):
        join_response = client.post(
            f"/graphql/{BRANCH_NAME}",
            json={"query": join_administrators, "variables": {"group": administrators.id, "account": account.id}},
            headers=headers,
        )
        merge_response = client.post(
            f"/graphql/{BRANCH_NAME}",
            json={"query": merge_branch, "variables": {"branch": BRANCH_NAME}},
            headers=headers,
        )

    assert join_response.status_code == 200
    assert "errors" not in join_response.json()
    assert join_response.json()["data"]["CoreAccountGroupUpdate"]["ok"] is True

    assert merge_response.json().get("errors"), "the merge must be refused"
    assert (
        merge_response.json()["errors"][0]["message"]
        == GLOBAL_PERMISSION_DENIAL_MESSAGE[GlobalPermissions.MERGE_BRANCH.value]
    )
    mock_execute_workflow.assert_not_called()


async def test_account_update_refused_with_administrators_membership_added_on_branch(
    db: InfrahubDatabase,
    client: TestClient,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    account, headers = await _create_account_with_token(db=db, name="branch-admin")
    target, _ = await _create_account_with_token(db=db, name="target")
    administrators = await _create_administrators_group(db=db)

    branch = await create_branch(db=db, branch_name=BRANCH_NAME)
    administrators_on_branch = await NodeManager.get_one(
        db=db, id=administrators.id, branch=branch, raise_on_error=True
    )
    await administrators_on_branch.members.add(db=db, data={"id": account.id})
    await administrators_on_branch.members.save(db=db)

    update_account = """
    mutation ($account: String!) {
        CoreAccountUpdate(data: { id: $account, description: { value: "changed from a branch" } }) {
            ok
        }
    }
    """

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            f"/graphql/{BRANCH_NAME}",
            json={"query": update_account, "variables": {"account": target.id}},
            headers=headers,
        )

    assert response.json().get("errors"), "the account update must be refused"
    assert (
        response.json()["errors"][0]["message"]
        == GLOBAL_PERMISSION_DENIAL_MESSAGE[GlobalPermissions.MANAGE_ACCOUNTS.value]
    )
    target_on_default = await NodeManager.get_one(db=db, id=target.id, branch=default_branch, raise_on_error=True)
    assert target_on_default.description.value is None
