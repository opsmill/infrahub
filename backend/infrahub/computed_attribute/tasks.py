from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from infrahub_sdk.exceptions import URLNotFoundError
from infrahub_sdk.protocols import CoreTransformPython
from infrahub_sdk.template import Jinja2Template
from prefect import State, flow
from prefect.client.orchestration import get_client as get_prefect_client
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
from prefect.client.schemas.objects import StateType
from prefect.logging import get_run_logger
from prefect.states import Completed, Failed

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core.constants import ComputedAttributeKind, InfrahubKind
from infrahub.core.registry import registry
from infrahub.events import BranchDeletedEvent
from infrahub.git.repository import get_initialized_repo
from infrahub.trigger.models import TriggerSetupReport, TriggerType
from infrahub.trigger.setup import setup_triggers, setup_triggers_specific
from infrahub.workers.dependencies import get_client, get_component, get_database, get_workflow
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE,
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
    TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
)
from infrahub.workflows.utils import add_tags, wait_for_schema_to_converge

from .gather import gather_trigger_computed_attribute_jinja2, gather_trigger_computed_attribute_python
from .models import (
    ComputedAttrJinja2GraphQL,
    ComputedAttrJinja2GraphQLResponse,
    ComputedAttrJinja2TriggerDefinition,
    PythonTransformTarget,
)

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub.core.schema.computed_attribute import ComputedAttribute

UPDATE_ATTRIBUTE = """
mutation UpdateAttribute(
    $id: String!,
    $kind: String!,
    $attribute: String!,
    $value: String!
    $context_account_id: String!
  ) {
  InfrahubUpdateComputedAttribute(
    context: {account: {id: $context_account_id}},
    data: {id: $id, attribute: $attribute, value: $value, kind: $kind}
  ) {
    ok
  }
}
"""


async def wait_until_flow_runs_are_completed(
    flow_run_ids: list[UUID], interval: int = 2, timeout: int | None = 3600
) -> list[UUID]:
    pending_flow_run_ids: list[UUID] = flow_run_ids
    failed_flow_run_ids: list[UUID] = []

    ACTIVE_FLOW_RUN_STATES = [StateType.RUNNING, StateType.PENDING, StateType.SCHEDULED]
    FAILED_FLOW_RUN_STATES = [StateType.FAILED, StateType.CANCELLED, StateType.CRASHED]

    start_time = time.time()

    async with get_prefect_client(sync_client=False) as prefect_client:
        while pending_flow_run_ids:
            flow_runs = await prefect_client.read_flow_runs(
                flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=pending_flow_run_ids))
            )
            pending_flow_run_ids = [
                flow_run.id for flow_run in flow_runs if flow_run.state_type in ACTIVE_FLOW_RUN_STATES
            ]
            failed_flow_run_ids.extend(
                [flow_run.id for flow_run in flow_runs if flow_run.state_type in FAILED_FLOW_RUN_STATES]
            )
            await asyncio.sleep(interval)
            if timeout and time.time() - start_time > timeout:
                raise TimeoutError(f"Timeout of {timeout} seconds reached while waiting for flow runs to complete")

        return failed_flow_run_ids


@flow(
    name="computed_attribute_process_transform",
    flow_run_name="Process computed attribute for {computed_attribute_kind}.{computed_attribute_name}",
)
async def process_transform(
    branch_name: str,
    node_kind: str,
    object_id: str,
    computed_attribute_name: str,  # noqa: ARG001
    computed_attribute_kind: str,  # noqa: ARG001
    context: InfrahubContext,
    updated_fields: list[str] | None = None,  # noqa: ARG001
) -> None:
    await add_tags(branches=[branch_name], nodes=[object_id])
    client = get_client()

    schema_branch = registry.schema.get_schema_branch(name=branch_name)
    node_schema = schema_branch.get_node(name=node_kind, duplicate=False)
    transform_attributes: dict[str, ComputedAttribute] = {}
    for attribute in node_schema.attributes:
        if attribute.computed_attribute and attribute.computed_attribute.kind == ComputedAttributeKind.TRANSFORM_PYTHON:
            transform_attributes[attribute.name] = attribute.computed_attribute

    if not transform_attributes:
        return

    for attribute_name, transform_attribute in transform_attributes.items():
        transform = await client.get(
            kind=CoreTransformPython,
            branch=branch_name,
            id=transform_attribute.transform,
            prefetch_relationships=True,
            populate_store=True,
        )

        if not transform:
            continue

        repo_node = await client.get(
            kind=str(transform.repository.peer.typename),
            branch=branch_name,
            id=transform.repository.peer.id,
            raise_when_missing=True,
        )

        repo = await get_initialized_repo(
            client=client,
            repository_id=transform.repository.peer.id,
            name=transform.repository.peer.name.value,
            repository_kind=str(transform.repository.peer.typename),
            commit=repo_node.commit.value,
        )

        data = await client.query_gql_query(
            name=transform.query.id,
            branch_name=branch_name,
            variables={"id": object_id},
            update_group=True,
            subscribers=[object_id],
        )

        transformed_data = await repo.execute_python_transform.with_options(timeout_seconds=transform.timeout.value)(
            client=client,
            branch_name=branch_name,
            commit=repo_node.commit.value,
            location=f"{transform.file_path.value}::{transform.class_name.value}",
            data=data,
            convert_query_response=transform.convert_query_response.value,
        )  # type: ignore[call-overload]

        await client.execute_graphql(
            query=UPDATE_ATTRIBUTE,
            variables={
                "id": object_id,
                "kind": node_kind,
                "attribute": attribute_name,
                "value": transformed_data,
                "context_account_id": context.account.account_id,
            },
            branch_name=branch_name,
        )


@flow(
    name="trigger_update_python_computed_attributes",
    flow_run_name="Trigger updates for computed attributes on branch {branch_name} for {computed_attribute_kind}.{computed_attribute_name}",
)
async def trigger_update_python_computed_attributes(
    branch_name: str,
    computed_attribute_name: str,
    computed_attribute_kind: str,
    context: InfrahubContext,
) -> None:
    await add_tags(branches=[branch_name])

    nodes = await get_client().all(kind=computed_attribute_kind, branch=branch_name)

    for node in nodes:
        await get_workflow().submit_workflow(
            workflow=COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
            context=context,
            parameters={
                "branch_name": branch_name,
                "node_kind": computed_attribute_kind,
                "object_id": node.id,
                "computed_attribute_name": computed_attribute_name,
                "computed_attribute_kind": computed_attribute_kind,
                "context": context,
            },
        )


@flow(
    name="computed-attribute-jinja2-update-value",
    flow_run_name="Update value for computed attribute {node_kind}:{attribute_name}",
)
async def computed_attribute_jinja2_update_value(
    branch_name: str,
    obj: ComputedAttrJinja2GraphQLResponse,
    node_kind: str,
    attribute_name: str,
    template: Jinja2Template,
    context: InfrahubContext,
) -> None:
    log = get_run_logger()
    client = get_client()

    await add_tags(branches=[branch_name], nodes=[obj.node_id], db_change=True)

    value = await template.render(variables=obj.variables)
    if value == obj.computed_attribute_value:
        log.debug(f"Ignoring to update {obj} with existing value on {attribute_name}={value}")
        return

    try:
        await client.execute_graphql(
            query=UPDATE_ATTRIBUTE,
            variables={
                "id": obj.node_id,
                "kind": node_kind,
                "attribute": attribute_name,
                "value": value,
                "context_account_id": context.account.account_id,
            },
            branch_name=branch_name,
        )
        log.info(f"Updating computed attribute {node_kind}.{attribute_name}='{value}' ({obj.node_id})")
    except URLNotFoundError:
        log.warning(
            f"Update of computed attribute {node_kind}.{attribute_name} failed for branch {branch_name} (not found)"
        )


@flow(
    name="computed_attribute_process_jinja2",
    flow_run_name="Process computed attribute for {computed_attribute_kind}.{computed_attribute_name}",
)
async def process_jinja2(
    branch_name: str,
    node_kind: str,
    object_id: str,
    computed_attribute_name: str,
    computed_attribute_kind: str,
    context: InfrahubContext,
    updated_fields: list[str] | None = None,
) -> State[Any]:
    log = get_run_logger()
    client = get_client()

    await add_tags(branches=[branch_name])
    updates: list[str] = updated_fields or []

    target_branch_schema = (
        branch_name if branch_name in registry.get_altered_schema_branches() else registry.default_branch
    )
    schema_branch = registry.schema.get_schema_branch(name=target_branch_schema)
    node_schema = schema_branch.get_node(name=computed_attribute_kind, duplicate=False)
    computed_macros = [
        attrib
        for attrib in schema_branch.computed_attributes.get_impacted_jinja2_targets(kind=node_kind, updates=updates)
        if attrib.kind == computed_attribute_kind and attrib.attribute.name == computed_attribute_name
    ]

    tasks: dict[UUID, str] = {}

    for computed_macro in computed_macros:
        found: list[ComputedAttrJinja2GraphQLResponse] = []
        template_string = "n/a"
        if computed_macro.attribute.computed_attribute and computed_macro.attribute.computed_attribute.jinja2_template:
            template_string = computed_macro.attribute.computed_attribute.jinja2_template

        jinja_template = Jinja2Template(template=template_string)
        variables = jinja_template.get_variables()

        attribute_graphql = ComputedAttrJinja2GraphQL(
            node_schema=node_schema, attribute_schema=computed_macro.attribute, variables=variables
        )

        for id_filter in computed_macro.node_filters:
            query = attribute_graphql.render_graphql_query(query_filter=id_filter, filter_id=object_id)
            try:
                response = await client.execute_graphql(query=query, branch_name=branch_name)
            except URLNotFoundError:
                log.warning(
                    f"Process computed attributes for {computed_attribute_kind}.{computed_attribute_name} failed for branch {branch_name} (not found)"
                )
                return
            output = attribute_graphql.parse_response(response=response)
            found.extend(output)

        if not found:
            log.debug("No nodes found that requires updates")

        # Create all the tasks in Prefect, for now creating the task one by one to not overload the prefect server
        for node in found:
            task = await get_workflow().submit_workflow(
                workflow=COMPUTED_ATTRIBUTE_JINJA2_UPDATE_VALUE,
                parameters={
                    "branch_name": branch_name,
                    "obj": node,
                    "node_kind": node_schema.kind,
                    "attribute_name": computed_macro.attribute.name,
                    "template": jinja_template,
                },
                context=context,
            )
            tasks[task.id] = node.node_id

    # Wait for all tasks to complete and report on the overall success or failure of the task
    # Calculate a timeout based on the number of nodes to update
    timeout = len(found) * 3 if len(found) > 50 else len(found) * 10
    failed_flow_run_ids = await wait_until_flow_runs_are_completed(list(tasks.keys()), interval=2, timeout=timeout)
    failed_nodes: list[str] = [tasks[flow_run_id] for flow_run_id in failed_flow_run_ids]

    if failed_flow_run_ids:
        return Failed(
            message=f"Failed to update computed attribute {computed_attribute_kind}.{computed_attribute_name} on {branch_name}: {failed_nodes}"
        )

    return Completed(message=f"Successfully updated {len(found)} computed attributes")


@flow(
    name="trigger_update_jinja2_computed_attributes",
    flow_run_name="Trigger updates for computed attributes for {computed_attribute_kind}.{computed_attribute_name}",
)
async def trigger_update_jinja2_computed_attributes(
    branch_name: str,
    computed_attribute_name: str,
    computed_attribute_kind: str,
    context: InfrahubContext,
) -> None:
    await add_tags(branches=[branch_name])

    client = get_client()

    # NOTE we only need the id of the nodes, we need to ooptimize the query here
    nodes = await client.all(kind=computed_attribute_kind, branch=branch_name)

    for node in nodes:
        await get_workflow().submit_workflow(
            workflow=COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
            context=context,
            parameters={
                "branch_name": branch_name,
                "computed_attribute_name": computed_attribute_name,
                "computed_attribute_kind": computed_attribute_kind,
                "node_kind": computed_attribute_kind,
                "object_id": node.id,
                "context": context,
            },
        )


@flow(name="computed-attribute-setup-jinja2", flow_run_name="Setup computed attributes in task-manager")
async def computed_attribute_setup_jinja2(
    context: InfrahubContext, branch_name: str | None = None, event_name: str | None = None
) -> None:
    database = await get_database()
    async with database.start_session() as db:
        log = get_run_logger()

        if branch_name:
            await add_tags(branches=[branch_name])
            component = await get_component()
            await wait_for_schema_to_converge(branch_name=branch_name, component=component, db=db, log=log)

        report: TriggerSetupReport = await setup_triggers_specific(
            gatherer=gather_trigger_computed_attribute_jinja2, trigger_type=TriggerType.COMPUTED_ATTR_JINJA2
        )  # type: ignore[misc]
        # Configure all ComputedAttrJinja2Trigger in Prefect

        all_triggers = report.triggers_with_type(trigger_type=ComputedAttrJinja2TriggerDefinition)

        # Since we can have multiple trigger per NodeKind
        # we need to extract the list of unique node that should be processed, this is done by filtering the triggers that targets_self
        modified_triggers = [
            trigger
            for trigger in report.modified_triggers_with_type(trigger_type=ComputedAttrJinja2TriggerDefinition)
            if trigger.targets_self
        ]

        for modified_trigger in modified_triggers:
            if event_name != BranchDeletedEvent.event_name and modified_trigger.branch == branch_name:
                if branch_name != registry.default_branch:
                    default_branch_triggers = [
                        trigger
                        for trigger in all_triggers
                        if trigger.branch == registry.default_branch
                        and trigger.targets_self
                        and trigger.computed_attribute.kind == modified_trigger.computed_attribute.kind
                        and trigger.computed_attribute.attribute.name
                        == modified_trigger.computed_attribute.attribute.name
                    ]
                    if (
                        default_branch_triggers
                        and len(default_branch_triggers) == 1
                        and default_branch_triggers[0].template_hash == modified_trigger.template_hash
                    ):
                        log.debug(
                            f"Skipping computed attribute updates for {modified_trigger.computed_attribute.kind}."
                            f"{modified_trigger.computed_attribute.attribute.name} [{branch_name}], schema is identical to default branch"
                        )
                        continue

                await get_workflow().submit_workflow(
                    workflow=TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
                    context=context,
                    parameters={
                        "branch_name": modified_trigger.branch,
                        "computed_attribute_name": modified_trigger.computed_attribute.attribute.name,
                        "computed_attribute_kind": modified_trigger.computed_attribute.kind,
                    },
                )

        log.info(f"{report.in_use_count} Computed Attribute for Jinja2 automation configuration completed")


@flow(
    name="computed-attribute-setup-python",
    flow_run_name="Setup computed attributes for Python transforms in task-manager",
)
async def computed_attribute_setup_python(
    context: InfrahubContext,
    branch_name: str | None = None,
    event_name: str | None = None,
    commit: str | None = None,  # noqa: ARG001
) -> None:
    database = await get_database()
    async with database.start_session() as db:
        log = get_run_logger()

        branch_name = branch_name or registry.default_branch
        if branch_name:
            await add_tags(branches=[branch_name])
            component = await get_component()
            await wait_for_schema_to_converge(branch_name=branch_name, component=component, db=db, log=log)

        triggers_python, triggers_python_query = await gather_trigger_computed_attribute_python(db=db)

        # Since we can have multiple trigger per NodeKind
        # we need to extract the list of unique node that should be processed
        # also
        # Because the automation in Prefect doesn't capture all information about the computed attribute
        # we can't tell right now if a given computed attribute has changed and need to be updated
        unique_nodes: set[tuple[str, str, str]] = {
            (
                trigger.branch,
                trigger.computed_attribute.computed_attribute.kind,
                trigger.computed_attribute.computed_attribute.attribute.name,
            )
            for trigger in triggers_python
        }
        for branch, kind, attribute_name in unique_nodes:
            if event_name != BranchDeletedEvent.event_name and branch == branch_name:
                log.info(f"Triggering update for {kind}.{attribute_name} on {branch}")
                await get_workflow().submit_workflow(
                    workflow=TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
                    context=context,
                    parameters={
                        "branch_name": branch_name,
                        "computed_attribute_name": attribute_name,
                        "computed_attribute_kind": kind,
                    },
                )

        async with get_prefect_client(sync_client=False) as prefect_client:
            await setup_triggers(
                client=prefect_client,
                triggers=triggers_python,
                trigger_type=TriggerType.COMPUTED_ATTR_PYTHON,
            )  # type: ignore[misc]
            log.info(f"{len(triggers_python)} Computed Attribute for Python automation configuration completed")

            await setup_triggers(
                client=prefect_client,
                triggers=triggers_python_query,
                trigger_type=TriggerType.COMPUTED_ATTR_PYTHON_QUERY,
            )  # type: ignore[misc]
            log.info(
                f"{len(triggers_python_query)} Computed Attribute for Python Query automation configuration completed"
            )


@flow(
    name="query-computed-attribute-transform-targets",
    flow_run_name="Query for potential targets of computed attributes for {node_kind}",
)
async def query_transform_targets(
    branch_name: str,
    node_kind: str,  # noqa: ARG001
    object_id: str,
    context: InfrahubContext,
) -> None:
    await add_tags(branches=[branch_name])
    schema_branch = registry.schema.get_schema_branch(name=branch_name)
    targets = await get_client().execute_graphql(
        query=GATHER_GRAPHQL_QUERY_SUBSCRIBERS, variables={"members": [object_id]}, branch_name=branch_name
    )

    subscribers: list[PythonTransformTarget] = []

    for group in targets[InfrahubKind.GRAPHQLQUERYGROUP]["edges"]:
        for subscriber in group["node"]["subscribers"]["edges"]:
            subscribers.append(
                PythonTransformTarget(object_id=subscriber["node"]["id"], kind=subscriber["node"]["__typename"])
            )

    nodes_with_computed_attributes = schema_branch.computed_attributes.get_python_attributes_per_node()
    for subscriber in subscribers:
        if subscriber.kind in nodes_with_computed_attributes:
            for computed_attribute in nodes_with_computed_attributes[subscriber.kind]:
                await get_workflow().submit_workflow(
                    workflow=COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
                    context=context,
                    parameters={
                        "branch_name": branch_name,
                        "node_kind": subscriber.kind,
                        "object_id": subscriber.object_id,
                        "computed_attribute_name": computed_attribute.name,
                        "computed_attribute_kind": subscriber.kind,
                        "context": context,
                    },
                )


GATHER_GRAPHQL_QUERY_SUBSCRIBERS = """
query GatherGraphQLQuerySubscribers($members: [ID!]) {
  CoreGraphQLQueryGroup(members__ids: $members) {
    edges {
      node {
        subscribers {
          edges {
            node {
              id
              __typename
            }
          }
        }
      }
    }
  }
}
"""
