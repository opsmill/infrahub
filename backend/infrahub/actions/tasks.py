from __future__ import annotations

from infrahub_sdk.graphql import Mutation
from prefect import flow

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import setup_triggers_specific
from infrahub.workflows.utils import add_tags

from .gather import gather_trigger_action_rules
from .models import EventGroupMember  # noqa: TC001  needed for prefect flow


@flow(
    name="action-add-node-to-group",
    flow_run_name="Adding node={node_id} to group={group_id}",
)
async def add_node_to_group(
    branch_name: str,
    node_id: str,
    group_id: str,
    context: InfrahubContext,  # noqa: ARG001
    service: InfrahubServices,
) -> None:
    await add_tags(branches=[branch_name], nodes=[node_id, group_id])

    mutation = Mutation(
        mutation="RelationshipAdd",
        input_data={"data": {"id": group_id, "name": "members", "nodes": [{"id": node_id}]}},
        query={"ok": None},
    )

    await service.client.execute_graphql(query=mutation.render(), branch_name=branch_name)


@flow(
    name="action-remove-node-from-group",
    flow_run_name="Removing node={node_id} from group={group_id}",
)
async def remove_node_from_group(
    branch_name: str,
    node_id: str,
    group_id: str,
    context: InfrahubContext,  # noqa: ARG001
    service: InfrahubServices,
) -> None:
    await add_tags(branches=[branch_name], nodes=[node_id, group_id])

    mutation = Mutation(
        mutation="RelationshipRemove",
        input_data={"data": {"id": group_id, "name": "members", "nodes": [{"id": node_id}]}},
        query={"ok": None},
    )

    await service.client.execute_graphql(query=mutation.render(), branch_name=branch_name)


@flow(
    name="action-run-generator",
    flow_run_name="Running generator generator_definition_id={generator_definition_id} for nodes={node_ids}",
)
async def run_generator(
    branch_name: str,
    node_ids: list[str],
    generator_definition_id: str,
    context: InfrahubContext,  # noqa: ARG001
    service: InfrahubServices,
) -> None:
    await add_tags(branches=[branch_name], nodes=node_ids + [generator_definition_id])
    await _run_generator(
        branch_name=branch_name, generator_definition_id=generator_definition_id, node_ids=node_ids, service=service
    )


@flow(
    name="action-run-generator-group-event",
    flow_run_name="Running generator",
)
async def run_generator_group_event(
    branch_name: str,
    members: list[EventGroupMember],
    generator_definition_id: str,
    context: InfrahubContext,  # noqa: ARG001
    service: InfrahubServices,
) -> None:
    node_ids = [node.id for node in members]
    await add_tags(branches=[branch_name], nodes=node_ids + [generator_definition_id])
    await _run_generator(
        branch_name=branch_name, generator_definition_id=generator_definition_id, node_ids=node_ids, service=service
    )


@flow(
    name="configure-action-rules",
    flow_run_name="Configure updated action rules and triggers",
)
async def configure_action_rules(
    service: InfrahubServices,
) -> None:
    await setup_triggers_specific(
        gatherer=gather_trigger_action_rules, trigger_type=TriggerType.ACTION_TRIGGER_RULE, db=service.database
    )  # type: ignore[misc]


async def _run_generator(
    branch_name: str,
    node_ids: list[str],
    generator_definition_id: str,
    service: InfrahubServices,
) -> None:
    mutation = Mutation(
        mutation="CoreGeneratorDefinitionRun",
        input_data={"data": {"id": generator_definition_id, "nodes": node_ids}},
        query={"ok": None},
    )

    await service.client.execute_graphql(query=mutation.render(), branch_name=branch_name)
