import inspect

from infrahub.core import registry
from infrahub.graphql.generator import (
    generate_graphql_mutation_create,
    generate_graphql_mutation_update,
    generate_graphql_object,
    generate_object_types,
)
from infrahub.graphql.query import InfrahubObject


def test_generate_graphql_object(default_branch, criticality_schema):

    result = generate_graphql_object(criticality_schema)
    assert inspect.isclass(result)
    assert issubclass(result, InfrahubObject)
    assert result._meta.name == "Criticality"
    assert sorted(list(result._meta.fields.keys())) == ["_updated_at", "color", "description", "id", "level", "name"]


def test_generate_graphql_mutation_create(default_branch, criticality_schema):

    result = generate_graphql_mutation_create(criticality_schema)
    assert result._meta.name == "CriticalityCreate"
    assert sorted(list(result._meta.fields.keys())) == ["object", "ok"]


def test_generate_graphql_mutation_update(default_branch, criticality_schema):

    result = generate_graphql_mutation_update(criticality_schema)
    assert result._meta.name == "CriticalityUpdate"
    assert sorted(list(result._meta.fields.keys())) == ["object", "ok"]


async def test_generate_object_types(session, default_branch, car_person_schema):

    await generate_object_types(session=session, branch=default_branch)

    car = await registry.get_graphql_type(session=session, name="Car")
    related_car = await registry.get_graphql_type(session=session, name="RelatedCar")
    person = await registry.get_graphql_type(session=session, name="Person")
    related_person = await registry.get_graphql_type(session=session, name="RelatedPerson")

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
