import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


@pytest.fixture
def interface_schema(default_branch: Branch, register_core_models_schema: SchemaBranch) -> None:
    generic = GenericSchema(
        name="Interface",
        namespace="Test",
        branch=BranchSupportType.AWARE.value,
        generate_profile=True,
        attributes=[
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "speed", "kind": "Number", "optional": True},
        ],
    )
    registry.schema.set(name=generic.kind, schema=generic)

    # This node inherits from a profile-enabled generic but opts out of profiles.
    # Its template must still satisfy the 'profiles' field from the generic template interface.
    node = NodeSchema(
        name="InterfaceL3",
        namespace="Test",
        branch=BranchSupportType.AWARE.value,
        generate_profile=False,
        generate_template=True,
        inherit_from=[generic.kind],
        attributes=[
            {"name": "vrf", "kind": "Text", "optional": True},
        ],
    )
    registry.schema.set(name=node.kind, schema=node)

    registry.schema.process_schema_branch(name=default_branch.name)


async def test_template_node_has_profiles_relationship_when_parent_generic_does(
    db: InfrahubDatabase,
    default_branch: Branch,
    interface_schema: None,
) -> None:
    template_node = registry.schema.get(name="TemplateTestInterfaceL3", branch=default_branch, duplicate=False)
    relationship_names = [r.name for r in template_node.relationships]
    assert "profiles" in relationship_names, (
        "TemplateTestInterfaceL3 is missing 'profiles' — it would fail the TemplateTestInterface GraphQL interface"
    )


async def test_graphql_schema_has_no_validation_errors_when_node_disables_profiles(
    db: InfrahubDatabase,
    default_branch: Branch,
    interface_schema: None,
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    # Any query will trigger validate_schema() in the execution path;
    # a schema that violates interface contracts returns errors before the query even runs.
    result = await graphql(
        schema=gql_params.schema,
        source="{ __typename }",
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is None, f"GraphQL schema has validation errors: {[str(e) for e in result.errors]}"
