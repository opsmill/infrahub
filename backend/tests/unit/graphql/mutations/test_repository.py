from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql_mutation

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_trigger_repository_import(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
):
    repository_model = registry.schema.get_node_schema(name=InfrahubKind.REPOSITORY, branch=default_branch)
    recorder = BusRecorder()
    service = InfrahubServices(database=db, message_bus=recorder)

    RUN_REIMPORT = """
    mutation InfrahubRepositoryProcess($id: String!) {
        InfrahubRepositoryProcess(data: {id: $id}) {
            ok
        }
    }
    """

    repo = await Node.init(schema=repository_model, db=db, branch=default_branch)
    commit_id = "d85571671cf51f561fb0695d8657747f9ce84057"
    await repo.new(db=db, name="test-edge-demo", location="/tmp/edge", commit=commit_id)
    await repo.save(db=db)
    result = await graphql_mutation(
        query=RUN_REIMPORT,
        db=db,
        variables={"id": repo.id},
        service=service,
    )

    assert not result.errors
    assert result.data

    assert len(recorder.messages) == 1
    message = recorder.messages[0]
    assert isinstance(message, messages.GitRepositoryImportObjects)
    assert message.repository_id == repo.id
    assert message.commit == commit_id
