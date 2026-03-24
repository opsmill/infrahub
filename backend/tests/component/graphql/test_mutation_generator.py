from unittest.mock import call, patch

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workflows.catalogue import REQUEST_GENERATOR_DEFINITION_RUN
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql


@pytest.fixture
async def group1(db: InfrahubDatabase, car_person_data_generic: dict[str, Node]) -> Node:
    g1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await g1.new(db=db, name="group1", members=[car_person_data_generic["c1"], car_person_data_generic["c2"]])
    await g1.save(db=db)
    return g1


@pytest.fixture
async def definition1(db: InfrahubDatabase, car_person_data_generic: dict[str, Node], group1: Node) -> Node:
    gd1 = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION)
    await gd1.new(
        db=db,
        name="generatordef01",
        query=str(car_person_data_generic["q1"].id),
        repository=str(car_person_data_generic["r1"].id),
        file_path="generator01.py",
        class_name="Generator01",
        targets=str(group1.id),
        parameters={"value": {"name": "name__value"}},
    )
    await gd1.save(db=db)
    return gd1


async def test_run_generator_definition(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_data_generic: dict[str, Node],
    create_test_admin: Node,
    definition1: Node,
) -> None:
    query = """
    mutation {
        CoreGeneratorDefinitionRun(data: { id: "%s" }, wait_until_completion: false) {
            ok
        }
    }
    """ % (definition1.id)
    recorder = BusRecorder()
    service = await InfrahubServices.new(message_bus=recorder, workflow=WorkflowLocalExecution())

    account_session = AccountSession(
        authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
    )
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=account_session
    )

    with patch(
        "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
    ) as mock_submit_workflow:
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )

        assert not result.errors
        assert result.data
        assert result.data["CoreGeneratorDefinitionRun"]["ok"]

        context = InfrahubContext.init(branch=default_branch, account=account_session)
        query = await definition1.query.get_peer(db=db)
        repository = await definition1.repository.get_peer(db=db)
        group = await definition1.targets.get_peer(db=db)
        expected_calls = [
            call(
                workflow=REQUEST_GENERATOR_DEFINITION_RUN,
                parameters={
                    "model": RequestGeneratorDefinitionRun(
                        generator_definition=ProposedChangeGeneratorDefinition(
                            definition_id=definition1.id,
                            definition_name=definition1.name.value,
                            class_name=definition1.class_name.value,
                            file_path=definition1.file_path.value,
                            query_name=query.name.value,
                            query_models=query.models.value,
                            repository_id=repository.id,
                            parameters=definition1.parameters.value,
                            group_id=group.id,
                            convert_query_response=definition1.convert_query_response.value,
                            execute_in_proposed_change=definition1.execute_in_proposed_change.value,
                            execute_after_merge=definition1.execute_after_merge.value,
                        ),
                        branch=context.branch.name,
                    )
                },
                context=context,
            ),
        ]
        mock_submit_workflow.assert_has_calls(expected_calls)
