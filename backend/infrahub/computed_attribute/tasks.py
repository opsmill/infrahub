from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.protocols import (
    CoreNode,  # noqa: TC002
    CoreTransformPython,
)
from prefect import flow
from prefect.client.orchestration import get_client
from prefect.logging import get_run_logger

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core.constants import ComputedAttributeKind, InfrahubKind
from infrahub.core.registry import registry
from infrahub.git.repository import get_initialized_repo
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.support.macro import MacroDefinition
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import setup_triggers
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
    UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM,
)
from infrahub.workflows.utils import add_tags, wait_for_schema_to_converge

from .gather import gather_trigger_computed_attribute_jinja2, gather_trigger_computed_attribute_python
from .models import (
    PythonTransformTarget,
)

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
    name="process_computed_attribute_transform",
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
            workflow=UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM,
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
    branch_name: str, obj: CoreNode, attribute_name: str, template_value: str, service: InfrahubServices
) -> None:
    log = get_run_logger()

    await add_tags(branches=[branch_name], nodes=[obj.id], db_change=True)

    macro_definition = MacroDefinition(macro=template_value)
    my_filter = {}
    for variable in macro_definition.variables:
        components = variable.split("__")
        if len(components) == 2:
            property_name = components[0]
            property_value = components[1]
            attribute_property = getattr(obj, property_name)
            my_filter[variable] = getattr(attribute_property, property_value)
        elif len(components) == 3:
            relationship_name = components[0]
            property_name = components[1]
            property_value = components[2]
            relationship = getattr(obj, relationship_name)
            try:
                attribute_property = getattr(relationship.peer, property_name)
                my_filter[variable] = getattr(attribute_property, property_value)
            except ValueError:
                my_filter[variable] = ""

    value = macro_definition.render(variables=my_filter)
    existing_value = getattr(obj, attribute_name).value
    if value == existing_value:
        log.debug(f"Ignoring to update {obj} with existing value on {attribute_name}={value}")
        return

    await service.client.execute_graphql(
        query=UPDATE_ATTRIBUTE,
        variables={
            "id": obj.id,
            "kind": obj.get_kind(),
            "attribute": attribute_name,
            "value": value,
        },
        branch_name=branch_name,
    )
    log.info(f"Updating computed attribute {obj.get_kind()}.{attribute_name}='{value}' ({obj.id})")


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
    await service.client.schema.all(branch=branch_name, refresh=True)

    computed_macros = [
        attrib
        for attrib in schema_branch.computed_attributes.get_impacted_jinja2_targets(kind=node_kind, updates=updates)
        if attrib.kind == computed_attribute_kind and attrib.attribute.name == computed_attribute_name
    ]
    for computed_macro in computed_macros:
        found: list[CoreNode] = []
        for id_filter in computed_macro.node_filters:
            filters = {id_filter: object_id}
            nodes: list[CoreNode] = await service.client.filters(
                kind=computed_macro.kind,
                branch=branch_name,
                prefetch_relationships=True,
                populate_store=True,
                **filters,
            )
            found.extend(nodes)

        if not found:
            log.debug("No nodes found that requires updates")

        template_string = "n/a"
        if computed_macro.attribute.computed_attribute and computed_macro.attribute.computed_attribute.jinja2_template:
            template_string = computed_macro.attribute.computed_attribute.jinja2_template

        batch = await service.client.create_batch()
        for node in found:
            batch.add(
                task=update_computed_attribute_value_jinja2,
                branch_name=branch_name,
                obj=node,
                attribute_name=computed_macro.attribute.name,
                template_value=template_string,
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
    service: InfrahubServices, context: InfrahubContext, branch_name: str | None = None
) -> None:
    log = get_run_logger()

    if branch_name:
        await add_tags(branches=[branch_name])
        await wait_for_schema_to_converge(branch_name=branch_name, service=service, log=log)

    triggers = await gather_trigger_computed_attribute_jinja2()

    for trigger in triggers:
        if branch_name and trigger.branch != branch_name:
            continue

        await service.workflow.submit_workflow(
            workflow=TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
            context=context,
            parameters={
                "branch_name": trigger.branch,
                "computed_attribute_name": trigger.computed_attribute.attribute.name,
                "computed_attribute_kind": trigger.computed_attribute.kind,
                "context": context,
            },
        )

    # Configure all ComputedAttrJinja2Trigger in Prefect
    async with get_client(sync_client=False) as prefect_client:
        await setup_triggers(
            client=prefect_client,
            triggers=triggers,
            trigger_type=TriggerType.COMPUTED_ATTR_JINJA2,
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
    commit: str | None = None,  # noqa: ARG001
    trigger_updates: bool = True,
) -> None:
    log = get_run_logger()

    branch_name = branch_name or registry.default_branch

    if branch_name:
        await add_tags(branches=[branch_name])
        await wait_for_schema_to_converge(branch_name=branch_name, service=service, log=log)

    triggers_python, triggers_python_query = await gather_trigger_computed_attribute_python(client=service.client)

    if trigger_updates and branch_name:
        for trigger in triggers_python:
            if trigger.branch != branch_name:
                continue

            log.info(
                f"Triggering update for {trigger.computed_attribute.computed_attribute.attribute.name} on {branch_name}"
            )
            await service.workflow.submit_workflow(
                workflow=TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
                context=context,
                parameters={
                    "branch_name": branch_name,
                    "computed_attribute_name": trigger.computed_attribute.computed_attribute.attribute.name,
                    "computed_attribute_kind": trigger.computed_attribute.computed_attribute.kind,
                    "context": context,
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
        log.info(f"{len(triggers_python_query)} Computed Attribute for Python Query automation configuration completed")


@flow(
    name="computed-attribute-remove",
    flow_run_name="Remove Python based computed attributes",
)
async def computed_attribute_remove(
    branch_name: str,
    context: InfrahubContext,  # noqa: ARG001
) -> None:
    log = get_run_logger()
    await add_tags(branches=[branch_name])

    async with get_client(sync_client=False) as client:
        automations = await client.read_automations()

        prefixes = [
            f"{TriggerType.COMPUTED_ATTR_JINJA2.value}{NAME_SEPARATOR}{branch_name}{NAME_SEPARATOR}",
            f"{TriggerType.COMPUTED_ATTR_PYTHON.value}{NAME_SEPARATOR}{branch_name}{NAME_SEPARATOR}",
            f"{TriggerType.COMPUTED_ATTR_PYTHON_QUERY.value}{NAME_SEPARATOR}{branch_name}{NAME_SEPARATOR}",
        ]

        automations_to_delete = [
            automation for automation in automations if any(automation.name.startswith(prefix) for prefix in prefixes)
        ]

        for automation in automations_to_delete:
            await client.delete_automation(automation_id=automation.id)
            log.info(f"Deleted automation {automation.name} ({automation.id})")


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
                    workflow=UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM,
                    context=context,
                    parameters={
                        "branch_name": branch_name,
                        "node_kind": subscriber.kind,
                        "object_id": subscriber.object_id,
                        "computed_attribute_name": computed_attribute.name,
                        "computed_attribute_kind": subscriber.kind,
                    },
                )


# @task(
#     name="gather-python-transform-attributes",
#     task_run_name="Gather Python transform attributes for {branch_name}",
#     cache_policy=NONE,
# )
# async def gather_python_transform_attributes(
#     branch_name: str, client: InfrahubClient, repositories: dict[str, RepositoryData] | None = None
# ) -> list[PythonTransformComputedAttribute]:
#     log = get_run_logger()
#     schema_branch = registry.schema.get_schema_branch(name=branch_name)
#     branches_with_diff_from_main = registry.get_altered_schema_branches()

#     transform_attributes = schema_branch.computed_attributes.python_attributes_by_transform

#     transform_names = list(transform_attributes.keys())
#     if not transform_names:
#         return []

#     transforms = await client.filters(
#         kind=CoreTransformPython,
#         branch=branch_name,
#         prefetch_relationships=True,
#         populate_store=True,
#         name__values=transform_names,
#     )

#     found_transforms_names = [transform.name.value for transform in transforms]
#     for transform_name in transform_names:
#         if transform_name not in found_transforms_names:
#             log.warning(
#                 msg=f"The transform {transform_name} is assigned to a computed attribute but the transform could not be found in the database."
#             )
#     repositories = repositories or await client.get_list_repositories()

#     computed_attributes: list[PythonTransformComputedAttribute] = []
#     for transform in transforms:
#         for attribute in transform_attributes[transform.name.value]:
#             python_transform_computed_attribute = PythonTransformComputedAttribute(
#                 name=transform.name.value,
#                 branch_name=branch_name,
#                 repository_id=transform.repository.peer.id,
#                 repository_name=transform.repository.peer.name.value,
#                 repository_kind=transform.repository.peer.typename,
#                 query_name=transform.query.peer.name.value,
#                 query_models=transform.query.peer.models.value,
#                 computed_attribute=attribute,
#                 default_schema=branch_name not in branches_with_diff_from_main,
#             )
#             python_transform_computed_attribute.populate_branch_commit(
#                 repository_data=repositories.get(transform.repository.peer.name.value)
#             )
#             computed_attributes.append(python_transform_computed_attribute)

#     return computed_attributes


# @task(
#     name="gather-trigger-computed-attribute-jinja2",
#     cache_policy=NONE,
# )
# async def gather_trigger_computed_attribute_jinja2() -> list[ComputedAttrJinja2TriggerDefinition]:
#     log = get_run_logger()

#     # Build a list of all branches to process based on which branch is different from main
#     branches_with_diff_from_main = registry.get_altered_schema_branches()
#     branches_to_process: list[tuple[str, list[str]]] = [(branch, []) for branch in branches_with_diff_from_main]
#     branches_to_process.append((registry.default_branch, branches_with_diff_from_main))

#     triggers: list[ComputedAttrJinja2TriggerDefinition] = []

#     for branch_scope, branches_out_of_scope in branches_to_process:
#         schema_branch = registry.schema.get_schema_branch(name=branch_scope)
#         mapping = schema_branch.computed_attributes.get_jinja2_target_map()

#         log.info(f"Generating {len(mapping)} Jinja2 trigger for {branch_scope} (except {branches_out_of_scope})")

#         for computed_attribute, source_node_types in mapping.items():
#             trigger = ComputedAttrJinja2TriggerDefinition.from_computed_attribute(
#                 branch=branch_scope,
#                 computed_attribute=computed_attribute,
#                 source_node_types=source_node_types,
#                 branches_out_of_scope=branches_out_of_scope,
#             )
#             triggers.append(trigger)

#     return triggers


# @task(
#     name="gather-trigger-computed-attribute-python",
#     cache_policy=NONE,
# )
# async def gather_trigger_computed_attribute_python(
#     client: InfrahubClient,
# ) -> tuple[list[ComputedAttrPythonTriggerDefinition], list[ComputedAttrPythonQueryTriggerDefinition]]:
#     triggers_python = []
#     triggers_python_query = []

#     repositories = await client.get_list_repositories()

#     all_computed_attributes: dict[str, dict[str, PythonTransformComputedAttribute]] = defaultdict(dict)
#     for branch in registry.branch.values():
#         computed_attributes = await gather_python_transform_attributes(
#             branch_name=branch.name, client=client, repositories=repositories
#         )
#         for computed_attribute in computed_attributes:
#             all_computed_attributes[computed_attribute.name][branch.name] = computed_attribute

#     for branches in all_computed_attributes.values():
#         branches_with_diff_from_main = []
#         if registry.default_branch in branches.keys():
#             commit_main = branches[registry.default_branch].repository_commit
#             branches_with_diff_from_main = [
#                 branch_name for branch_name, item in branches.items() if item.repository_commit != commit_main
#             ]
#         else:
#             branches_with_diff_from_main = list(branches.keys())

#         branches_to_process: list[tuple[str, list[str]]] = [(branch, []) for branch in branches_with_diff_from_main]
#         branches_to_process.append((registry.default_branch, branches_with_diff_from_main))

#         for branch_scope, branches_out_of_scope in branches_to_process:
#             trigger_python = ComputedAttrPythonTriggerDefinition.from_object(
#                 computed_attribute=branches[branch_scope],
#                 branch=branch_scope,
#                 branches_out_of_scope=branches_out_of_scope,
#             )
#             triggers_python.append(trigger_python)

#             trigger_python_query = ComputedAttrPythonQueryTriggerDefinition.from_object(
#                 computed_attribute=branches[branch_scope],
#                 branch=branch_scope,
#                 branches_out_of_scope=branches_out_of_scope,
#             )
#             triggers_python_query.append(trigger_python_query)

#     return triggers_python, triggers_python_query


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
