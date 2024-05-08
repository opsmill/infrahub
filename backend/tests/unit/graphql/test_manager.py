import inspect

import graphene

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.manager import GraphQLSchemaManager
from infrahub.graphql.types import InfrahubObject


async def test_input_type_registration():
    assert registry.input_type is not {}  # noqa


async def test_generate_interface_object(db: InfrahubDatabase, default_branch: Branch, generic_vehicule_schema):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)

    result = gqlm.generate_interface_object(schema=generic_vehicule_schema)
    assert inspect.isclass(result)
    assert issubclass(result, graphene.Interface)
    assert result._meta.name == "TestVehicule"
    assert sorted(list(result._meta.fields.keys())) == ["description", "display_label", "id", "name"]


async def test_generate_graphql_object(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)

    result = gqlm.generate_graphql_object(schema=criticality_schema)
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
    db: InfrahubDatabase, default_branch: Branch, data_schema, generic_vehicule_schema, car_schema
):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)
    gqlm.generate_interface_object(schema=generic_vehicule_schema, populate_cache=True)

    result = gqlm.generate_graphql_object(schema=car_schema)
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


async def test_generate_graphql_mutation_create(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)

    input_type = gqlm.generate_graphql_mutation_create_input(schema=criticality_schema)
    result = gqlm.generate_graphql_mutation_create(schema=criticality_schema, input_type=input_type)
    assert result._meta.name == "TestCriticalityCreate"
    assert sorted(list(result._meta.fields.keys())) == ["object", "ok"]


async def test_generate_graphql_mutation_update(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)

    input_type = gqlm.generate_graphql_mutation_update_input(schema=criticality_schema)
    result = gqlm.generate_graphql_mutation_update(schema=criticality_schema, input_type=input_type)
    assert result._meta.name == "TestCriticalityUpdate"
    assert sorted(list(result._meta.fields.keys())) == ["object", "ok"]


async def test_generate_object_types(db: InfrahubDatabase, default_branch: Branch, data_schema, car_person_schema):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)

    gqlm.generate_object_types()

    car = gqlm.get_type(name="TestCar")
    edged_car = gqlm.get_type(name="EdgedTestCar")
    nested_edged_car = gqlm.get_type(name="NestedEdgedTestCar")
    person = gqlm.get_type(name="TestPerson")
    edged_person = gqlm.get_type(name="EdgedTestPerson")
    nested_edged_person = gqlm.get_type(name="NestedEdgedTestPerson")
    relationship_property = gqlm.get_type(name="RelationshipProperty")

    assert issubclass(car, InfrahubObject)
    assert issubclass(edged_car, InfrahubObject)
    assert issubclass(nested_edged_car, InfrahubObject)
    assert issubclass(person, InfrahubObject)
    assert issubclass(edged_person, InfrahubObject)
    assert issubclass(nested_edged_person, InfrahubObject)
    assert issubclass(relationship_property, graphene.ObjectType)

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
        "profiles",
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
        "profiles",
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


async def test_generate_filters(db: InfrahubDatabase, default_branch: Branch, data_schema, car_person_schema_generics):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)

    person = schema.get(name="TestPerson")
    filters = gqlm.generate_filters(schema=person, top_level=True)
    expected_filters = [
        "offset",
        "limit",
        "partial_match",
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
        "profiles__height__is_protected",
        "profiles__height__is_visible",
        "profiles__height__owner__id",
        "profiles__height__source__id",
        "profiles__height__value",
        "profiles__height__values",
        "profiles__ids",
        "profiles__profile_name__is_protected",
        "profiles__profile_name__is_visible",
        "profiles__profile_name__owner__id",
        "profiles__profile_name__source__id",
        "profiles__profile_name__value",
        "profiles__profile_name__values",
        "profiles__profile_priority__is_protected",
        "profiles__profile_priority__is_visible",
        "profiles__profile_priority__owner__id",
        "profiles__profile_priority__source__id",
        "profiles__profile_priority__value",
        "profiles__profile_priority__values",
        "subscriber_of_groups__description__value",
        "subscriber_of_groups__description__values",
        "subscriber_of_groups__ids",
        "subscriber_of_groups__label__value",
        "subscriber_of_groups__label__values",
        "subscriber_of_groups__name__value",
        "subscriber_of_groups__name__values",
    ]
    assert sorted(list(filters.keys())) == sorted(expected_filters)
