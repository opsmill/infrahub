from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreTransformPython
from infrahub_sdk.template import Jinja2Template
from prefect import flow
from prefect.client.orchestration import get_client
from prefect.logging import get_run_logger

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core.constants import ComputedAttributeKind, InfrahubKind
from infrahub.core.registry import registry
from infrahub.events import BranchDeletedEvent
from infrahub.git.repository import get_initialized_repo
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import setup_triggers
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
    TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
)
from infrahub.workflows.utils import add_tags, wait_for_schema_to_converge

from .gather import gather_trigger_computed_attribute_jinja2, gather_trigger_computed_attribute_python
from .models import ComputedAttrJinja2GraphQL, ComputedAttrJinja2GraphQLResponse, PythonTransformTarget

if TYPE_CHECKING:
    from infrahub.core.schema.computed_attribute import ComputedAttribute

UPDATE_ATTRIBUTE = """
mutation UpdateAttribute(
    $id: String!,
    $kind: String!,
    $attribute: String!,
    $value: String!
  ) {
  InfrahubUpdateComputedAttribute(
    data: {id: $id, attribute: $attribute, value: $value, kind: $kind}
  ) {
    ok
  }
}
"""


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
    context: InfrahubContext,  # noqa: ARG001
    service: InfrahubServices,
    updated_fields: list[str] | None = None,  # noqa: ARG001
) -> None:
    await add_tags(branches=[branch_name], nodes=[object_id])

    schema_branch = registry.schema.get_schema_branch(name=branch_name)
    node_schema = schema_branch.get_node(name=node_kind, duplicate=False)
    transform_attributes: dict[str, ComputedAttribute] = {}
    for attribute in node_schema.attributes:
        if attribute.computed_attribute and attribute.computed_attribute.kind == ComputedAttributeKind.TRANSFORM_PYTHON:
            transform_attributes[attribute.name] = attribute.computed_attribute

    if not transform_attributes:
        return

    for attribute_name, transform_attribute in transform_attributes.items():
        transform = await service.client.get(
            kind=CoreTransformPython,
            branch=branch_name,
            id=transform_attribute.transform,
            prefetch_relationships=True,
            populate_store=True,
        )

        if not transform:
            continue

        repo_node = await service.client.get(
            kind=str(transform.repository.peer.typename),
            branch=branch_name,
            id=transform.repository.peer.id,
            raise_when_missing=True,
        )

        repo = await get_initialized_repo(
            repository_id=transform.repository.peer.id,
            name=transform.repository.peer.name.value,
            service=service,
            repository_kind=str(transform.repository.peer.typename),
            commit=repo_node.commit.value,
        )  # type: ignore[misc]

        data = await service.client.query_gql_query(
            name=transform.query.peer.name.value,
            branch_name=branch_name,
            variables={"id": object_id},
            update_group=True,
            subscribers=[object_id],
        )

        transformed_data = await repo.execute_python_transform.with_options(timeout_seconds=transform.timeout.value)(
            branch_name=branch_name,
            commit=repo_node.commit.value,
            location=f"{transform.file_path.value}::{transform.class_name.value}",
            data=data,
            client=service.client,
            convert_query_response=transform.convert_query_response.value,
        )  # type: ignore[misc]

        await service.client.execute_graphql(
            query=UPDATE_ATTRIBUTE,
            variables={
                "id": object_id,
                "kind": node_kind,
                "attribute": attribute_name,
                "value": transformed_data,
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
    service: InfrahubServices,
) -> None:
    await add_tags(branches=[branch_name])

    nodes = await service.client.all(kind=computed_attribute_kind, branch=branch_name)

    for node in nodes:
        await service.workflow.submit_workflow(
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
    name="process_computed_attribute_value_jinja2",
    flow_run_name="Update value for computed attribute {attribute_name}",
)
async def update_computed_attribute_value_jinja2(
    branch_name: str,
    obj: ComputedAttrJinja2GraphQLResponse,
    node_kind: str,
    attribute_name: str,
    template: Jinja2Template,
    service: InfrahubServices,
) -> None:
    log = get_run_logger()

    await add_tags(branches=[branch_name], nodes=[obj.node_id], db_change=True)

    value = await template.render(variables=obj.variables)
    if value == obj.computed_attribute_value:
        log.debug(f"Ignoring to update {obj} with existing value on {attribute_name}={value}")
        return

    await service.client.execute_graphql(
        query=UPDATE_ATTRIBUTE,
        variables={
            "id": obj.node_id,
            "kind": node_kind,
            "attribute": attribute_name,
            "value": value,
        },
        branch_name=branch_name,
    )
    log.info(f"Updating computed attribute {node_kind}.{attribute_name}='{value}' ({obj.node_id})")


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
    context: InfrahubContext,  # noqa: ARG001
    service: InfrahubServices,
    updated_fields: list[str] | None = None,
) -> None:
    log = get_run_logger()

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
            response = await service.client.execute_graphql(query=query, branch_name=branch_name)
            output = attribute_graphql.parse_response(response=response)
            found.extend(output)

        if not found:
            log.debug("No nodes found that requires updates")

        batch = await service.client.create_batch()
        for node in found:
            batch.add(
                task=update_computed_attribute_value_jinja2,
                branch_name=branch_name,
                obj=node,
                node_kind=node_schema.kind,
                attribute_name=computed_macro.attribute.name,
                template=jinja_template,
                service=service,
            )

        _ = [response async for _, response in batch.execute()]


@flow(
    name="trigger_update_jinja2_computed_attributes",
    flow_run_name="Trigger updates for computed attributes for {computed_attribute_kind}.{computed_attribute_name}",
)
async def trigger_update_jinja2_computed_attributes(
    branch_name: str,
    computed_attribute_name: str,
    computed_attribute_kind: str,
    context: InfrahubContext,
    service: InfrahubServices,
) -> None:
    await add_tags(branches=[branch_name])

    # NOTE we only need the id of the nodes, we need to ooptimize the query here
    nodes = await service.client.all(kind=computed_attribute_kind, branch=branch_name)

    for node in nodes:
        await service.workflow.submit_workflow(
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
    service: InfrahubServices, context: InfrahubContext, branch_name: str | None = None, event_name: str | None = None
) -> None:
    async with service.database.start_session() as db:
        log = get_run_logger()

        if branch_name:
            await add_tags(branches=[branch_name])
            await wait_for_schema_to_converge(branch_name=branch_name, component=service.component, db=db, log=log)

        triggers = await gather_trigger_computed_attribute_jinja2()

        # Since we can have multiple trigger per NodeKind
        # we need to extract the list of unique node that should be processed
        # also
        # Because the automation in Prefect doesn't capture all information about the computed attribute
        # we can't tell right now if a given computed attribute has changed and need to be updated
        unique_nodes: set[tuple[str, str, str]] = {
            (trigger.branch, trigger.computed_attribute.kind, trigger.computed_attribute.attribute.name)
            for trigger in triggers
        }
        for branch, kind, attribute_name in unique_nodes:
            if event_name != BranchDeletedEvent.event_name and branch == branch_name:
                await service.workflow.submit_workflow(
                    workflow=TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
                    context=context,
                    parameters={
                        "branch_name": branch,
                        "computed_attribute_name": attribute_name,
                        "computed_attribute_kind": kind,
                    },
                )

        # Configure all ComputedAttrJinja2Trigger in Prefect
        async with get_client(sync_client=False) as prefect_client:
            await setup_triggers(
                client=prefect_client,
                triggers=triggers,
                trigger_type=TriggerType.COMPUTED_ATTR_JINJA2,
                force_update=False,
            )  # type: ignore[misc]

        log.info(f"{len(triggers)} Computed Attribute for Jinja2 automation configuration completed")


@flow(
    name="computed-attribute-setup-python",
    flow_run_name="Setup computed attributes for Python transforms in task-manager",
)
async def computed_attribute_setup_python(
    service: InfrahubServices,
    context: InfrahubContext,
    branch_name: str | None = None,
    event_name: str | None = None,
    commit: str | None = None,  # noqa: ARG001
) -> None:
    async with service.database.start_session() as db:
        log = get_run_logger()

        branch_name = branch_name or registry.default_branch

        if branch_name:
            await add_tags(branches=[branch_name])
            await wait_for_schema_to_converge(branch_name=branch_name, component=service.component, db=db, log=log)

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
                await service.workflow.submit_workflow(
                    workflow=TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
                    context=context,
                    parameters={
                        "branch_name": branch_name,
                        "computed_attribute_name": attribute_name,
                        "computed_attribute_kind": kind,
                    },
                )

        async with get_client(sync_client=False) as prefect_client:
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
    service: InfrahubServices,
) -> None:
    await add_tags(branches=[branch_name])
    schema_branch = registry.schema.get_schema_branch(name=branch_name)
    targets = await service.client.execute_graphql(
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
                await service.workflow.submit_workflow(
                    workflow=COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
                    context=context,
                    parameters={
                        "branch_name": branch_name,
                        "node_kind": subscriber.kind,
                        "object_id": subscriber.object_id,
                        "computed_attribute_name": computed_attribute.name,
                        "computed_attribute_kind": subscriber.kind,
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
