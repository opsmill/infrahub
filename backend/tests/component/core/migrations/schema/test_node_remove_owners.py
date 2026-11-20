from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_remove import NodeRemoveMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.ownership.models import (
    NODE_HOLDER,
    NODE_SOURCES_HOLDER,
    NODE_TARGET_HOLDER,
    HolderKey,
    StoredNodeOwnership,
    StoredOwnerState,
    field_holder,
)
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.path import SchemaPath
from infrahub.core.query import QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from tests.helpers.ownership import USER_ID, add_node

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

CAR_KIND = "TestCar"
PERSON_KIND = "TestPerson"
NO_OWNER: tuple[str, ...] = ()

Edge = tuple[str, str, str]
"""The start vertex, the type and the end vertex of an edge. A node vertex is named by its kind."""


@dataclass
class CarsAndPerson:
    car_ids: list[str]
    person_id: str
    group_ids: list[str]


async def _write(
    db: InfrahubDatabase,
    branch: Branch,
    node_id: str,
    holder: HolderKey,
    owner_ids: tuple[str, ...],
    template_id: str | None = None,
) -> None:
    """Store a state without the check of the kind of each owner, so that a car can stand for any owner or source."""
    await OwnershipRepository(db=db, branch=branch, at=None).write(
        node_id=node_id,
        holder=holder,
        state=StoredOwnerState(owner_ids=owner_ids, template_id=template_id),
        write_branch=branch,
        at=Timestamp(),
        user_id=USER_ID,
    )


async def _read(db: InfrahubDatabase, branch: Branch, node_id: str) -> dict[str, StoredNodeOwnership]:
    return await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=[node_id], attributes=True)


async def _active_edges(db: InfrahubDatabase, branch: Branch, node_ids: list[str]) -> list[Edge]:
    """Return each owner edge and each source edge that the branch reads as active at the nodes.

    The edges start or end at a node, at one of its attributes or at one of its sets of owners.
    """
    branch_filter, params = branch.get_query_filter_path(at=Timestamp().to_string())
    query = """
MATCH (n:Node)-[:HAS_ATTRIBUTE|HAS_OWNER_SET|HAS_TARGET_OWNER_SET*0..1]->(h)
WHERE n.uuid IN $node_ids
WITH DISTINCT h
MATCH (h)-[e:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SET|HAS_TARGET_OWNER_SET|HAS_OWNER_SOURCE|HAS_SOURCE]-(peer)
WITH DISTINCT startNode(e) AS start_vertex, type(e) AS edge_type, endNode(e) AS end_vertex
CALL (start_vertex, edge_type, end_vertex) {
    MATCH (start_vertex)-[r:$(edge_type)]->(end_vertex)
    WHERE %(branch_filter)s
    RETURN r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH start_vertex, edge_type, end_vertex, r
WHERE r.status = "active"
UNWIND [start_vertex, end_vertex] AS vertex
WITH start_vertex, edge_type, end_vertex, collect(
    CASE
        WHEN vertex:Attribute THEN "Attribute"
        WHEN vertex:OwnerSet THEN "OwnerSet"
        WHEN vertex:NoOwner THEN "NoOwner"
        ELSE vertex.kind
    END
) AS names
RETURN names[0] AS start_name, edge_type, names[1] AS end_name
    """ % {"branch_filter": branch_filter}
    rows = await db.execute_query(query=query, params={**params, "node_ids": node_ids}, type=QueryType.READ)
    return sorted((row["start_name"], row["edge_type"], row["end_name"]) for row in rows)


async def _remove_car_kind(db: InfrahubDatabase, branch: Branch) -> None:
    schema = registry.schema.get_schema_branch(name=branch.name)
    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name=CAR_KIND),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind=CAR_KIND),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not execution_result.errors


@pytest.fixture
async def cars_and_person(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
) -> CarsAndPerson:
    groups = [await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name=name) for name in ("dc-emea", "security")]
    person = await add_node(db=db, kind=PERSON_KIND, name="John")
    cars = [
        await add_node(db=db, kind=CAR_KIND, name=name, nbr_seats=5, is_electric=True, owner=person)
        for name in ("accord", "camry")
    ]
    return CarsAndPerson(
        car_ids=[car.id for car in cars], person_id=person.id, group_ids=sorted(group.id for group in groups)
    )


@pytest.mark.parametrize("on_branch", [pytest.param(False, id="default_branch"), pytest.param(True, id="branch")])
async def test_removal_of_a_kind_closes_the_owner_edges_and_the_source_edges_of_its_nodes(
    db: InfrahubDatabase, default_branch: Branch, cars_and_person: CarsAndPerson, on_branch: bool
) -> None:
    """The person keeps the edges to the account groups and to the "no owner" vertex that the cars also use."""
    accord_id, camry_id = cars_and_person.car_ids
    person_id = cars_and_person.person_id
    dc_emea, security = cars_and_person.group_ids
    car_schema = registry.schema.get(name=CAR_KIND, branch=default_branch, duplicate=False)
    owner_set = field_holder(schema=car_schema, field_name="owner")
    color = field_holder(schema=car_schema, field_name="color")
    person_name = field_holder(
        schema=registry.schema.get(name=PERSON_KIND, branch=default_branch, duplicate=False), field_name="name"
    )
    assert owner_set
    assert color
    assert person_name
    for node_id, holder, owner_ids, template_id in (
        (accord_id, NODE_HOLDER, (dc_emea,), person_id),
        (accord_id, NODE_SOURCES_HOLDER, (security,), None),
        (accord_id, owner_set, (security,), person_id),
        (accord_id, color, (dc_emea,), None),
        (accord_id, NODE_TARGET_HOLDER, NO_OWNER, None),
        (camry_id, NODE_HOLDER, NO_OWNER, None),
        (camry_id, color, NO_OWNER, None),
        (person_id, NODE_HOLDER, (dc_emea,), None),
        (person_id, person_name, NO_OWNER, None),
    ):
        await _write(
            db=db, branch=default_branch, node_id=node_id, holder=holder, owner_ids=owner_ids, template_id=template_id
        )
    branch = await create_branch(branch_name="branch2", db=db) if on_branch else default_branch
    car_edges = await _active_edges(db=db, branch=default_branch, node_ids=cars_and_person.car_ids)
    person_before = await _read(db=db, branch=branch, node_id=person_id)

    await _remove_car_kind(db=db, branch=branch)

    assert car_edges == [
        ("Attribute", "HAS_NO_OWNER", "NoOwner"),
        ("Attribute", "HAS_OWNER", InfrahubKind.ACCOUNTGROUP),
        ("OwnerSet", "HAS_NO_OWNER", "NoOwner"),
        ("OwnerSet", "HAS_OWNER", InfrahubKind.ACCOUNTGROUP),
        ("OwnerSet", "HAS_OWNER_SOURCE", PERSON_KIND),
        (CAR_KIND, "HAS_NO_OWNER", "NoOwner"),
        (CAR_KIND, "HAS_OWNER", InfrahubKind.ACCOUNTGROUP),
        (CAR_KIND, "HAS_OWNER_SET", "OwnerSet"),
        (CAR_KIND, "HAS_OWNER_SOURCE", PERSON_KIND),
        (CAR_KIND, "HAS_SOURCE", InfrahubKind.ACCOUNTGROUP),
        (CAR_KIND, "HAS_TARGET_OWNER_SET", "OwnerSet"),
    ]
    assert await _active_edges(db=db, branch=branch, node_ids=cars_and_person.car_ids) == []
    assert await _read(db=db, branch=branch, node_id=person_id) == person_before
    if on_branch:
        assert await _active_edges(db=db, branch=default_branch, node_ids=cars_and_person.car_ids) == car_edges
    await verify_graph(db=db)


async def _delete_cars(db: InfrahubDatabase, branch: Branch) -> None:
    cars = await NodeManager.query(db=db, schema=CAR_KIND, branch=branch)
    await NodeManager.delete(db=db, nodes=cars, branch=branch, cascade_delete=False)


@pytest.mark.parametrize("on_branch", [pytest.param(False, id="default_branch"), pytest.param(True, id="branch")])
@pytest.mark.parametrize(
    "remove_cars", [pytest.param(_remove_car_kind, id="kind_removal"), pytest.param(_delete_cars, id="node_delete")]
)
async def test_removal_of_a_kind_keeps_the_owners_and_sources_that_are_its_nodes_as_a_delete_does(
    db: InfrahubDatabase,
    default_branch: Branch,
    cars_and_person: CarsAndPerson,
    on_branch: bool,
    remove_cars: Callable[..., Awaitable[None]],
) -> None:
    """A deleted owner or source stays in the list of its holder, and the mark of a copy from the deleted node closes."""
    accord_id, camry_id = cars_and_person.car_ids
    person_id = cars_and_person.person_id
    person_schema = registry.schema.get(name=PERSON_KIND, branch=default_branch, duplicate=False)
    cars_set = field_holder(schema=person_schema, field_name="cars")
    name = field_holder(schema=person_schema, field_name="name")
    assert cars_set
    assert name
    holders = (NODE_HOLDER, NODE_SOURCES_HOLDER, cars_set, name)
    for holder in holders:
        await _write(
            db=db,
            branch=default_branch,
            node_id=person_id,
            holder=holder,
            owner_ids=(accord_id,),
            template_id=None if holder is NODE_SOURCES_HOLDER else camry_id,
        )
    branch = await create_branch(branch_name="branch2", db=db) if on_branch else default_branch
    person_edges = await _active_edges(db=db, branch=default_branch, node_ids=[person_id])

    await remove_cars(db=db, branch=branch)

    assert person_edges == [
        ("Attribute", "HAS_OWNER", CAR_KIND),
        ("Attribute", "HAS_OWNER_SOURCE", CAR_KIND),
        ("OwnerSet", "HAS_OWNER", CAR_KIND),
        ("OwnerSet", "HAS_OWNER_SOURCE", CAR_KIND),
        (PERSON_KIND, "HAS_OWNER", CAR_KIND),
        (PERSON_KIND, "HAS_OWNER_SET", "OwnerSet"),
        (PERSON_KIND, "HAS_OWNER_SOURCE", CAR_KIND),
        (PERSON_KIND, "HAS_SOURCE", CAR_KIND),
    ]
    assert await _active_edges(db=db, branch=branch, node_ids=[person_id]) == [
        ("Attribute", "HAS_OWNER", CAR_KIND),
        ("OwnerSet", "HAS_OWNER", CAR_KIND),
        (PERSON_KIND, "HAS_OWNER", CAR_KIND),
        (PERSON_KIND, "HAS_OWNER_SET", "OwnerSet"),
        (PERSON_KIND, "HAS_SOURCE", CAR_KIND),
    ]
    stored = await _read(db=db, branch=branch, node_id=person_id)
    assert dict(stored[person_id].holders) == {holder: StoredOwnerState(owner_ids=(accord_id,)) for holder in holders}
    if on_branch:
        assert await _active_edges(db=db, branch=default_branch, node_ids=[person_id]) == person_edges
    await verify_graph(db=db)
