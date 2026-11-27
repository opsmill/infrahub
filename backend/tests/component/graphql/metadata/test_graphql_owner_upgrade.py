"""Clients read the attributes that an earlier release wrote, after the graph migrations of the owners ran."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.graph.m085_hide_replaced_branch_attribute_owners import Migration085
from infrahub.core.migrations.graph.m086_close_repository_owner_edges import Migration086
from infrahub.core.migrations.graph.m087_create_no_owner_vertex import Migration087
from infrahub.core.migrations.shared import MigrationInput
from infrahub.graphql.constants import IS_PROTECTED_DEPRECATION_REASON, OWNER_DEPRECATION_REASON
from tests.helpers.ownership import ADD_ATTRIBUTE_OWNER, add_node, add_owner_edge, create_groups, own, run

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

READ_COLORS = """
query($protected: Boolean) {
    TestCar(color__is_protected: $protected) {
        edges {
            node {
                name { value }
                color { is_protected owner { id } ownership { state origin origin_node { id } owners { id } } }
            }
        }
    }
}
"""

DEPRECATIONS = """
query {
    interface: __type(name: "AttributeInterface") {
        fields(includeDeprecated: true) { name isDeprecated deprecationReason }
        possibleTypes { name fields(includeDeprecated: true) { name isDeprecated deprecationReason } }
    }
    query: __type(name: "Query") {
        fields { name args(includeDeprecated: true) { name isDeprecated deprecationReason } }
    }
    link_properties: __type(name: "RelationshipProperty") {
        fields(includeDeprecated: true) { name isDeprecated }
    }
    attribute_input: __type(name: "TextAttributeUpdate") {
        inputFields(includeDeprecated: true) { name isDeprecated }
    }
}
"""

# The car has no owners, so nothing gives owners to its attributes.
INHERIT_NOTHING = {"state": "INHERIT", "origin": None, "origin_node": None, "owners": []}


async def _upgrade(db: InfrahubDatabase) -> None:
    for migration in (Migration085(), Migration086(), Migration087()):
        result = await migration.execute(migration_input=MigrationInput(db=db))
        assert result.errors == []


async def _colors(db: InfrahubDatabase, branch: Branch, protected: bool | None = None) -> dict[str, dict[str, Any]]:
    """Return the `color` of each car that the query lists, by car name."""
    edges = (await run(db=db, branch=branch, query=READ_COLORS, variables={"protected": protected}))["TestCar"]["edges"]
    colors = {edge["node"]["name"]["value"]: edge["node"]["color"] for edge in edges}
    assert len(colors) == len(edges)
    return colors


def _color(ownership: dict[str, Any], owner_id: str | None = None, is_protected: bool = False) -> dict[str, Any]:
    return {
        "is_protected": is_protected,
        "owner": None if owner_id is None else {"id": owner_id},
        "ownership": ownership,
    }


async def test_attribute_owners_of_an_earlier_release_read_as_own_owners_or_inherit(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    group_id = (await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-team")).id
    person = await add_node(db=db, kind="TestPerson", name="John")
    owned_car = await add_node(db=db, kind="TestCar", name="owned-car", owner=person, color="#111111")
    await add_node(db=db, kind="TestCar", name="plain-car", owner=person, color="#222222")
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=owned_car.id, owner_id=group_id
    )
    before_upgrade = await _colors(db=db, branch=default_branch)

    await _upgrade(db=db)

    assert {name: color["owner"] for name, color in before_upgrade.items()} == {
        "owned-car": {"id": group_id},
        "plain-car": None,
    }
    assert await _colors(db=db, branch=default_branch) == {
        "owned-car": _color(ownership=own(owned_car.id, group_id), owner_id=group_id),
        "plain-car": _color(ownership=INHERIT_NOTHING),
    }


async def test_attribute_owner_written_on_a_branch_before_the_upgrade_is_the_owner_on_that_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    groups = await create_groups(db=db, names=("main-owner", "branch-owner"))
    main_owner, branch_owner = groups["main-owner"], groups["branch-owner"]
    person = await add_node(db=db, kind="TestPerson", name="John")
    car = await add_node(db=db, kind="TestCar", name="volt", owner=person, color="#111111")
    await add_owner_edge(db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=car.id, owner_id=main_owner)
    branch = await create_branch(db=db, branch_name="branch1")
    await add_owner_edge(db=db, query=ADD_ATTRIBUTE_OWNER, branch=branch, node_id=car.id, owner_id=branch_owner)
    before_upgrade = await _colors(db=db, branch=branch)

    await _upgrade(db=db)

    assert before_upgrade == {"volt": _color(ownership=own(car.id, main_owner, branch_owner))}
    assert await _colors(db=db, branch=branch) == {
        "volt": _color(ownership=own(car.id, branch_owner), owner_id=branch_owner)
    }
    assert await _colors(db=db, branch=default_branch) == {
        "volt": _color(ownership=own(car.id, main_owner), owner_id=main_owner)
    }


async def test_is_protected_and_its_filter_give_the_same_cars_after_the_upgrade(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    person = await add_node(db=db, kind="TestPerson", name="John")
    await add_node(
        db=db, kind="TestCar", name="protected-car", owner=person, color={"value": "#111111", "is_protected": True}
    )
    await add_node(db=db, kind="TestCar", name="plain-car", owner=person, color="#222222")
    filter_values = (None, True, False)
    before_upgrade = [await _colors(db=db, branch=default_branch, protected=value) for value in filter_values]

    await _upgrade(db=db)

    protected = {"protected-car": _color(ownership=INHERIT_NOTHING, is_protected=True)}
    plain = {"plain-car": _color(ownership=INHERIT_NOTHING)}
    assert before_upgrade == [protected | plain, protected, plain]
    assert [await _colors(db=db, branch=default_branch, protected=value) for value in filter_values] == before_upgrade


async def test_schema_marks_is_protected_of_attributes_and_its_filters_as_deprecated(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> None:
    data = await run(db=db, branch=default_branch, query=DEPRECATIONS)

    interface = data["interface"]
    assert {field["name"]: field["deprecationReason"] for field in interface["fields"] if field["isDeprecated"]} == {
        "is_protected": IS_PROTECTED_DEPRECATION_REASON
    }
    attribute_types = interface["possibleTypes"]
    assert len(attribute_types) > 0
    for attribute_type in attribute_types:
        deprecated = {
            field["name"]: field["deprecationReason"] for field in attribute_type["fields"] if field["isDeprecated"]
        }
        assert (attribute_type["name"], deprecated) == (
            attribute_type["name"],
            {"is_protected": IS_PROTECTED_DEPRECATION_REASON, "owner": OWNER_DEPRECATION_REASON},
        )

    car_query = next(field for field in data["query"]["fields"] if field["name"] == "TestCar")
    assert {arg["name"]: arg["deprecationReason"] for arg in car_query["args"] if arg["isDeprecated"]} == dict.fromkeys(
        [
            "any__is_protected",
            "color__is_protected",
            "driver__height__is_protected",
            "driver__name__is_protected",
            "is_electric__is_protected",
            "name__is_protected",
            "nbr_seats__is_protected",
            "owner__height__is_protected",
            "owner__name__is_protected",
            "profiles__profile_name__is_protected",
            "profiles__profile_priority__is_protected",
            "transmission__is_protected",
        ],
        IS_PROTECTED_DEPRECATION_REASON,
    )
    assert [field["name"] for field in data["link_properties"]["fields"] if field["isDeprecated"]] == []
    assert [field["name"] for field in data["attribute_input"]["inputFields"] if field["isDeprecated"]] == ["owner"]
