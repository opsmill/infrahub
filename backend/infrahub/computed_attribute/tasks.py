from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import ujson
from infrahub_sdk.protocols import (
    CoreNode,  # noqa: TC002
    CoreTransformPython,
)
from prefect import flow
from prefect.automations import AutomationCore
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterName
from prefect.events.actions import (
    RunDeployment,
)
from prefect.events.schemas.automations import EventTrigger, Posture
from prefect.events.schemas.events import ResourceSpecification
from prefect.logging import get_run_logger

from infrahub.core.constants import ComputedAttributeKind, InfrahubKind
from infrahub.core.registry import registry
from infrahub.git.repository import get_initialized_repo
from infrahub.services import services
from infrahub.support.macro import MacroDefinition
from infrahub.workflows.catalogue import (
    PROCESS_COMPUTED_MACRO,
    QUERY_COMPUTED_ATTRIBUTE_TRANSFORM_TARGETS,
    TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
    UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM,
)
from infrahub.workflows.utils import add_tags, wait_for_schema_to_converge

from .constants import (
    PROCESS_AUTOMATION_NAME,
    PROCESS_JINJA2_AUTOMATION_NAME_PREFIX,
    PROCESS_PYTHON_AUTOMATION_NAME_PREFIX,
    QUERY_AUTOMATION_NAME,
    QUERY_AUTOMATION_NAME_PREFIX,
)
from .models import ComputedAttributeAutomations, PythonTransformComputedAttribute, PythonTransformTarget

if TYPE_CHECKING:
    import logging

    from infrahub.core.schema.computed_attribute import ComputedAttribute
    from infrahub.services import InfrahubServices

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
    computed_attribute_name: str,  # pylint: disable=unused-argument
    computed_attribute_kind: str,  # pylint: disable=unused-argument
    updated_fields: list[str] | None = None,  # pylint: disable=unused-argument
) -> None:
    await add_tags(branches=[branch_name], nodes=[object_id])

    service = services.service
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
        )

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
        )

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
) -> None:
    service = services.service
    await add_tags(branches=[branch_name])

    nodes = await service.client.all(kind=computed_attribute_kind, branch=branch_name)

    for node in nodes:
        await service.workflow.submit_workflow(
            workflow=UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM,
            parameters={
                "branch_name": branch_name,
                "node_kind": computed_attribute_kind,
                "object_id": node.id,
                "computed_attribute_name": computed_attribute_name,
                "computed_attribute_kind": computed_attribute_kind,
            },
        )


@flow(
    name="process_computed_attribute_value_jinja2",
    flow_run_name="Update value for computed attribute {attribute_name}",
)
async def update_computed_attribute_value_jinja2(
    branch_name: str, obj: CoreNode, attribute_name: str, template_value: str
) -> None:
    log = get_run_logger()
    service = services.service

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
    name="process_computed_attribute_jinja2",
    flow_run_name="Process computed attribute for {computed_attribute_kind}.{computed_attribute_name}",
)
async def process_jinja2(
    branch_name: str,
    node_kind: str,
    object_id: str,
    computed_attribute_name: str,
    computed_attribute_kind: str,
    updated_fields: str | None = None,
) -> None:
    log = get_run_logger()
    service = services.service

    await add_tags(branches=[branch_name])
    updates: list[str] = []
    if isinstance(updated_fields, str):
        updates = ujson.loads(updated_fields)

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
) -> None:
    service = services.service
    await add_tags(branches=[branch_name])

    nodes = await service.client.all(kind=computed_attribute_kind, branch=branch_name)

    for node in nodes:
        await service.workflow.submit_workflow(
            workflow=PROCESS_COMPUTED_MACRO,
            parameters={
                "branch_name": branch_name,
                "computed_attribute_name": computed_attribute_name,
                "computed_attribute_kind": computed_attribute_kind,
                "node_kind": computed_attribute_kind,
                "object_id": node.id,
            },
        )


@flow(name="computed-attribute-setup", flow_run_name="Setup computed attributes in task-manager")
async def computed_attribute_setup(branch_name: str | None = None) -> None:  # pylint: disable=too-many-statements
    service = services.service
    branch_name = branch_name or registry.default_branch

    await add_tags(branches=[branch_name])

    log = get_run_logger()
    await wait_for_schema_to_converge(branch_name=branch_name, service=service, log=log)

    branches_with_diff_from_main = registry.get_altered_schema_branches()
    schema_branch = registry.schema.get_schema_branch(name=branch_name)

    async with get_client(sync_client=False) as client:
        deployments = {
            item.name: item
            for item in await client.read_deployments(
                deployment_filter=DeploymentFilter(name=DeploymentFilterName(any_=[PROCESS_COMPUTED_MACRO.name]))
            )
        }
        if PROCESS_COMPUTED_MACRO.name not in deployments:
            raise ValueError("Unable to find the deployment for PROCESS_COMPUTED_MACRO")

        deployment_id_jinja = deployments[PROCESS_COMPUTED_MACRO.name].id

        automations = await client.read_automations()
        existing_computed_attr_automations = ComputedAttributeAutomations.from_prefect(
            automations=automations, prefix=PROCESS_JINJA2_AUTOMATION_NAME_PREFIX
        )
        automations_to_keep = []
        mapping = schema_branch.computed_attributes.get_jinja2_target_map()
        for computed_attribute, source_node_types in mapping.items():
            log.info(f"processing {computed_attribute.key_name}")
            scope = registry.default_branch

            match_criteria: dict[str, Any] = {"infrahub.node.kind": source_node_types}
            if branches_with_diff_from_main:
                match_criteria["infrahub.branch.name"] = [f"!{branch}" for branch in branches_with_diff_from_main]

            automation = AutomationCore(
                name=PROCESS_AUTOMATION_NAME.format(
                    prefix=PROCESS_JINJA2_AUTOMATION_NAME_PREFIX, identifier=computed_attribute.key_name, scope=scope
                ),
                description=f"Process value of the computed attribute for {computed_attribute.key_name} [{scope}] and branches with the same schema",
                enabled=True,
                trigger=EventTrigger(
                    posture=Posture.Reactive,
                    expect={"infrahub.node.*"},
                    within=timedelta(0),
                    match=ResourceSpecification(match_criteria),
                    threshold=1,
                ),
                actions=[
                    RunDeployment(
                        source="selected",
                        deployment_id=deployment_id_jinja,
                        parameters={
                            "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                            "node_kind": "{{ event.resource['infrahub.node.kind'] }}",
                            "object_id": "{{ event.resource['infrahub.node.id'] }}",
                            "computed_attribute_name": computed_attribute.attribute.name,
                            "computed_attribute_kind": computed_attribute.kind,
                            "updated_fields": "{{ event.payload['fields'] | tojson }}",
                        },
                        job_variables={},
                    )
                ],
            )

            if existing_computed_attr_automations.has(identifier=computed_attribute.key_name, scope=scope):
                existing = existing_computed_attr_automations.get(identifier=computed_attribute.key_name, scope=scope)
                await client.update_automation(automation_id=existing.id, automation=automation)
                automations_to_keep.append(existing.id)
                log.info(f"{computed_attribute.key_name} Updated")
            else:
                automation_id = await client.create_automation(automation=automation)
                automations_to_keep.append(automation_id)
                log.info(f"{computed_attribute.key_name} Created")

            if branch_name == registry.default_branch:
                await service.workflow.submit_workflow(
                    workflow=TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
                    parameters={
                        "branch_name": registry.default_branch,
                        "computed_attribute_name": computed_attribute.attribute.name,
                        "computed_attribute_kind": computed_attribute.kind,
                    },
                )

        for diff_branch in branches_with_diff_from_main:
            schema_branch = registry.schema.get_schema_branch(name=diff_branch)

            mapping = schema_branch.computed_attributes.get_jinja2_target_map()
            for computed_attribute, source_node_types in mapping.items():
                log.info(f"processing {computed_attribute.key_name}")

                automation = AutomationCore(
                    name=PROCESS_AUTOMATION_NAME.format(
                        prefix=PROCESS_PYTHON_AUTOMATION_NAME_PREFIX,
                        identifier=computed_attribute.key_name,
                        scope=diff_branch,
                    ),
                    description=f"Process value of the computed attribute for {computed_attribute.key_name} [{diff_branch}]",
                    enabled=True,
                    trigger=EventTrigger(
                        posture=Posture.Reactive,
                        expect={"infrahub.node.*"},
                        within=timedelta(0),
                        match=ResourceSpecification(
                            {
                                "infrahub.node.kind": source_node_types,
                                "infrahub.branch.name": diff_branch,
                            }
                        ),
                        threshold=1,
                    ),
                    actions=[
                        RunDeployment(
                            source="selected",
                            deployment_id=deployment_id_jinja,
                            parameters={
                                "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                                "node_kind": "{{ event.resource['infrahub.node.kind'] }}",
                                "object_id": "{{ event.resource['infrahub.node.id'] }}",
                                "computed_attribute_name": computed_attribute.attribute.name,
                                "computed_attribute_kind": computed_attribute.kind,
                                "updated_fields": "{{ event.payload['fields'] | tojson }}",
                            },
                            job_variables={},
                        )
                    ],
                )

                if existing_computed_attr_automations.has(identifier=computed_attribute.key_name, scope=diff_branch):
                    existing = existing_computed_attr_automations.get(
                        identifier=computed_attribute.key_name, scope=diff_branch
                    )
                    await client.update_automation(automation_id=existing.id, automation=automation)
                    automations_to_keep.append(existing.id)
                    log.info(f"{computed_attribute.key_name} Updated")
                else:
                    automation_id = await client.create_automation(automation=automation)
                    automations_to_keep.append(automation_id)
                    log.info(f"{computed_attribute.key_name} Created")

                if branch_name == diff_branch:
                    await service.workflow.submit_workflow(
                        workflow=TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
                        parameters={
                            "branch_name": branch_name,
                            "computed_attribute_name": computed_attribute.attribute.name,
                            "computed_attribute_kind": computed_attribute.kind,
                        },
                    )

        automations_to_remove = existing_computed_attr_automations.return_obsolete(keep=automations_to_keep)
        for automation_to_remove in automations_to_remove:
            await client.delete_automation(automation_id=automation_to_remove)


@flow(
    name="computed-attribute-setup-python",
    flow_run_name="Setup computed attributes for Python transforms in task-manager",
)
async def computed_attribute_setup_python(
    branch_name: str | None = None,
    commit: str | None = None,  # pylint: disable=unused-argument
    trigger_updates: bool = True,
) -> None:
    log = get_run_logger()
    service = services.service

    branch_name = branch_name or registry.default_branch

    await add_tags(branches=[branch_name])

    await wait_for_schema_to_converge(branch_name=branch_name, service=service, log=log)

    computed_attributes = await _gather_python_transform_attributes(branch_name=branch_name, service=service, log=log)

    async with get_client(sync_client=False) as client:
        deployments = {
            item.name: item
            for item in await client.read_deployments(
                deployment_filter=DeploymentFilter(
                    name=DeploymentFilterName(
                        any_=[UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM.name, QUERY_COMPUTED_ATTRIBUTE_TRANSFORM_TARGETS.name]
                    )
                )
            )
        }
        if UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM.name not in deployments:
            raise ValueError("Unable to find the deployment for UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM")
        if QUERY_COMPUTED_ATTRIBUTE_TRANSFORM_TARGETS.name not in deployments:
            raise ValueError("Unable to find the deployment for QUERY_COMPUTED_ATTRIBUTE_TRANSFORM_TARGETS")

        deployment_id_python = deployments[UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM.name].id
        deployment_id_query = deployments[QUERY_COMPUTED_ATTRIBUTE_TRANSFORM_TARGETS.name].id

        automations = await client.read_automations()
        existing_computed_attr_process_automations = ComputedAttributeAutomations.from_prefect(
            automations=automations, prefix=f"{PROCESS_PYTHON_AUTOMATION_NAME_PREFIX}::{branch_name}::"
        )
        existing_computed_attr_query_automations = ComputedAttributeAutomations.from_prefect(
            automations=automations, prefix=f"{QUERY_AUTOMATION_NAME_PREFIX}::{branch_name}::"
        )

        automations_to_keep = []
        for computed_attribute in computed_attributes:
            log.info(f"processing {computed_attribute.computed_attribute.key_name}")
            scope = branch_name

            automation = AutomationCore(
                name=PROCESS_AUTOMATION_NAME.format(
                    prefix=PROCESS_PYTHON_AUTOMATION_NAME_PREFIX,
                    identifier=computed_attribute.computed_attribute.key_name,
                    scope=scope,
                ),
                description=f"Process value of the computed attribute for {computed_attribute.computed_attribute.key_name} [{scope}]",
                enabled=True,
                trigger=EventTrigger(
                    posture=Posture.Reactive,
                    expect={"infrahub.node.*"},
                    within=timedelta(0),
                    match=ResourceSpecification(
                        {
                            "infrahub.node.kind": [computed_attribute.computed_attribute.kind],
                            "infrahub.branch.name": branch_name,
                        }
                    ),
                    threshold=1,
                ),
                actions=[
                    RunDeployment(
                        source="selected",
                        deployment_id=deployment_id_python,
                        parameters={
                            "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                            "node_kind": "{{ event.resource['infrahub.node.kind'] }}",
                            "object_id": "{{ event.resource['infrahub.node.id'] }}",
                            "computed_attribute_name": computed_attribute.computed_attribute.attribute.name,
                            "computed_attribute_kind": computed_attribute.computed_attribute.kind,
                        },
                        job_variables={},
                    )
                ],
            )

            if existing_computed_attr_process_automations.has(
                identifier=computed_attribute.computed_attribute.key_name, scope=scope
            ):
                existing = existing_computed_attr_process_automations.get(
                    identifier=computed_attribute.computed_attribute.key_name, scope=scope
                )
                await client.update_automation(automation_id=existing.id, automation=automation)
                log.info(f"Process {computed_attribute.computed_attribute.key_name} Updated")
                automations_to_keep.append(existing.id)
            else:
                automation_id = await client.create_automation(automation=automation)
                automations_to_keep.append(automation_id)
                log.info(f"Process {computed_attribute.computed_attribute.key_name} Created")

            automation = AutomationCore(
                name=QUERY_AUTOMATION_NAME.format(
                    prefix=QUERY_AUTOMATION_NAME_PREFIX,
                    identifier=computed_attribute.computed_attribute.key_name,
                    scope=scope,
                ),
                description=f"Query the computed attribute targets for {computed_attribute.computed_attribute.key_name} [{scope}]",
                enabled=True,
                trigger=EventTrigger(
                    posture=Posture.Reactive,
                    expect={"infrahub.node.*"},
                    within=timedelta(0),
                    match=ResourceSpecification(
                        {
                            "infrahub.node.kind": computed_attribute.query_models,
                            "infrahub.branch.name": branch_name,
                        }
                    ),
                    threshold=1,
                ),
                actions=[
                    RunDeployment(
                        source="selected",
                        deployment_id=deployment_id_query,
                        parameters={
                            "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                            "node_kind": "{{ event.resource['infrahub.node.kind'] }}",
                            "object_id": "{{ event.resource['infrahub.node.id'] }}",
                        },
                        job_variables={},
                    )
                ],
            )

            if existing_computed_attr_query_automations.has(
                identifier=computed_attribute.computed_attribute.key_name, scope=scope
            ):
                existing = existing_computed_attr_query_automations.get(
                    identifier=computed_attribute.computed_attribute.key_name, scope=scope
                )
                await client.update_automation(automation_id=existing.id, automation=automation)
                automations_to_keep.append(existing.id)
                log.info(f"Query {computed_attribute.computed_attribute.key_name} Updated")
            else:
                automation_id = await client.create_automation(automation=automation)
                automations_to_keep.append(automation_id)
                log.info(f"Query {computed_attribute.computed_attribute.key_name} Created")

            if trigger_updates:
                await service.workflow.submit_workflow(
                    workflow=TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
                    parameters={
                        "branch_name": branch_name,
                        "computed_attribute_name": computed_attribute.computed_attribute.attribute.name,
                        "computed_attribute_kind": computed_attribute.computed_attribute.kind,
                    },
                )

        automations_to_remove = existing_computed_attr_process_automations.return_obsolete(keep=automations_to_keep)
        for automation_to_remove in automations_to_remove:
            await client.delete_automation(automation_id=automation_to_remove)

        automations_to_remove = existing_computed_attr_query_automations.return_obsolete(keep=automations_to_keep)
        for automation_to_remove in automations_to_remove:
            await client.delete_automation(automation_id=automation_to_remove)


@flow(
    name="computed-attribute-remove-python",
    flow_run_name="Remove Python based computed attributes on branch={branch_name}",
)
async def computed_attribute_remove_python(
    branch_name: str,
) -> None:
    async with get_client(sync_client=False) as client:
        automations = await client.read_automations()
        existing_computed_attr_process_automations = ComputedAttributeAutomations.from_prefect(
            automations=automations, prefix=f"{PROCESS_PYTHON_AUTOMATION_NAME_PREFIX}::{branch_name}::"
        )
        existing_computed_attr_query_automations = ComputedAttributeAutomations.from_prefect(
            automations=automations, prefix=f"{QUERY_AUTOMATION_NAME_PREFIX}::{branch_name}::"
        )

        for automation_id in existing_computed_attr_process_automations.all_automation_ids:
            await client.delete_automation(automation_id=automation_id)

        for automation_id in existing_computed_attr_query_automations.all_automation_ids:
            await client.delete_automation(automation_id=automation_id)


@flow(
    name="query-computed-attribute-transform-targets",
    flow_run_name="Query for potential targets of computed attributes for {node_kind}",
)
async def query_transform_targets(
    branch_name: str,
    node_kind: str,  # pylint: disable=unused-argument
    object_id: str,
) -> None:
    await add_tags(branches=[branch_name])
    service = services.service
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
                    parameters={
                        "branch_name": branch_name,
                        "node_kind": subscriber.kind,
                        "object_id": subscriber.object_id,
                        "computed_attribute_name": computed_attribute.name,
                        "computed_attribute_kind": subscriber.kind,
                    },
                )


async def _gather_python_transform_attributes(
    branch_name: str, service: InfrahubServices, log: logging.Logger | logging.LoggerAdapter
) -> list[PythonTransformComputedAttribute]:
    schema_branch = registry.schema.get_schema_branch(name=branch_name)
    branches_with_diff_from_main = registry.get_altered_schema_branches()

    transform_attributes = schema_branch.computed_attributes.python_attributes_by_transform

    transform_names = list(transform_attributes.keys())
    if not transform_names:
        return []

    transforms = await service.client.filters(
        kind="CoreTransformPython",
        branch=branch_name,
        prefetch_relationships=True,
        populate_store=True,
        name__values=transform_names,
    )

    found_transforms_names = [transform.name.value for transform in transforms]
    for transform_name in transform_names:
        if transform_name not in found_transforms_names:
            log.warning(
                msg=f"The transform {transform_name} is assigned to a computed attribute but the transform could not be found in the database."
            )

    repositories = await service.client.get_list_repositories()
    computed_attributes: list[PythonTransformComputedAttribute] = []
    for transform in transforms:
        for attribute in transform_attributes[transform.name.value]:
            python_transform_computed_attribute = PythonTransformComputedAttribute(
                name=transform.name.value,
                repository_id=transform.repository.peer.id,
                repository_name=transform.repository.peer.name.value,
                repository_kind=transform.repository.peer.typename,
                query_name=transform.query.peer.name.value,
                query_models=transform.query.peer.models.value,
                computed_attribute=attribute,
                default_schema=branch_name not in branches_with_diff_from_main,
            )
            python_transform_computed_attribute.populate_branch_commit(
                repository_data=repositories.get(transform.repository.peer.name.value)
            )
            computed_attributes.append(python_transform_computed_attribute)

    return computed_attributes


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
