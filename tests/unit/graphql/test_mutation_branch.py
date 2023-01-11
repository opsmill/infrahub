import graphene
from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.graphql import get_gql_mutation, get_gql_query


async def test_branch_create(db, session, default_branch, car_person_schema):

    query = """
    mutation {
        branch_create(data: { name: "branch2", is_data_only: true }) {
            ok
            object {
                id
                name
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(
            query=await get_gql_query(session=session),
            mutation=await get_gql_mutation(session=session),
            auto_camelcase=False,
        ).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_create"]["ok"] is True
    assert len(result.data["branch_create"]["object"]["id"]) == 36  # lenght of an UUID

    assert await Branch.get_by_name(session=session, name="branch2")

    # Validate that we can't create a branch with a name that already exist
    result = await graphql(
        graphene.Schema(
            query=await get_gql_query(session=session),
            mutation=await get_gql_mutation(session=session),
            auto_camelcase=False,
        ).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )
    assert len(result.errors) == 1
    assert "The branch branch2, already exist" in result.errors[0].message


async def test_branch_rebase(db, session, default_branch, car_person_schema):

    branch2 = await create_branch(session=session, branch_name="branch2")

    query = """
    mutation {
        branch_rebase(data: { name: "branch2" }) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(
            query=await get_gql_query(session=session),
            mutation=await get_gql_mutation(session=session),
            auto_camelcase=False,
        ).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_rebase"]["ok"] is True
    assert result.data["branch_rebase"]["object"]["id"] == str(branch2.uuid)

    new_branch2 = await Branch.get_by_name(session=session, name="branch2")
    assert new_branch2.branched_from != branch2.branched_from


async def test_branch_validate(db, session, base_dataset_02, register_core_models_schema):

    branch1 = await Branch.get_by_name(session=session, name="branch1")

    query = """
    mutation {
        branch_validate(data: { name: "branch1" }) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(
            query=await get_gql_query(session=session),
            mutation=await get_gql_mutation(session=session),
            auto_camelcase=False,
        ).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_validate"]["ok"] is True
    assert result.data["branch_validate"]["object"]["id"] == str(branch1.uuid)


async def test_branch_merge(db, session, base_dataset_02, register_core_models_schema):

    branch1 = await Branch.get_by_name(session=session, name="branch1")

    query = """
    mutation {
        branch_merge(data: { name: "branch1" }) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(
            query=await get_gql_query(session=session),
            mutation=await get_gql_mutation(session=session),
            auto_camelcase=False,
        ).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["branch_merge"]["ok"] is True
    assert result.data["branch_merge"]["object"]["id"] == str(branch1.uuid)
