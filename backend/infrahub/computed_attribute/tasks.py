from datetime import timedelta
from typing import TYPE_CHECKING

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
    UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM,
)
from infrahub.workflows.utils import add_branch_tag, wait_for_schema_to_converge

from .constants import (
    PROCESS_AUTOMATION_NAME,
    PROCESS_AUTOMATION_NAME_PREFIX,
    QUERY_AUTOMATION_NAME,
    QUERY_AUTOMATION_NAME_PREFIX,
)
from .models import ComputedAttributeAutomations, PythonTransformComputedAttribute, PythonTransformTarget

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
    flow_run_name="Process computed attribute on branch {branch_name} for {computed_attribute_kind}.{computed_attribute_name}",
)
async def process_transform(
    branch_name: str,
    node_kind: str,
    object_id: str,
    computed_attribute_name: str,  # pylint: disable=unused-argument
    computed_attribute_kind: str,  # pylint: disable=unused-argument
    updated_fields: list[str] | None = None,  # pylint: disable=unused-argument
) -> None:
    """Request to the creation of git branches in available repositories."""
    await add_branch_tag(branch_name=branch_name)

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
            kind="CoreTransformPython",
            branch=branch_name,
            id=transform_attribute.transform,
            prefetch_relationships=True,
            populate_store=True,
        )
        if not transform:
            continue

        repo_node = await service.client.get(
            kind=transform.repository.peer.typename,
            branch=branch_name,
            id=transform.repository.peer.id,
            raise_when_missing=True,
        )

        repo = await get_initialized_repo(
            repository_id=transform.repository.peer.id,
            name=transform.repository.peer.name.value,
            service=service,
            repository_kind=transform.repository.peer.typename,
        )

        data = await service.client.query_gql_query(
            name=transform.query.peer.name.value,
            variables={"id": object_id},
            update_group=True,
            subscribers=[object_id],
        )

        transformed_data = await repo.execute_python_transform(
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
    name="process_computed_attribute_jinja2",
    flow_run_name="Process computed attribute on branch {branch_name} for {computed_attribute_kind}.{computed_attribute_name}",
)
async def process_jinja2(
    branch_name: str,
    node_kind: str,
    object_id: str,
    computed_attribute_name: str,
    computed_attribute_kind: str,
    updated_fields: list[str] | None = None,
) -> None:
    """Request to the creation of git branches in available repositories."""
    log = get_run_logger()
    service = services.service
    schema_branch = registry.schema.get_schema_branch(name=branch_name)

    computed_macros = [
        attrib
        for attrib in schema_branch.computed_attributes.get_impacted_jinja2_targets(
            kind=node_kind, updates=updated_fields
        )
        if attrib.kind == computed_attribute_kind and attrib.attribute.name == computed_attribute_name
    ]
    for computed_macro in computed_macros:
        found = []
        for id_filter in computed_macro.node_filters:
            filters = {id_filter: object_id}
            nodes = await service.client.filters(
                kind=computed_macro.kind, prefetch_relationships=True, populate_store=True, **filters
            )
            found.extend(nodes)

        if not found:
            log.debug("No nodes found that requires updates")

        template_string = "n/a"
        if computed_macro.attribute.computed_attribute and computed_macro.attribute.computed_attribute.jinja2_template:
            template_string = computed_macro.attribute.computed_attribute.jinja2_template
        macro_definition = MacroDefinition(macro=template_string)
        for node in found:
            my_filter = {}
            for variable in macro_definition.variables:
                components = variable.split("__")
                if len(components) == 2:
                    property_name = components[0]
                    property_value = components[1]
                    attribute_property = getattr(node, property_name)
                    my_filter[variable] = getattr(attribute_property, property_value)
                elif len(components) == 3:
                    relationship_name = components[0]
                    property_name = components[1]
                    property_value = components[2]
                    relationship = getattr(node, relationship_name)
                    try:
                        attribute_property = getattr(relationship.peer, property_name)
                        my_filter[variable] = getattr(attribute_property, property_value)
                    except ValueError:
                        my_filter[variable] = ""

            value = macro_definition.render(variables=my_filter)
            existing_value = getattr(node, computed_macro.attribute.name).value
            if value == existing_value:
                log.debug(f"Ignoring to update {node} with existing value on {computed_macro.attribute.name}={value}")
                continue

            await service.client.execute_graphql(
                query=UPDATE_ATTRIBUTE,
                variables={
                    "id": node.id,
                    "kind": computed_macro.kind,
                    "attribute": computed_macro.attribute.name,
                    "value": value,
                },
                branch_name=branch_name,
            )
            log.info(
                f"Updating computed attribute {computed_attribute_kind}.{computed_attribute_name}='{value}' ({node.id})"
            )


@flow(name="computed-attribute-setup", flow_run_name="Setup computed attributes in task-manager")
async def computed_attribute_setup() -> None:
    service = services.service
    log = get_run_logger()
    await wait_for_schema_to_converge(branch_name=registry.default_branch, service=service, log=log)

    schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)

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
        existing_computed_attr_automations = ComputedAttributeAutomations.from_prefect(automations=automations)

        mapping = schema_branch.computed_attributes.get_jinja2_target_map()
        for computed_attribute, source_node_types in mapping.items():
            log.info(f"processing {computed_attribute.key_name}")
            scope = "default"

            automation = AutomationCore(
                name=PROCESS_AUTOMATION_NAME.format(
                    prefix=PROCESS_AUTOMATION_NAME_PREFIX, identifier=computed_attribute.key_name, scope=scope
                ),
                description=f"Process value of the computed attribute for {computed_attribute.key_name} [{scope}]",
                enabled=True,
                trigger=EventTrigger(
                    posture=Posture.Reactive,
                    expect={"infrahub.node.*"},
                    within=timedelta(0),
                    match=ResourceSpecification({"infrahub.node.kind": source_node_types}),
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
                        },
                        job_variables={},
                    )
                ],
            )

            if existing_computed_attr_automations.has(identifier=computed_attribute.key_name, scope=scope):
                existing = existing_computed_attr_automations.get(identifier=computed_attribute.key_name, scope=scope)
                await client.update_automation(automation_id=existing.id, automation=automation)
                log.info(f"{computed_attribute.key_name} Updated")
            else:
                await client.create_automation(automation=automation)
                log.info(f"{computed_attribute.key_name} Created")


@flow(
    name="computed-attribute-setup-python",
    flow_run_name="Setup computed attributes for Python transforms in task-manager",
)
async def computed_attribute_setup_python() -> None:
    log = get_run_logger()
    service = services.service
    await wait_for_schema_to_converge(branch_name=registry.default_branch, service=service, log=log)

    schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)

    transform_attributes = schema_branch.computed_attributes.python_attributes_by_transform

    transform_names = list(transform_attributes.keys())

    transforms = await service.client.filters(
        kind="CoreTransformPython",
        branch=registry.default_branch,
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

    computed_attributes: list[PythonTransformComputedAttribute] = []
    for transform in transforms:
        for attribute in transform_attributes[transform.name.value]:
            computed_attributes.append(
                PythonTransformComputedAttribute(
                    name=transform.name.value,
                    repository_id=transform.repository.peer.id,
                    repository_name=transform.repository.peer.name.value,
                    repository_kind=transform.repository.peer.typename,
                    query_name=transform.query.peer.name.value,
                    query_models=transform.query.peer.models.value,
                    computed_attribute=attribute,
                )
            )

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
            automations=automations, prefix=PROCESS_AUTOMATION_NAME_PREFIX
        )
        existing_computed_attr_query_automations = ComputedAttributeAutomations.from_prefect(
            automations=automations, prefix=QUERY_AUTOMATION_NAME_PREFIX
        )

        for computed_attribute in computed_attributes:
            log.info(f"processing {computed_attribute.computed_attribute.key_name}")
            scope = "default"

            automation = AutomationCore(
                name=PROCESS_AUTOMATION_NAME.format(
                    prefix=PROCESS_AUTOMATION_NAME_PREFIX,
                    identifier=computed_attribute.computed_attribute.key_name,
                    scope=scope,
                ),
                description=f"Process value of the computed attribute for {computed_attribute.computed_attribute.key_name} [{scope}]",
                enabled=True,
                trigger=EventTrigger(
                    posture=Posture.Reactive,
                    expect={"infrahub.node.*"},
                    within=timedelta(0),
                    match=ResourceSpecification({"infrahub.node.kind": [computed_attribute.computed_attribute.kind]}),
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
            else:
                await client.create_automation(automation=automation)
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
                    match=ResourceSpecification({"infrahub.node.kind": computed_attribute.query_models}),
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
                log.info(f"Query {computed_attribute.computed_attribute.key_name} Updated")
            else:
                await client.create_automation(automation=automation)
                log.info(f"Query {computed_attribute.computed_attribute.key_name} Created")


@flow(
    name="query-computed-attribute-transform-targets",
    flow_run_name="Query for potential targets of computed attributes in branch {branch_name} for {node_kind}",
)
async def query_transform_targets(
    branch_name: str,
    node_kind: str,  # pylint: disable=unused-argument
    object_id: str,
) -> None:
    await add_branch_tag(branch_name=branch_name)
    service = services.service
    schema_branch = registry.schema.get_schema_branch(name=branch_name)
    targets = await service.client.execute_graphql(
        query=GATHER_GRAPHQL_QUERY_SUBSCRIBERS, variables={"members": [object_id]}
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
