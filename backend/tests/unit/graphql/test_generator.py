import inspect

import graphene

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.graphql.generator import (
    generate_graphql_mutation_create,
    generate_graphql_mutation_update,
    generate_graphql_object,
    generate_interface_object,
    generate_object_types,
    generate_union_object,
    load_attribute_types_in_registry,
    load_node_interface,
)
from infrahub.graphql.types import InfrahubObject


async def test_input_type_registration():
    assert registry.input_type is not {}


async def test_generate_interface_object(session, default_branch: Branch, generic_vehicule_schema):
    load_attribute_types_in_registry(branch=default_branch)
    load_node_interface(branch=default_branch)

    result = generate_interface_object(schema=generic_vehicule_schema, branch=default_branch)
    assert inspect.isclass(result)
    assert issubclass(result, graphene.Interface)
    assert result._meta.name == "Vehicule"
    assert sorted(list(result._meta.fields.keys())) == ["description", "display_label", "id", "name"]


async def test_generate_union_object(
    session,
    default_branch: Branch,
    data_schema,
    group_graphql,
    generic_vehicule_schema,
    car_schema,
    group_on_road_vehicule_schema,
):
    node_type = generate_interface_object(generic_vehicule_schema, branch=default_branch)
    registry.set_graphql_type(name=node_type._meta.name, graphql_type=node_type, branch=default_branch.name)

    node_type = generate_graphql_object(schema=car_schema, branch=default_branch)
    registry.set_graphql_type(name=node_type._meta.name, graphql_type=node_type, branch=default_branch.name)

    result = generate_union_object(schema=group_on_road_vehicule_schema, members=[], branch=default_branch)
    assert result is None

    result = generate_union_object(
        schema=group_on_road_vehicule_schema, members=[car_schema.kind], branch=default_branch
    )
    assert issubclass(result, graphene.Union)
    assert result._meta.name == "OnRoad"
    assert result._meta.schema == group_on_road_vehicule_schema


async def test_generate_graphql_object(session, default_branch: Branch, group_graphql, criticality_schema):
    result = generate_graphql_object(schema=criticality_schema, branch=default_branch)
    assert inspect.isclass(result)
    assert issubclass(result, InfrahubObject)
    assert result._meta.name == "Criticality"
    assert sorted(list(result._meta.fields.keys())) == [
        "_updated_at",
        "color",
        "description",
        "display_label",
        "id",
        "is_false",
        "is_true",
        "label",
        "level",
        "mylist",
        "name",
    ]


async def test_generate_graphql_object_with_interface(
    session, default_branch: Branch, data_schema, group_graphql, generic_vehicule_schema, car_schema
):
    node_type = generate_interface_object(generic_vehicule_schema, branch=default_branch)
    registry.set_graphql_type(name=node_type._meta.name, graphql_type=node_type, branch=default_branch.name)

    result = generate_graphql_object(schema=car_schema, branch=default_branch)
    assert inspect.isclass(result)
    assert issubclass(result, InfrahubObject)
    assert result._meta.name == "Car"
    assert sorted(list(result._meta.fields.keys())) == [
        "_updated_at",
        "description",
        "display_label",
        "id",
        "name",
        "nbr_doors",
    ]


async def test_generate_graphql_mutation_create(session, default_branch: Branch, group_graphql, criticality_schema):
    result = generate_graphql_mutation_create(schema=criticality_schema, branch=default_branch)
    assert result._meta.name == "CriticalityCreate"
    assert sorted(list(result._meta.fields.keys())) == ["object", "ok"]


async def test_generate_graphql_mutation_update(session, default_branch: Branch, group_graphql, criticality_schema):
    result = generate_graphql_mutation_update(schema=criticality_schema, branch=default_branch)
    assert result._meta.name == "CriticalityUpdate"
    assert sorted(list(result._meta.fields.keys())) == ["object", "ok"]


async def test_generate_object_types(session, default_branch: Branch, data_schema, group_graphql, car_person_schema):
    await generate_object_types(session=session, branch=default_branch)

    car = registry.get_graphql_type(name="Car", branch=default_branch)
    edged_car = registry.get_graphql_type(name="EdgedCar", branch=default_branch)
    nested_edged_car = registry.get_graphql_type(name="NestedEdgedCar", branch=default_branch)
    person = registry.get_graphql_type(name="Person", branch=default_branch)
    edged_person = registry.get_graphql_type(name="EdgedPerson", branch=default_branch)
    nested_edged_person = registry.get_graphql_type(name="NestedEdgedPerson", branch=default_branch)
    relationship_property = registry.get_graphql_type(name="RelationshipProperty", branch=default_branch)

    assert issubclass(car, InfrahubObject)
    assert issubclass(edged_car, InfrahubObject)
    assert issubclass(nested_edged_car, InfrahubObject)
    assert issubclass(person, InfrahubObject)
    assert issubclass(edged_person, InfrahubObject)
    assert issubclass(nested_edged_person, InfrahubObject)

    assert sorted(list(car._meta.fields.keys())) == [
        "_updated_at",
        "color",
        "display_label",
        "id",
        "is_electric",
        "name",
        "nbr_seats",
        "owner",
    ]

    assert sorted(list(edged_car._meta.fields.keys())) == ["node"]
    assert str(edged_car._meta.fields["node"].type) == "Car"
    assert sorted(list(nested_edged_car._meta.fields.keys())) == ["node", "properties"]
    assert str(nested_edged_car._meta.fields["node"].type) == "Car"
    assert str(nested_edged_car._meta.fields["properties"].type) == "RelationshipProperty"

    assert sorted(list(person._meta.fields.keys())) == [
        "_updated_at",
        "cars",
        "display_label",
        "height",
        "id",
        "name",
    ]
    assert sorted(list(edged_person._meta.fields.keys())) == ["node"]
    assert str(edged_person._meta.fields["node"].type) == "Person"
    assert sorted(list(nested_edged_person._meta.fields.keys())) == ["node", "properties"]
    assert str(nested_edged_person._meta.fields["node"].type) == "Person"
    assert str(nested_edged_person._meta.fields["properties"].type) == "RelationshipProperty"
    assert sorted(list(relationship_property._meta.fields.keys())) == [
        "is_protected",
        "is_visible",
        "owner",
        "source",
        "updated_at",
    ]
