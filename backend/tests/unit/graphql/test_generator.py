import inspect

import graphene

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.generator import (
    generate_filters,
    generate_graphql_mutation_create,
    generate_graphql_mutation_create_input,
    generate_graphql_mutation_update,
    generate_graphql_mutation_update_input,
    generate_graphql_object,
    generate_interface_object,
    generate_object_types,
    load_attribute_types_in_registry,
    load_node_interface,
)
from infrahub.graphql.types import InfrahubObject


async def test_input_type_registration():
    assert registry.input_type is not {}  # noqa


async def test_generate_interface_object(db: InfrahubDatabase, default_branch: Branch, generic_vehicule_schema):
    load_attribute_types_in_registry(branch=default_branch)
    load_node_interface(branch=default_branch)

    result = generate_interface_object(schema=generic_vehicule_schema, branch=default_branch)
    assert inspect.isclass(result)
    assert issubclass(result, graphene.Interface)
    assert result._meta.name == "TestVehicule"
    assert sorted(list(result._meta.fields.keys())) == ["description", "display_label", "id", "name"]


async def test_generate_graphql_object(db: InfrahubDatabase, default_branch: Branch, group_graphql, criticality_schema):
    result = generate_graphql_object(schema=criticality_schema, branch=default_branch)
    assert inspect.isclass(result)
    assert issubclass(result, InfrahubObject)
    assert result._meta.name == "TestCriticality"
    assert sorted(list(result._meta.fields.keys())) == [
        "_updated_at",
        "color",
        "description",
        "display_label",
        "id",
        "is_false",
        "is_true",
        "json_default",
        "json_no_default",
        "label",
        "level",
        "mylist",
        "name",
        "status",
    ]


async def test_generate_graphql_object_with_interface(
    db: InfrahubDatabase, default_branch: Branch, data_schema, group_graphql, generic_vehicule_schema, car_schema
):
    node_type = generate_interface_object(generic_vehicule_schema, branch=default_branch)
    registry.set_graphql_type(name=node_type._meta.name, graphql_type=node_type, branch=default_branch.name)

    result = generate_graphql_object(schema=car_schema, branch=default_branch)
    assert inspect.isclass(result)
    assert issubclass(result, InfrahubObject)
    assert result._meta.name == "TestCar"
    assert sorted(list(result._meta.fields.keys())) == [
        "_updated_at",
        "description",
        "display_label",
        "id",
        "name",
        "nbr_doors",
    ]


async def test_generate_graphql_mutation_create(
    db: InfrahubDatabase, default_branch: Branch, group_graphql, criticality_schema
):
    input_type = generate_graphql_mutation_create_input(criticality_schema)
    result = generate_graphql_mutation_create(schema=criticality_schema, branch=default_branch, input_type=input_type)
    assert result._meta.name == "TestCriticalityCreate"
    assert sorted(list(result._meta.fields.keys())) == ["object", "ok"]


async def test_generate_graphql_mutation_update(
    db: InfrahubDatabase, default_branch: Branch, group_graphql, criticality_schema
):
    input_type = generate_graphql_mutation_update_input(schema=criticality_schema)
    result = generate_graphql_mutation_update(schema=criticality_schema, branch=default_branch, input_type=input_type)
    assert result._meta.name == "TestCriticalityUpdate"
    assert sorted(list(result._meta.fields.keys())) == ["object", "ok"]


async def test_generate_object_types(
    db: InfrahubDatabase, default_branch: Branch, data_schema, group_graphql, car_person_schema
):
    await generate_object_types(db=db, branch=default_branch)

    car = registry.get_graphql_type(name="TestCar", branch=default_branch)
    edged_car = registry.get_graphql_type(name="EdgedTestCar", branch=default_branch)
    nested_edged_car = registry.get_graphql_type(name="NestedEdgedTestCar", branch=default_branch)
    person = registry.get_graphql_type(name="TestPerson", branch=default_branch)
    edged_person = registry.get_graphql_type(name="EdgedTestPerson", branch=default_branch)
    nested_edged_person = registry.get_graphql_type(name="NestedEdgedTestPerson", branch=default_branch)
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
        "member_of_groups",
        "name",
        "nbr_seats",
        "owner",
        "subscriber_of_groups",
        "transmission",
    ]

    assert sorted(list(edged_car._meta.fields.keys())) == ["node"]
    assert str(edged_car._meta.fields["node"].type) == "TestCar"
    assert sorted(list(nested_edged_car._meta.fields.keys())) == ["node", "properties"]
    assert str(nested_edged_car._meta.fields["node"].type) == "TestCar"
    assert str(nested_edged_car._meta.fields["properties"].type) == "RelationshipProperty"

    assert sorted(list(person._meta.fields.keys())) == [
        "_updated_at",
        "cars",
        "display_label",
        "height",
        "id",
        "member_of_groups",
        "name",
        "subscriber_of_groups",
    ]
    assert sorted(list(edged_person._meta.fields.keys())) == ["node"]
    assert str(edged_person._meta.fields["node"].type) == "TestPerson"
    assert sorted(list(nested_edged_person._meta.fields.keys())) == ["node", "properties"]
    assert str(nested_edged_person._meta.fields["node"].type) == "TestPerson"
    assert str(nested_edged_person._meta.fields["properties"].type) == "RelationshipProperty"
    assert sorted(list(relationship_property._meta.fields.keys())) == [
        "is_protected",
        "is_visible",
        "owner",
        "source",
        "updated_at",
    ]


async def test_generate_filters(
    db: InfrahubDatabase, default_branch: Branch, data_schema, group_graphql, car_person_schema_generics
):
    person = registry.get_schema(name="TestPerson")
    filters = await generate_filters(db=db, schema=person, top_level=True)
    expected_filters = [
        "offset",
        "limit",
        "ids",
        "any__is_protected",
        "any__is_visible",
        "any__owner__id",
        "any__source__id",
        "any__value",
        "any__values",
        "cars__color__is_protected",
        "cars__color__is_visible",
        "cars__color__owner__id",
        "cars__color__source__id",
        "cars__color__value",
        "cars__color__values",
        "cars__ids",
        "cars__name__is_protected",
        "cars__name__is_visible",
        "cars__name__owner__id",
        "cars__name__source__id",
        "cars__name__value",
        "cars__name__values",
        "cars__nbr_seats__is_protected",
        "cars__nbr_seats__is_visible",
        "cars__nbr_seats__owner__id",
        "cars__nbr_seats__source__id",
        "cars__nbr_seats__value",
        "cars__nbr_seats__values",
        "height__is_protected",
        "height__is_visible",
        "height__owner__id",
        "height__source__id",
        "height__value",
        "height__values",
        "member_of_groups__description__value",
        "member_of_groups__description__values",
        "member_of_groups__ids",
        "member_of_groups__label__value",
        "member_of_groups__label__values",
        "member_of_groups__name__value",
        "member_of_groups__name__values",
        "name__is_protected",
        "name__is_visible",
        "name__owner__id",
        "name__source__id",
        "name__value",
        "name__values",
        "subscriber_of_groups__description__value",
        "subscriber_of_groups__description__values",
        "subscriber_of_groups__ids",
        "subscriber_of_groups__label__value",
        "subscriber_of_groups__label__values",
        "subscriber_of_groups__name__value",
        "subscriber_of_groups__name__values",
    ]
    assert sorted(list(filters.keys())) == sorted(expected_filters)
