from uuid import uuid4

from prefect.client.schemas.objects import FlowRun

from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.task_manager.flow_run.enrichment import UNRESOLVED_NODE_KIND, RelatedNodeEnricher
from infrahub.task_manager.flow_run.tags import WorkflowTagDecoder
from infrahub.workflows.constants import WorkflowTag


def _run_tagged_with(node_ids: list[str]) -> FlowRun:
    return FlowRun(
        flow_id=uuid4(),
        name="run",
        tags=[WorkflowTag.RELATED_NODE.render(identifier=node_id) for node_id in node_ids],
    )


async def test_enrich_resolves_kind_for_an_existing_node(db: InfrahubDatabase, person_john_main: Node) -> None:
    enricher = RelatedNodeEnricher(db=db, tag_decoder=WorkflowTagDecoder())

    result = await enricher.enrich(flows=[_run_tagged_with([person_john_main.id])])

    assert result.nodes[person_john_main.id].kind == "TestPerson"


async def test_enrich_labels_a_tagged_id_with_no_node(db: InfrahubDatabase, person_john_main: Node) -> None:
    missing_id = str(uuid4())
    enricher = RelatedNodeEnricher(db=db, tag_decoder=WorkflowTagDecoder())

    result = await enricher.enrich(flows=[_run_tagged_with([person_john_main.id, missing_id])])

    assert result.nodes[person_john_main.id].kind == "TestPerson"
    assert result.nodes[missing_id].kind == UNRESOLVED_NODE_KIND
