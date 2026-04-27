from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fast_depends import Provider
from infrahub_sdk.client import InfrahubClient

from infrahub.auth import AccountSession, AuthType
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workers.dependencies import build_database, build_message_bus, build_workflow
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql, graphql_mutation
from tests.helpers.test_app import TestInfrahubApp


class TestBranchCreate(TestInfrahubApp):
    async def test_branch_create(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        register_core_models_schema: SchemaBranch,
        session_admin: AccountSession,
        client: InfrahubClient,
        service: InfrahubServices,
    ) -> None:
        query = """
            mutation {
                BranchCreate(data: { name: "branch2", sync_with_git: false, origin_branch: "main" }) {
                    ok
                    object {
                        id
                        name
                        description
                        sync_with_git
                        is_default
                        branched_from
                    }
                }
            }
            """

        result = await graphql_mutation(
            query=query, db=db, service=service, branch=default_branch, account_session=session_admin
        )

        assert result.errors is None
        assert result.data
        assert result.data["BranchCreate"]["ok"] is True
        assert len(result.data["BranchCreate"]["object"]["id"]) == 36  # length of an UUID
        assert result.data["BranchCreate"]["object"]["name"] == "branch2"
        assert not result.data["BranchCreate"]["object"]["description"]
        assert result.data["BranchCreate"]["object"]["sync_with_git"] is False
        assert result.data["BranchCreate"]["object"]["is_default"] is False
        assert result.data["BranchCreate"]["object"]["branched_from"] is not None

        branch2 = await Branch.get_by_name(db=db, name="branch2")
        branch2_schema = registry.schema.get_schema_branch(name=branch2.name)

        assert branch2
        assert branch2_schema

        assert branch2.schema_hash == branch2_schema.get_hash_full()

        # Validate that we can't create a branch with a name that already exist
        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(
            db=db,
            branch=default_branch,
            account_session=session_admin,
            service=service,
        )
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )
        assert result.errors
        assert len(result.errors) == 1
        assert "The branch branch2 already exists" in result.errors[0].message

        # Create another branch with different inputs
        query = """
        mutation {
            BranchCreate(data: { name: "branch3", description: "my description" }) {
                ok
                object {
                    id
                    name
                    description
                    sync_with_git
                }
            }
        }
        """
        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(
            db=db,
            branch=default_branch,
            account_session=session_admin,
            service=service,
        )
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )

        assert result.errors is None
        assert result.data
        assert result.data["BranchCreate"]["ok"] is True
        assert len(result.data["BranchCreate"]["object"]["id"]) == 36  # length of an UUID
        assert result.data["BranchCreate"]["object"]["name"] == "branch3"
        assert result.data["BranchCreate"]["object"]["description"] == "my description"
        assert result.data["BranchCreate"]["object"]["sync_with_git"] is True

    async def test_branch_create_invalid_names(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        register_core_models_schema: SchemaBranch,
        session_admin: AccountSession,
        client: InfrahubClient,
        service: InfrahubServices,
    ) -> None:
        query = """
        mutation($branch_name: String!) {
            BranchCreate(data: { name: $branch_name, sync_with_git: false }) {
                ok
                object {
                    id
                    name
                }
            }
        }
        """

        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(
            db=db,
            branch=default_branch,
            account_session=session_admin,
            service=service,
        )
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"branch_name": "not valid"},
        )

        assert result.errors
        assert len(result.errors) == 1
        assert (
            result.errors[0].message
            == "Branch name contains invalid patterns or characters: disallowed ASCII characters/patterns"
        )

    async def test_branch_create_short_name(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        register_core_models_schema: SchemaBranch,
        session_admin: AccountSession,
        service: InfrahubServices,
    ) -> None:
        query = """
        mutation($branch_name: String!) {
            BranchCreate(data: { name: $branch_name, sync_with_git: false }) {
                ok
                object {
                    id
                    name
                }
            }
        }
        """

        result = await graphql_mutation(
            query=query, db=db, variables={"branch_name": "b"}, account_session=session_admin, service=service
        )
        assert result.errors
        assert len(result.errors) == 1
        assert result.errors[0].message == "invalid field name: String should have at least 3 characters"

    async def test_branch_create_registry(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        register_core_models_schema: SchemaBranch,
        session_admin: AccountSession,
        client: InfrahubClient,
        service: InfrahubServices,
    ) -> None:
        query = """
        mutation {
            BranchCreate(data: { name: "branch5", sync_with_git: false }) {
                ok
                object {
                    id
                    name
                    description
                    sync_with_git
                    is_default
                    branched_from
                }
            }
        }
        """

        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(
            db=db,
            branch=default_branch,
            account_session=session_admin,
            service=service,
        )
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )

        assert result.errors is None
        assert result.data
        assert result.data["BranchCreate"]["ok"] is True

        branch2 = await Branch.get_by_name(db=db, name="branch2")
        assert branch2.active_schema_hash.main == default_branch.active_schema_hash.main

    async def test_branch_create_invalid_origin_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        session_admin: AccountSession,
        service: InfrahubServices,
    ) -> None:
        query = """
        mutation AddBranch {
            BranchCreate(data: {
                name: "test1"
                description: "test1 description"
                sync_with_git: false
                origin_branch: "test"
            }) {
                ok
                object {
                    id
                }
            }
        }
        """
        result = await graphql_mutation(
            query=query, db=db, service=service, branch=default_branch, account_session=session_admin
        )

        assert result.errors
        assert len(result.errors) == 1
        assert f"origin_branch must be '{default_branch.name}'" == result.errors[0].message


@pytest.fixture
async def local_services(db: InfrahubDatabase, dependency_provider: Provider) -> InfrahubServices:
    message_bus = BusRecorder()
    workflow = WorkflowLocalExecution()

    with (
        dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
        dependency_provider.scope(build_message_bus, lambda: message_bus),
        dependency_provider.scope(build_workflow, lambda: workflow),
    ):
        yield await InfrahubServices.new(message_bus=message_bus, database=db, workflow=workflow)


async def test_branch_delete(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    register_core_models_schema: SchemaBranch,
    session_admin: AccountSession,
    local_services: InfrahubServices,
) -> None:
    delete_query = """
    mutation {
        BranchDelete(data: { name: "branch3" }) {
            ok
        }
    }
    """
    delete_before_create = await graphql_mutation(
        query=delete_query, db=db, branch=default_branch, account_session=session_admin, service=local_services
    )

    assert delete_before_create.errors
    assert delete_before_create.errors[0].message == "Branch: branch3 not found."


async def test_branch_rebase_wrong_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    session_admin: AccountSession,
    local_services: InfrahubServices,
) -> None:
    query = """
    mutation {
        BranchRebase(data: { name: "branch2" }) {
            ok
            object {
                id
            }
        }
    }
    """

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db,
        service=local_services,
        branch=default_branch,
        account_session=session_admin,
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert result.errors[0].message == "Branch: branch2 not found."


async def test_branch_update_description(
    db: InfrahubDatabase, base_dataset_02: dict, session_admin: AccountSession, local_services: InfrahubServices
) -> None:
    branch4 = await create_branch(branch_name="branch4", db=db)

    query = """
    mutation {
    BranchUpdate(
        data: {
        name: "branch4",
        description: "testing"
        }
    ) {
        ok
    }
    }
    """

    branch4.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=branch4, account_session=session_admin, service=local_services
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["BranchUpdate"]["ok"] is True

    branch4_updated = await Branch.get_by_name(db=db, name="branch4")

    assert branch4.updated_at == branch4.created_at
    assert branch4_updated.description == "testing"
    assert branch4.updated_at
    assert branch4_updated.updated_at
    assert branch4_updated.updated_at > branch4.updated_at
    assert branch4_updated.updated_by == session_admin.account_id


async def test_branch_merge_wrong_branch(
    db: InfrahubDatabase,
    base_dataset_02: dict[str, Any],
    register_core_models_schema: SchemaBranch,
    session_admin: AccountSession,
    local_services: InfrahubServices,
) -> None:
    branch1 = await Branch.get_by_name(db=db, name="branch1")

    query = """
    mutation {
        BranchMerge(data: { name: "branch99" }) {
            ok
            object {
                id
            }
        }
    }
    """

    branch1.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=branch1, account_session=session_admin, service=local_services
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert result.errors[0].message == "Branch: branch99 not found."


async def test_branch_merge_need_upgrade_rebase(
    db: InfrahubDatabase,
    base_dataset_02: dict[str, Any],
    register_core_models_schema: SchemaBranch,
    session_admin: AccountSession,
    local_services: InfrahubServices,
) -> None:
    branch = await create_branch(db=db, branch_name="branch_to_upgrade")
    branch.status = BranchStatus.NEED_UPGRADE_REBASE
    await branch.save(db=db)

    query = """
    mutation {
        BranchMerge(data: { name: "branch_to_upgrade" }) {
            ok
            object {
                id
            }
        }
    }
    """

    gql_params = await prepare_graphql_params(
        db=db, branch=branch, account_session=session_admin, service=local_services
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert result.errors[0].message == "Cannot merge branch 'branch_to_upgrade' with status 'NEED_UPGRADE_REBASE'"


async def test_branch_merge_with_conflict_fails(
    db: InfrahubDatabase,
    car_person_schema: SchemaBranch,
    car_camry_main: Node,
    session_admin: AccountSession,
    local_services: InfrahubServices,
) -> None:
    query = """
    mutation {
        BranchMerge(data: { name: "branch2" }) {
            ok
            object {
                id
            }
        }
    }
    """

    branch2 = await create_branch(db=db, branch_name="branch2")
    car_main = await NodeManager.get_one(db=db, id=car_camry_main.id)
    car_main.name.value += "-main"
    await car_main.save(db=db)
    car_branch = await NodeManager.get_one(db=db, branch=branch2, id=car_camry_main.id)
    car_branch.name.value += "-branch"
    await car_branch.save(db=db)

    branch2.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=branch2, account_session=session_admin, service=local_services
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "contains conflicts with the default branch" in result.errors[0].message


async def _create_branch(branch_name: str, db: InfrahubDatabase, owner: Node) -> Branch:
    branch = Branch(name=branch_name, status=BranchStatus.OPEN, hierarchy_level=2, is_default=False)
    origin_schema = registry.schema.get_schema_branch(name=branch.origin_branch)
    registry.schema.set_schema_branch(name=branch.name, schema=origin_schema.duplicate(name=branch.name))
    branch.update_schema_hash()
    await branch.save(db=db, user_id=owner.id)
    registry.branch[branch.name] = branch
    return branch


async def test_branch_delete_own_branch_succeeds(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    local_services: InfrahubServices,
) -> None:
    """A user who created a branch can delete it without any elevated permissions."""
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="delete-own-branch-user", account_type="User", password="TestPassword123!")
    await account.save(db=db)
    session = AccountSession(authenticated=True, auth_type=AuthType.API, account_id=account.id)

    await _create_branch(branch_name="test-own-branch", db=db, owner=account)

    with patch.object(local_services.workflow, "execute_workflow", new=AsyncMock(return_value=None)):
        delete_result = await graphql_mutation(
            query='mutation { BranchDelete(data: { name: "test-own-branch" }) { ok } }',
            db=db,
            branch=default_branch,
            account_session=session,
            service=local_services,
        )
    assert delete_result.errors is None
    assert delete_result.data
    assert delete_result.data["BranchDelete"]["ok"] is True


async def test_branch_delete_others_branch_denied(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    local_services: InfrahubServices,
) -> None:
    """A user without DELETE_BRANCH permission cannot delete a branch they did not create."""
    owner = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await owner.new(db=db, name="branch-creator-user", account_type="User", password="OwnerPassword123!")
    await owner.save(db=db)

    other = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await other.new(db=db, name="branch-non-owner-user", account_type="User", password="OtherPassword123!")
    await other.save(db=db)
    other_session = AccountSession(authenticated=True, auth_type=AuthType.API, account_id=other.id)

    await _create_branch(branch_name="test-others-branch", db=db, owner=owner)

    delete_result = await graphql_mutation(
        query='mutation { BranchDelete(data: { name: "test-others-branch" }) { ok } }',
        db=db,
        branch=default_branch,
        account_session=other_session,
        service=local_services,
    )
    assert delete_result.errors
    assert "You are not allowed to delete a branch you did not create" in delete_result.errors[0].message
