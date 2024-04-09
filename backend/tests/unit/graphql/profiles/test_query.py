from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


async def test_profile_in_schema(db: InfrahubDatabase, default_branch: Branch, data_schema):
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number", "optional": True},
        ],
    }

    tmp_schema = NodeSchema(**SCHEMA)
    registry.schema.set(name=tmp_schema.kind, schema=tmp_schema)
    registry.schema.process_schema_branch(name=default_branch.name)

    profile = registry.schema.get(f"Profile{tmp_schema.kind}", branch=default_branch)

    obj1 = await Node.init(db=db, schema=profile)
    await obj1.new(db=db, profile_name="prof1", level=8)
    await obj1.save(db=db)

    query = """
    query {
        ProfileTestCriticality {
            edges {
                node {
                    id
                    display_label
                }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["ProfileTestCriticality"]["edges"]) == 1
    assert (
        result.data["ProfileTestCriticality"]["edges"][0]["node"]["display_label"]
        == f"ProfileTestCriticality(ID: {obj1.id})"
    )
