import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql_mutation


@pytest.fixture
async def repos_and_checks_in_main(db: InfrahubDatabase, register_core_models_schema):
    repo01 = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repo01.new(db=db, name="repo01", location="git@github.com:user/repo01.git")
    await repo01.save(db=db)

    repo02 = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repo02.new(db=db, name="repo02", location="git@github.com:user/repo02.git")
    await repo02.save(db=db)

    query01 = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await query01.new(db=db, name="my_query", query="query { check { id } }")
    await query01.save(db=db)

    checkdef01 = await Node.init(db=db, schema=InfrahubKind.CHECKDEFINITION)
    await checkdef01.new(
        db=db,
        name="check01",
        query=query01,
        repository=repo01,
        file_path="check01.py",
        class_name="Check01",
    )
    await checkdef01.save(db=db)

    checkdef02 = await Node.init(db=db, schema=InfrahubKind.CHECKDEFINITION)
    await checkdef02.new(
        db=db,
        name="check02",
        query=query01,
        repository=repo02,
        file_path="check02.py",
        class_name="Check02",
    )
    await checkdef02.save(db=db)


async def test_branch_create(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, register_core_models_schema, session_admin
):
    query = """
    mutation {
        BranchCreate(data: { name: "branch2", sync_with_git: false }) {
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
    recorder = BusRecorder()
    service = InfrahubServices(message_bus=recorder)

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
    assert recorder.seen_routing_keys == ["event.branch.create"]
    assert recorder.messages
    message = recorder.messages[0]
    assert isinstance(message, messages.EventBranchCreate)
    assert message.branch == "branch2"

    branch2 = await Branch.get_by_name(db=db, name="branch2")
    branch2_schema = registry.schema.get_schema_branch(name=branch2.name)

    assert branch2
    assert branch2_schema

    assert branch2.schema_hash == branch2_schema.get_hash_full()

    # Validate that we can't create a branch with a name that already exist
    gql_params = prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, account_session=session_admin
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
    assert "The branch branch2, already exist" in result.errors[0].message

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
    gql_params = prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, account_session=session_admin
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


async def test_branch_delete(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, register_core_models_schema, session_admin
):
    create_query = """
    mutation {
        BranchCreate(data: { name: "branch3", description: "my description", sync_with_git: false }) {
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

    delete_query = """
    mutation {
        BranchDelete(data: { name: "branch3" }) {
            ok
        }
    }
    """

    delete_before_create = await graphql_mutation(
        query=delete_query, db=db, branch=default_branch, account_session=session_admin
    )
    recorder = BusRecorder()
    service = InfrahubServices(message_bus=recorder)

    create = await graphql_mutation(
        query=create_query, db=db, branch=default_branch, service=service, account_session=session_admin
    )
    recorder = BusRecorder()
    service = InfrahubServices(message_bus=recorder)

    delete_after_create = await graphql_mutation(
        query=delete_query, db=db, branch=default_branch, service=service, account_session=session_admin
    )
    delete_after_delete = await graphql_mutation(
        query=delete_query, db=db, branch=default_branch, account_session=session_admin
    )

    assert delete_before_create.errors
    assert delete_before_create.errors[0].message == "Branch: branch3 not found."
    assert not create.errors
    assert not delete_after_create.errors
    assert delete_after_delete.errors
    assert delete_after_delete.errors[0].message == "Branch: branch3 not found."
    assert recorder.seen_routing_keys == ["event.branch.delete"]


async def test_branch_create_registry(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, register_core_models_schema, session_admin
):
    query = """
    mutation {
        BranchCreate(data: { name: "branch2", sync_with_git: false }) {
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
    gql_params = prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, account_session=session_admin
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


async def test_branch_create_invalid_names(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, register_core_models_schema, session_admin
):
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
    gql_params = prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, account_session=session_admin
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
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, register_core_models_schema, session_admin
):
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
    result = await graphql_mutation(query=query, db=db, variables={"branch_name": "b"}, account_session=session_admin)
    assert result.errors
    assert len(result.errors) == 1
    assert result.errors[0].message == "invalid field name: String should have at least 3 characters"


async def test_branch_create_with_repositories(
    db: InfrahubDatabase,
    default_branch: Branch,
    repos_and_checks_in_main,
    register_core_models_schema,
    data_schema,
    session_admin,
):
    query = """
    mutation {
        BranchCreate(data: { name: "branch2", sync_with_git: true }) {
            ok
            object {
                id
                name
            }
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, account_session=session_admin
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

    assert await Branch.get_by_name(db=db, name="branch2")


async def test_branch_rebase(db: InfrahubDatabase, default_branch: Branch, car_person_schema, session_admin):
    branch2 = await create_branch(db=db, branch_name="branch2")

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
    recorder = BusRecorder()
    service = InfrahubServices(message_bus=recorder)
    result = await graphql_mutation(
        query=query, db=db, branch=default_branch, service=service, account_session=session_admin
    )

    assert result.errors is None
    assert result.data
    assert result.data["BranchRebase"]["ok"] is True
    assert result.data["BranchRebase"]["object"]["id"] == str(branch2.uuid)

    new_branch2 = await Branch.get_by_name(db=db, name="branch2")
    assert new_branch2.branched_from != branch2.branched_from

    assert recorder.seen_routing_keys == ["event.branch.rebased"]


async def test_branch_rebase_wrong_branch(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, session_admin
):
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
    recorder = BusRecorder()
    service = InfrahubServices(message_bus=recorder)
    gql_params = prepare_graphql_params(
        db=db, include_subscription=False, service=service, branch=default_branch, account_session=session_admin
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


async def test_branch_validate(db: InfrahubDatabase, base_dataset_02, register_core_models_schema, session_admin):
    branch1 = await Branch.get_by_name(db=db, name="branch1")

    query = """
    mutation {
        BranchValidate(data: { name: "branch1" }) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_subscription=False, branch=branch1, account_session=session_admin
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
    assert result.data["BranchValidate"]["ok"] is True
    assert result.data["BranchValidate"]["object"]["id"] == str(branch1.uuid)


async def test_branch_update_description(db: InfrahubDatabase, base_dataset_02):
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
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch4)
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

    assert branch4_updated.description == "testing"


async def test_branch_merge(db: InfrahubDatabase, base_dataset_02, register_core_models_schema, session_admin):
    branch1 = await Branch.get_by_name(db=db, name="branch1")

    query = """
    mutation {
        BranchMerge(data: { name: "branch1" }) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_subscription=False, branch=branch1, account_session=session_admin
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
    assert result.data["BranchMerge"]["ok"] is True
    assert result.data["BranchMerge"]["object"]["id"] == str(branch1.uuid)
