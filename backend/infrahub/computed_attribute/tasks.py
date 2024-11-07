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

from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.registry import registry
from infrahub.git.repository import get_initialized_repo
from infrahub.services import services
from infrahub.support.macro import MacroDefinition
from infrahub.workflows.catalogue import PROCESS_COMPUTED_MACRO
from infrahub.workflows.utils import add_branch_tag

if TYPE_CHECKING:
    from infrahub.core.schema.computed_attribute import ComputedAttribute
    from infrahub.core.schema.schema_branch import ComputedAttributeTarget

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


@flow(name="process_computed_attribute_transform", flow_run_name="Process computed attribute on branch {branch_name}")
async def process_transform(
    branch_name: str,
    node_kind: str,
    object_id: str,
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


@flow(name="process_computed_attribute_jinja2", log_prints=True)
async def process_jinja2(
    branch_name: str, node_kind: str, object_id: str, updated_fields: list[str] | None = None
) -> None:
    """Request to the creation of git branches in available repositories."""
    service = services.service
    schema_branch = registry.schema.get_schema_branch(name=branch_name)

    computed_macros = schema_branch.get_impacted_macros(kind=node_kind, updates=updated_fields)
    for computed_macro in computed_macros:
        found = []
        for id_filter in computed_macro.node_filters:
            filters = {id_filter: object_id}
            nodes = await service.client.filters(
                kind=computed_macro.kind, prefetch_relationships=True, populate_store=True, **filters
            )
            found.extend(nodes)

        if not found:
            print("No nodes found to apply Macro to")

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

            await service.client.execute_graphql(
                query=UPDATE_ATTRIBUTE,
                variables={
                    "id": node.id,
                    "kind": computed_macro.kind,
                    "attribute": computed_macro.attribute.name,
                    "value": macro_definition.render(variables=my_filter),
                },
                branch_name=branch_name,
            )
            print("#" * 40)
            print(f"node: {node.id}")
            print(f"attribute: {computed_macro.attribute.name}")
            print(f"value: {macro_definition.render(variables=my_filter)}")
            print()


@flow(name="computed-attribute-setup")
async def computed_attribute_setup() -> None:
    # service = services.service
    schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)
    log = get_run_logger()
    async with get_client(sync_client=False) as client:
        deployments = {
            item.name: item
            for item in await client.read_deployments(
                deployment_filter=DeploymentFilter(name=DeploymentFilterName(any_=[PROCESS_COMPUTED_MACRO.name]))
            )
        }
        if PROCESS_COMPUTED_MACRO.name not in deployments:
            raise ValueError("Unable to find the deployment for PROCESS_COMPUTED_MACRO")
        deployment_id = deployments[PROCESS_COMPUTED_MACRO.name].id

        # TODO need to pull the existing automation to see if we need to create or update each object
        # automations = await client.read_automations()

        computed_attributes: dict[str, ComputedAttributeTarget] = {}
        for item in schema_branch._computed_jinja2_attribute_map.values():
            for attrs in list(item.local_fields.values()) + list(item.relationships.values()):
                for attr in attrs:
                    if attr.key_name in computed_attributes:
                        continue
                    log.info(f"found {attr.key_name}")
                    computed_attributes[attr.key_name] = attr

        for identifier, computed_attribute in computed_attributes.items():
            log.info(f"processing {computed_attribute.key_name}")
            automation = AutomationCore(
                name=f"computed-attribute-process-{identifier}",
                description=f"Process value of the computed attribute for {identifier}",
                enabled=True,
                trigger=EventTrigger(
                    posture=Posture.Reactive,
                    expect={"infrahub.node.*"},
                    within=timedelta(0),
                    match=ResourceSpecification({"infrahub.node.kind": [computed_attribute.kind]}),
                    threshold=1,
                ),
                actions=[
                    RunDeployment(
                        source="selected",
                        deployment_id=deployment_id,
                        parameters={
                            "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                            "node_kind": "{{ event.resource['infrahub.node.kind'] }}",
                            "object_id": "{{ event.resource['infrahub.node.id'] }}",
                        },
                        job_variables={},
                    )
                ],
            )

            response = await client.create_automation(automation=automation)
            log.info(f"Processed: {computed_attribute.key_name} : {response}")
