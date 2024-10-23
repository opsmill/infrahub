from prefect import flow

from infrahub.core.registry import registry
from infrahub.services import services
from infrahub.support.macro import MacroDefinition

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


@flow(name="process-computed-macro")
async def process_macro(branch_name: str, node_kind: str, object_id: str, updated_fields: list[str]) -> None:
    """Request to the creation of git branches in available repositories."""
    service = services.service
    schema_branch = registry.schema.get_schema_branch(name=branch_name)

    computed_macros = schema_branch.get_impacted_macros(kind=node_kind, updates=updated_fields)
    for computed_macro in computed_macros:
        found = []
        for id_filter in computed_macro.node_filters:
            filters = {id_filter: object_id}
            characters = await service.client.filters(
                kind=computed_macro.kind, prefetch_relationships=True, populate_store=True, **filters
            )
            found.extend(characters)

        if not found:
            print("No nodes found to apply Macro to")

        macro_definition = MacroDefinition(macro=computed_macro.attribute.computation_logic or "n/a")
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
                        my_filter[variable] = "MISSING"

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
