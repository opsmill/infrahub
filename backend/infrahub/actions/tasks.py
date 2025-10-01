from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from infrahub_sdk.graphql import Mutation, Query
from infrahub_sdk.types import Order
from prefect import flow

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core.constants import InfrahubKind
from infrahub.generators.models import (
    GeneratorDefinitionModel,
    RequestGeneratorRun,
)
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import setup_triggers_specific
from infrahub.workers.dependencies import get_client, get_workflow
from infrahub.workflows.catalogue import REQUEST_GENERATOR_RUN
from infrahub.workflows.utils import add_tags

from .gather import gather_trigger_action_rules
from .models import EventGroupMember  # noqa: TC001  needed for prefect flow

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.node import InfrahubNode


def get_generator_run_query(definition_id: str, target_ids: list[str]) -> Query:
    return Query(
        name=InfrahubKind.GENERATORDEFINITION,
        query={
            InfrahubKind.GENERATORDEFINITION: {
                "@filters": {
                    "ids": [definition_id],
                },
                "edges": {
                    "node": {
                        "id": None,
                        "name": {
                            "value": None,
                        },
                        "class_name": {
                            "value": None,
                        },
                        "file_path": {
                            "value": None,
                        },
                        "query": {
                            "node": {
                                "name": {
                                    "value": None,
                                },
                            },
                        },
                        "convert_query_response": {
                            "value": None,
                        },
                        "parameters": {
                            "value": None,
                        },
                        "targets": {
                            "node": {
                                "id": None,
                                "members": {
                                    "@filters": {
                                        "ids": target_ids,
                                    },
                                    "edges": {
                                        "node": {
                                            "__typename": None,
                                            "id": None,
                                            "display_label": None,
                                        },
                                    },
                                },
                            },
                        },
                        "repository": {
                            "node": {
                                "__typename": None,
                                "id": None,
                                "name": {
                                    "value": None,
                                },
                                f"... on {InfrahubKind.REPOSITORY}": {
                                    "commit": {
                                        "value": None,
                                    },
                                },
                                f"... on {InfrahubKind.READONLYREPOSITORY}": {
                                    "commit": {
                                        "value": None,
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    )


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
    context: InfrahubContext,
    service: InfrahubServices,  # noqa: ARG001
) -> None:
    await add_tags(branches=[branch_name], nodes=node_ids + [generator_definition_id])

    client = get_client()

    await _run_generators(
        branch_name=branch_name,
        node_ids=node_ids,
        generator_definition_id=generator_definition_id,
        client=client,
        context=context,
    )


@flow(
    name="action-run-generator-group-event",
    flow_run_name="Running generator",
)
async def run_generator_group_event(
    branch_name: str,
    members: list[EventGroupMember],
    generator_definition_id: str,
    context: InfrahubContext,
    service: InfrahubServices,  # noqa: ARG001
) -> None:
    node_ids = [node.id for node in members]
    await add_tags(branches=[branch_name], nodes=node_ids + [generator_definition_id])

    client = get_client()

    await _run_generators(
        branch_name=branch_name,
        node_ids=node_ids,
        generator_definition_id=generator_definition_id,
        client=client,
        context=context,
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


async def _get_targets(
    branch_name: str,
    targets: list[dict[str, Any]],
    client: InfrahubClient,
) -> dict[str, dict[str, InfrahubNode]]:
    """Get the targets per kind in order to extract the variables."""

    targets_per_kind: dict[str, dict[str, InfrahubNode]] = defaultdict(dict)

    for target in targets:
        targets_per_kind[target["node"]["__typename"]][target["node"]["id"]] = None

    for kind, values in targets_per_kind.items():
        nodes = await client.filters(
            kind=kind, branch=branch_name, ids=list(values.keys()), populate_store=False, order=Order(disable=True)
        )
        for node in nodes:
            targets_per_kind[kind][node.id] = node

    return targets_per_kind


async def _run_generators(
    branch_name: str,
    node_ids: list[str],
    generator_definition_id: str,
    client: InfrahubClient,
    context: InfrahubContext | None = None,
) -> None:
    """Fetch generator metadata and submit per-target runs.

    Args:
        branch_name: Branch on which to execute.
        node_ids: Node IDs to run against (restricts selection if provided).
        generator_definition_id: Generator definition to execute.
        client: InfrahubClient to query additional data.
        context: Execution context passed to downstream workflow submissions.

    Returns:
        None

    Raises:
        ValueError: If the generator definition is not found or none of the requested
            targets are members of the target group.
    """
    response = await client.execute_graphql(
        query=get_generator_run_query(definition_id=generator_definition_id, target_ids=node_ids).render(),
        branch_name=branch_name,
    )
    if not response[InfrahubKind.GENERATORDEFINITION]["edges"]:
        raise ValueError(f"Generator definition {generator_definition_id} not found")

    data = response[InfrahubKind.GENERATORDEFINITION]["edges"][0]["node"]

    if not data["targets"]["node"]["members"]["edges"]:
        raise ValueError(f"Target {node_ids[0]} is not part of the group {data['targets']['node']['id']}")

    targets = data["targets"]["node"]["members"]["edges"]

    targets_per_kind = await _get_targets(branch_name=branch_name, targets=targets, client=client)

    workflow = get_workflow()

    for target in targets:
        node: InfrahubNode | None = None
        if data["parameters"]["value"]:
            node = targets_per_kind[target["node"]["__typename"]][target["node"]["id"]]

        request_generator_run_model = RequestGeneratorRun(
            generator_definition=GeneratorDefinitionModel(
                definition_id=generator_definition_id,
                definition_name=data["name"]["value"],
                class_name=data["class_name"]["value"],
                file_path=data["file_path"]["value"],
                query_name=data["query"]["node"]["name"]["value"],
                convert_query_response=data["convert_query_response"]["value"],
                group_id=data["targets"]["node"]["id"],
                parameters=data["parameters"]["value"],
            ),
            commit=data["repository"]["node"]["commit"]["value"],
            repository_id=data["repository"]["node"]["id"],
            repository_name=data["repository"]["node"]["name"]["value"],
            repository_kind=data["repository"]["node"]["__typename"],
            branch_name=branch_name,
            query=data["query"]["node"]["name"]["value"],
            variables=await node.extract(params=data["parameters"]["value"]) if node else {},
            target_id=target["node"]["id"],
            target_name=target["node"]["display_label"],
        )
        await workflow.submit_workflow(
            workflow=REQUEST_GENERATOR_RUN, context=context, parameters={"model": request_generator_run_model}
        )
