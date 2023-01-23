import inspect

import graphene

from infrahub.core import registry
from infrahub.graphql.generator import (
    generate_graphql_mutation_create,
    generate_graphql_mutation_update,
    generate_graphql_object,
    generate_interface_object,
    generate_object_types,
    generate_union_object,
)
from infrahub.graphql.types import InfrahubObject


async def test_generate_interface_object(session, default_branch, generic_vehicule_schema):

    result = generate_interface_object(schema=generic_vehicule_schema)
    assert inspect.isclass(result)
    assert issubclass(result, graphene.Interface)
    assert result._meta.name == "Vehicule"
    assert sorted(list(result._meta.fields.keys())) == ["description", "name"]


async def test_generate_union_object(
    session, default_branch, generic_vehicule_schema, car_schema, group_on_road_vehicule_schema
):

    node_type = generate_interface_object(generic_vehicule_schema)
    registry.set_graphql_type(name=node_type._meta.name, graphql_type=node_type, branch=default_branch.name)

    node_type = await generate_graphql_object(schema=car_schema)
    registry.set_graphql_type(name=node_type._meta.name, graphql_type=node_type, branch=default_branch.name)

    result = generate_union_object(schema=group_on_road_vehicule_schema, members=[])
    assert result is None

    result = generate_union_object(schema=group_on_road_vehicule_schema, members=[car_schema.kind])
    assert issubclass(result, graphene.Union)
    assert result._meta.name == "OnRoad"
    assert result._meta.schema == group_on_road_vehicule_schema


async def test_generate_graphql_object(session, default_branch, criticality_schema):

    result = await generate_graphql_object(schema=criticality_schema)
    assert inspect.isclass(result)
    assert issubclass(result, InfrahubObject)
    assert result._meta.name == "Criticality"
    assert sorted(list(result._meta.fields.keys())) == ["_updated_at", "color", "description", "id", "level", "name"]


async def test_generate_graphql_object_with_interface(session, default_branch, generic_vehicule_schema, car_schema):

    node_type = generate_interface_object(generic_vehicule_schema)
    registry.set_graphql_type(name=node_type._meta.name, graphql_type=node_type, branch=default_branch.name)

    result = await generate_graphql_object(schema=car_schema)
    assert inspect.isclass(result)
    assert issubclass(result, InfrahubObject)
    assert result._meta.name == "Car"
    assert sorted(list(result._meta.fields.keys())) == ["_updated_at", "description", "id", "name", "nbr_doors"]


async def test_generate_graphql_mutation_create(session, default_branch, criticality_schema):

    result = await generate_graphql_mutation_create(schema=criticality_schema, session=session)
    assert result._meta.name == "CriticalityCreate"
    assert sorted(list(result._meta.fields.keys())) == ["object", "ok"]


async def test_generate_graphql_mutation_update(session, default_branch, criticality_schema):

    result = await generate_graphql_mutation_update(schema=criticality_schema, session=session)
    assert result._meta.name == "CriticalityUpdate"
    assert sorted(list(result._meta.fields.keys())) == ["object", "ok"]


async def test_generate_object_types(session, default_branch, car_person_schema):

    await generate_object_types(session=session, branch=default_branch)

    car = registry.get_graphql_type(name="Car")
    related_car = registry.get_graphql_type(name="RelatedCar")
    person = registry.get_graphql_type(name="Person")
    related_person = registry.get_graphql_type(name="RelatedPerson")

    assert issubclass(car, InfrahubObject)
    assert issubclass(related_car, InfrahubObject)
    assert issubclass(person, InfrahubObject)
    assert issubclass(related_person, InfrahubObject)

    assert sorted(list(car._meta.fields.keys())) == [
        "_updated_at",
        "color",
        "id",
        "is_electric",
        "name",
        "nbr_seats",
        "owner",
    ]
    assert sorted(list(related_car._meta.fields.keys())) == [
        "_relation__is_protected",
        "_relation__is_visible",
        "_relation__owner",
        "_relation__source",
        "_relation__updated_at",
        "_updated_at",
        "color",
        "id",
        "is_electric",
        "name",
        "nbr_seats",
        "owner",
    ]
    assert sorted(list(person._meta.fields.keys())) == ["_updated_at", "cars", "height", "id", "name"]
    assert sorted(list(related_person._meta.fields.keys())) == [
        "_relation__is_protected",
        "_relation__is_visible",
        "_relation__owner",
        "_relation__source",
        "_relation__updated_at",
        "_updated_at",
        "cars",
        "height",
        "id",
        "name",
    ]
