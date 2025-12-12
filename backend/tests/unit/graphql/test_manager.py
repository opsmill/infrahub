import inspect

import graphene
import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.graphql.manager import GraphQLSchemaManager
from infrahub.graphql.registry import registry as graphql_registry
from infrahub.graphql.types import InfrahubObject
from infrahub.graphql.types.node import InfrahubObjectWithoutMeta


async def test_input_type_registration() -> None:
    assert registry.input_type is not {}  # noqa


async def test_generate_interface_object(db: InfrahubDatabase, default_branch: Branch, generic_vehicule_schema) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)

    result = gqlm.generate_interface_object(schema=generic_vehicule_schema)
    assert inspect.isclass(result.reference)
    assert issubclass(result.reference, graphene.Interface)
    assert result.reference._meta.name == "TestVehicule"
    assert sorted(result.reference._meta.fields.keys()) == ["description", "display_label", "hfid", "id", "name"]


async def test_generate_graphql_object(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    reset_graphql_schema_between_tests: None,
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)

    generic_schema = schema.get(name="TestGenericCriticality", duplicate=False)
    gqlm.generate_interface_object(schema=generic_schema, populate_cache=True)
    result = gqlm.generate_graphql_object(schema=criticality_schema)
    assert inspect.isclass(result.reference)
    assert issubclass(result.reference, InfrahubObject)
    assert result.reference._meta.name == "TestCriticality"
    assert sorted(result.reference._meta.fields.keys()) == [
        "_updated_at",
        "color",
        "description",
        "display_label",
        "hfid",
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
        "time",
    ]


async def test_generate_graphql_object_with_interface(
    db: InfrahubDatabase, default_branch: Branch, data_schema, generic_vehicule_schema, car_schema
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)
    gqlm.generate_interface_object(schema=generic_vehicule_schema, populate_cache=True)

    result = gqlm.generate_graphql_object(schema=car_schema)
    assert inspect.isclass(result.reference)
    assert issubclass(result.reference, InfrahubObject)
    assert result.reference._meta.name == "TestCar"
    assert sorted(result.reference._meta.fields.keys()) == [
        "_updated_at",
        "description",
        "display_label",
        "hfid",
        "id",
        "name",
        "nbr_doors",
    ]


async def test_generate_graphql_mutation_create(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)

    generic_schema = schema.get(name="TestGenericCriticality", duplicate=False)
    gqlm.generate_interface_object(schema=generic_schema, populate_cache=True)
    input_type = gqlm.generate_graphql_mutation_create_input(schema=criticality_schema)
    result = gqlm.generate_graphql_mutation_create(schema=criticality_schema, input_type=input_type)
    assert result._meta.name == "TestCriticalityCreate"
    assert sorted(result._meta.fields.keys()) == ["object", "ok"]


async def test_generate_graphql_mutation_update(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)

    generic_schema = schema.get(name="TestGenericCriticality", duplicate=False)
    gqlm.generate_interface_object(schema=generic_schema, populate_cache=True)
    input_type = gqlm.generate_graphql_mutation_update_input(schema=criticality_schema)
    result = gqlm.generate_graphql_mutation_update(schema=criticality_schema, input_type=input_type)
    assert result._meta.name == "TestCriticalityUpdate"
    assert sorted(result._meta.fields.keys()) == ["object", "ok"]


async def test_generate_object_types(
    db: InfrahubDatabase, default_branch: Branch, data_schema, car_person_schema
) -> None:
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
    assert issubclass(edged_car, InfrahubObjectWithoutMeta)
    assert issubclass(nested_edged_car, InfrahubObjectWithoutMeta)
    assert issubclass(person, InfrahubObject)
    assert issubclass(edged_person, InfrahubObjectWithoutMeta)
    assert issubclass(nested_edged_person, InfrahubObjectWithoutMeta)
    assert issubclass(relationship_property, graphene.ObjectType)

    assert sorted(car._meta.fields.keys()) == [
        "_updated_at",
        "color",
        "display_label",
        "driver",
        "hfid",
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

    assert sorted(edged_car._meta.fields.keys()) == ["node", "node_metadata"]
    assert str(edged_car._meta.fields["node"].type) == "TestCar"
    assert sorted(nested_edged_car._meta.fields.keys()) == [
        "node",
        "node_metadata",
        "properties",
        "relationship_metadata",
    ]
    assert str(nested_edged_car._meta.fields["node"].type) == "TestCar"
    assert str(nested_edged_car._meta.fields["properties"].type) == "RelationshipProperty"

    assert sorted(person._meta.fields.keys()) == [
        "_updated_at",
        "cars",
        "cars_driven",
        "display_label",
        "height",
        "hfid",
        "id",
        "member_of_groups",
        "name",
        "profiles",
        "subscriber_of_groups",
    ]
    assert sorted(edged_person._meta.fields.keys()) == ["node", "node_metadata"]
    assert str(edged_person._meta.fields["node"].type) == "TestPerson"
    assert sorted(nested_edged_person._meta.fields.keys()) == [
        "node",
        "node_metadata",
        "properties",
        "relationship_metadata",
    ]
    assert str(nested_edged_person._meta.fields["node"].type) == "TestPerson"
    assert str(nested_edged_person._meta.fields["properties"].type) == "RelationshipProperty"
    assert sorted(relationship_property._meta.fields.keys()) == [
        "is_protected",
        "owner",
        "source",
        "updated_at",
    ]


async def test_generate_filters(
    db: InfrahubDatabase, default_branch: Branch, data_schema, car_person_schema_generics
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)

    person = schema.get(name="TestPerson")
    filters = gqlm.generate_filters(schema=person, top_level=True)
    expected_filters = [
        "offset",
        "limit",
        "order",
        "partial_match",
        "ids",
        "any__is_protected",
        "any__owner__id",
        "any__source__id",
        "any__value",
        "any__values",
        "cars__color__is_protected",
        "cars__color__owner__id",
        "cars__color__source__id",
        "cars__color__value",
        "cars__color__values",
        "cars__ids",
        "cars__isnull",
        "cars__name__is_protected",
        "cars__name__owner__id",
        "cars__name__source__id",
        "cars__name__value",
        "cars__name__values",
        "cars__nbr_seats__is_protected",
        "cars__nbr_seats__owner__id",
        "cars__nbr_seats__source__id",
        "cars__nbr_seats__value",
        "cars__nbr_seats__values",
        "height__is_protected",
        "height__isnull",
        "height__owner__id",
        "height__source__id",
        "height__value",
        "height__values",
        "hfid",
        "member_of_groups__description__value",
        "member_of_groups__description__values",
        "member_of_groups__group_type__value",
        "member_of_groups__group_type__values",
        "member_of_groups__ids",
        "member_of_groups__isnull",
        "member_of_groups__label__value",
        "member_of_groups__label__values",
        "member_of_groups__name__value",
        "member_of_groups__name__values",
        "name__is_protected",
        "name__isnull",
        "name__owner__id",
        "name__source__id",
        "name__value",
        "name__values",
        "profiles__ids",
        "profiles__isnull",
        "profiles__profile_name__is_protected",
        "profiles__profile_name__owner__id",
        "profiles__profile_name__source__id",
        "profiles__profile_name__value",
        "profiles__profile_name__values",
        "profiles__profile_priority__is_protected",
        "profiles__profile_priority__owner__id",
        "profiles__profile_priority__source__id",
        "profiles__profile_priority__value",
        "profiles__profile_priority__values",
        "subscriber_of_groups__description__value",
        "subscriber_of_groups__description__values",
        "subscriber_of_groups__group_type__value",
        "subscriber_of_groups__group_type__values",
        "subscriber_of_groups__ids",
        "subscriber_of_groups__isnull",
        "subscriber_of_groups__label__value",
        "subscriber_of_groups__label__values",
        "subscriber_of_groups__name__value",
        "subscriber_of_groups__name__values",
    ]
    assert sorted(filters.keys()) == sorted(expected_filters)


@pytest.mark.parametrize(
    "schema_changed_at_null,schema_hash_null", [(False, False), (True, False), (False, True), (True, True)]
)
async def test_branch_caching_hit(
    db: InfrahubDatabase,
    default_branch: Branch,
    data_schema,
    car_person_schema_generics,
    schema_changed_at_null: bool,
    schema_hash_null: bool,
) -> None:
    default_branch.update_schema_hash()
    same_branch = default_branch.model_copy()
    if schema_changed_at_null:
        same_branch.schema_changed_at = None
    if schema_hash_null:
        same_branch.schema_hash = None
    schema_branch = registry.schema.get_schema_branch(default_branch.name)

    manager1 = graphql_registry.get_manager_for_branch(branch=default_branch, schema_branch=schema_branch)
    manager2 = graphql_registry.get_manager_for_branch(branch=same_branch, schema_branch=schema_branch)

    assert manager1 is manager2


async def test_branch_caching_miss(
    db: InfrahubDatabase,
    default_branch: Branch,
    data_schema,
    car_person_schema_generics,
) -> None:
    default_branch.update_schema_hash()
    same_branch = default_branch.model_copy()
    schema_branch = registry.schema.get_schema_branch(default_branch.name)

    default_branch.active_schema_hash.main = "abc"
    same_branch.update_schema_hash()

    manager1 = graphql_registry.get_manager_for_branch(branch=default_branch, schema_branch=schema_branch)
    manager2 = graphql_registry.get_manager_for_branch(branch=same_branch, schema_branch=schema_branch)

    assert manager1 is not manager2


async def test_branch_purge(
    db: InfrahubDatabase,
    default_branch: Branch,
    data_schema: None,
    car_person_schema_generics: None,
) -> None:
    default_branch.update_schema_hash()
    purged_branch = "i-will-be-purged"
    active_branch = "i-will-not-be-purged"
    schema_branch = registry.schema.get_schema_branch(default_branch.name)

    graphql_registry.get_manager_for_branch(branch=default_branch, schema_branch=schema_branch)
    graphql_registry.purge_inactive(active_branches=[default_branch.name])
    graphql_registry._add_branch_hash(branch_name=active_branch, schema_hash=default_branch.active_schema_hash.main)
    graphql_registry._add_branch_hash(branch_name=purged_branch, schema_hash=default_branch.active_schema_hash.main)

    assert default_branch.active_schema_hash.main in graphql_registry._branch_details_by_hash.keys()
    assert default_branch.active_schema_hash.main in graphql_registry._branch_name_by_hash.keys()

    assert active_branch in graphql_registry._branch_name_by_hash[default_branch.active_schema_hash.main]
    assert purged_branch in graphql_registry._branch_name_by_hash[default_branch.active_schema_hash.main]
    purged_branches = graphql_registry.purge_inactive(active_branches=[active_branch, default_branch.name])
    assert active_branch in graphql_registry._branch_name_by_hash[default_branch.active_schema_hash.main]
    assert purged_branch not in graphql_registry._branch_name_by_hash[default_branch.active_schema_hash.main]

    assert purged_branches == {purged_branch}
