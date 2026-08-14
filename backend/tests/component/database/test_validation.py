from dataclasses import dataclass
from typing import Awaitable, Callable

import pytest

from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import (
    GraphCheck,
    GraphValidationError,
    collect_graph_violations,
    verify_graph,
)


async def _duplicate_attribute_vertex(db: InfrahubDatabase, car: Node, person: Node) -> None:
    """Attach a second Attribute vertex with the same name to the car."""
    query = """
MATCH (n:Node {uuid: $node_id})-[hae:HAS_ATTRIBUTE {status: "active"}]->(a:Attribute {name: "name"})
WHERE hae.to IS NULL
WITH n, hae, a LIMIT 1
CREATE (dup:Attribute)
SET dup = properties(a)
SET dup.uuid = randomUUID()
CREATE (n)-[new_hae:HAS_ATTRIBUTE]->(dup)
SET new_hae = properties(hae)
    """
    await db.execute_query(query=query, params={"node_id": car.id})


async def _duplicate_has_value_edge(db: InfrahubDatabase, car: Node, person: Node) -> None:
    """Add a second identical HAS_VALUE edge below one of the car's attributes."""
    query = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "name"})-[hv:HAS_VALUE]->(av:AttributeValue)
WITH a, hv, av LIMIT 1
CREATE (a)-[dup_hv:HAS_VALUE]->(av)
SET dup_hv = properties(hv)
    """
    await db.execute_query(query=query, params={"node_id": car.id})


async def _duplicate_relationship_vertex(db: InfrahubDatabase, car: Node, person: Node) -> None:
    """Attach a second Relationship vertex with the same name between the car and its owner."""
    query = """
MATCH (car:Node {uuid: $car_id})-[e1:IS_RELATED]->(rel:Relationship)-[e2:IS_RELATED]->(person:Node {uuid: $person_id})
WHERE e1.status = "active" AND e1.to IS NULL AND e2.status = "active" AND e2.to IS NULL
WITH car, e1, rel, e2, person LIMIT 1
CREATE (dup:Relationship)
SET dup = properties(rel)
SET dup.uuid = randomUUID()
CREATE (car)-[new_e1:IS_RELATED]->(dup)
SET new_e1 = properties(e1)
CREATE (dup)-[new_e2:IS_RELATED]->(person)
SET new_e2 = properties(e2)
    """
    await db.execute_query(query=query, params={"car_id": car.id, "person_id": person.id})


async def _remove_owner_side_relationship_edge(db: InfrahubDatabase, car: Node, person: Node) -> None:
    """Leave the car's owner Relationship vertex with a single active IS_RELATED edge."""
    query = """
MATCH (:Node {uuid: $car_id})-[:IS_RELATED]-(rel:Relationship)-[e2:IS_RELATED]-(:Node {uuid: $person_id})
WITH e2 LIMIT 1
DELETE e2
    """
    await db.execute_query(query=query, params={"car_id": car.id, "person_id": person.id})


async def _delete_attribute_edge_only(db: InfrahubDatabase, car: Node, person: Node) -> None:
    """Mark one of the car's HAS_ATTRIBUTE edges deleted, leaving its HAS_VALUE edge active."""
    query = """
MATCH (:Node {uuid: $node_id})-[hae:HAS_ATTRIBUTE {status: "active"}]->(:Attribute {name: "name"})
WHERE hae.to IS NULL
WITH hae LIMIT 1
SET hae.status = "deleted"
    """
    await db.execute_query(query=query, params={"node_id": car.id})


async def _add_edge_after_node_delete(db: InfrahubDatabase, car: Node, person: Node) -> None:
    """Delete the car, then attach an edge to it afterwards."""
    query = """
MATCH (n:Node {uuid: $node_id})-[is_part_of:IS_PART_OF]->(:Root)
WITH n, is_part_of LIMIT 1
SET is_part_of.status = "deleted"
WITH n, is_part_of
MATCH (n)-[hae:HAS_ATTRIBUTE]->(a:Attribute {name: "name"})
WITH n, is_part_of, hae, a LIMIT 1
CREATE (n)-[:HAS_ATTRIBUTE {branch: hae.branch, branch_level: hae.branch_level, status: "active", from: $at}]->(a)
    """
    await db.execute_query(query=query, params={"node_id": car.id, "at": Timestamp().to_string()})


async def _delete_attribute_cleanly(db: InfrahubDatabase, node_uuid: str, attr_name: str, at: str) -> None:
    """Delete an attribute the way the product does: close every open edge and record a deleted one."""
    query = """
MATCH (n:Node {uuid: $node_id})-[hae:HAS_ATTRIBUTE {status: "active"}]->(a:Attribute {name: $attr_name})
WHERE hae.to IS NULL
WITH n, hae, a LIMIT 1
SET hae.to = $at
CREATE (n)-[:HAS_ATTRIBUTE {branch: hae.branch, branch_level: hae.branch_level, status: "deleted", from: $at}]->(a)
WITH a
MATCH (a)-[child]->(peer)
WHERE child.status = "active" AND child.to IS NULL
SET child.to = $at
CREATE (a)-[:$(type(child)) {branch: child.branch, branch_level: child.branch_level, status: "deleted", from: $at}]->(peer)
    """
    await db.execute_query(query=query, params={"node_id": node_uuid, "attr_name": attr_name, "at": at})


async def _write_value_edge_on_branch(
    db: InfrahubDatabase, node_uuid: str, attr_name: str, branch: Branch, at: str
) -> None:
    """Write an active HAS_VALUE edge for the attribute on a branch."""
    query = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attr_name})-[:HAS_VALUE]->(v)
WITH a, v LIMIT 1
CREATE (a)-[:HAS_VALUE {branch: $branch_name, branch_level: $branch_level, status: "active", from: $at}]->(v)
    """
    await db.execute_query(
        query=query,
        params={
            "node_id": node_uuid,
            "attr_name": attr_name,
            "branch_name": branch.name,
            "branch_level": branch.hierarchy_level,
            "at": at,
        },
    )


async def _split_node_vertex_keeping_the_field(db: InfrahubDatabase, node_uuid: str, attr_name: str, at: str) -> None:
    """Copy the node vertex the way a kind update does, moving the field's edge onto the copy.

    The old vertex's edge is deleted and the copy's is opened at the same moment, both pointing at the one
    field vertex, so the field never stops being in use.
    """
    query = """
MATCH (n:Node {uuid: $node_id})-[hae:HAS_ATTRIBUTE {status: "active"}]->(a:Attribute {name: $attr_name})
WHERE hae.to IS NULL
WITH n, hae, a LIMIT 1
SET hae.to = $at
CREATE (n)-[:HAS_ATTRIBUTE {branch: hae.branch, branch_level: hae.branch_level, status: "deleted", from: $at}]->(a)
CREATE (copy:$(labels(n)))
SET copy = properties(n)
CREATE (copy)-[:HAS_ATTRIBUTE {branch: hae.branch, branch_level: hae.branch_level, status: "active", from: $at}]->(a)
    """
    await db.execute_query(query=query, params={"node_id": node_uuid, "attr_name": attr_name, "at": at})


async def _update_value_on_branch(
    db: InfrahubDatabase, node_uuid: str, attr_name: str, branch: Branch, value: str, at: str
) -> None:
    """Change an attribute's value the way the product does: close the open edge, open one to the new value."""
    query = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attr_name})-[hv:HAS_VALUE]->(:AttributeValue)
WHERE hv.status = "active" AND hv.to IS NULL
WITH a, hv LIMIT 1
SET hv.to = $at
MERGE (new_value:AttributeValue:AttributeValueIndexed {value: $value, is_default: false})
CREATE (a)-[:HAS_VALUE {branch: $branch_name, branch_level: $branch_level, status: "active", from: $at}]->(new_value)
    """
    await db.execute_query(
        query=query,
        params={
            "node_id": node_uuid,
            "attr_name": attr_name,
            "branch_name": branch.name,
            "branch_level": branch.hierarchy_level,
            "value": value,
            "at": at,
        },
    )


async def _delete_attribute_on_branch(
    db: InfrahubDatabase, node_uuid: str, attr_name: str, branch: Branch, at: str
) -> None:
    """Delete an attribute on a branch, shadowing the default branch's edges rather than closing them."""
    query = """
MATCH (n:Node {uuid: $node_id})-[hae:HAS_ATTRIBUTE {status: "active"}]->(a:Attribute {name: $attr_name})
WHERE hae.to IS NULL
WITH n, hae, a LIMIT 1
CREATE (n)-[:HAS_ATTRIBUTE {branch: $branch_name, branch_level: $branch_level, status: "deleted", from: $at}]->(a)
WITH a
MATCH (a)-[child]->(peer)
WHERE child.status = "active" AND child.to IS NULL
CREATE (a)-[:$(type(child)) {branch: $branch_name, branch_level: $branch_level, status: "deleted", from: $at}]->(peer)
    """
    await db.execute_query(
        query=query,
        params={
            "node_id": node_uuid,
            "attr_name": attr_name,
            "branch_name": branch.name,
            "branch_level": branch.hierarchy_level,
            "at": at,
        },
    )


@dataclass
class GraphDamageCase:
    name: str
    check: GraphCheck
    damage: Callable[[InfrahubDatabase, Node, Node], Awaitable[None]]
    expected_violations: int
    scoped_violations: int
    included_kinds: list[str]
    excluded_kinds: list[str]


GRAPH_DAMAGE_CASES = [
    GraphDamageCase(
        name="duplicate_attributes",
        check=GraphCheck.DUPLICATE_ATTRIBUTES,
        damage=_duplicate_attribute_vertex,
        expected_violations=1,
        scoped_violations=1,
        included_kinds=["TestCar"],
        excluded_kinds=["TestPerson"],
    ),
    GraphDamageCase(
        name="duplicate_paths",
        check=GraphCheck.DUPLICATE_PATHS,
        damage=_duplicate_has_value_edge,
        expected_violations=1,
        scoped_violations=1,
        included_kinds=["TestCar"],
        excluded_kinds=["TestPerson"],
    ),
    GraphDamageCase(
        name="duplicate_relationships",
        check=GraphCheck.DUPLICATE_RELATIONSHIPS,
        damage=_duplicate_relationship_vertex,
        expected_violations=2,
        scoped_violations=1,
        included_kinds=["TestCar"],
        excluded_kinds=["CoreAccount"],
    ),
    GraphDamageCase(
        name="relationship_edge_counts",
        check=GraphCheck.RELATIONSHIP_EDGE_COUNTS,
        damage=_remove_owner_side_relationship_edge,
        expected_violations=1,
        scoped_violations=1,
        included_kinds=["TestCar"],
        excluded_kinds=["TestPerson"],
    ),
    GraphDamageCase(
        name="orphaned_active_edges",
        check=GraphCheck.ORPHANED_ACTIVE_EDGES,
        damage=_delete_attribute_edge_only,
        expected_violations=2,
        scoped_violations=2,
        included_kinds=["TestCar"],
        excluded_kinds=["TestPerson"],
    ),
    GraphDamageCase(
        name="edges_after_node_delete",
        check=GraphCheck.EDGES_AFTER_NODE_DELETE,
        damage=_add_edge_after_node_delete,
        expected_violations=1,
        scoped_violations=1,
        included_kinds=["TestCar"],
        excluded_kinds=["TestPerson"],
    ),
]


class TestVerifyGraph:
    async def test_healthy_graph_has_no_violations(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        person_john_main: Node,
        car_accord_main: Node,
    ) -> None:
        assert await collect_graph_violations(db=db) == []
        await verify_graph(db=db)

    @pytest.mark.parametrize("case", GRAPH_DAMAGE_CASES, ids=lambda case: case.name)
    async def test_damage_is_detected_and_scoped_by_kind(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        person_john_main: Node,
        car_accord_main: Node,
        case: GraphDamageCase,
    ) -> None:
        await case.damage(db, car_accord_main, person_john_main)

        unfiltered = await collect_graph_violations(db=db)
        assert [violation.check for violation in unfiltered] == [case.check] * case.expected_violations

        included = await collect_graph_violations(db=db, kinds=case.included_kinds)
        assert [violation.check for violation in included] == [case.check] * case.scoped_violations

        assert await collect_graph_violations(db=db, kinds=case.excluded_kinds) == []

    async def test_empty_kind_filter_behaves_like_no_filter(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        person_john_main: Node,
        car_accord_main: Node,
    ) -> None:
        await _duplicate_attribute_vertex(db, car_accord_main, person_john_main)

        assert await collect_graph_violations(db=db, kinds=[]) == await collect_graph_violations(db=db)

    async def test_branch_forked_after_a_delete_may_not_write_to_the_field(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        person_john_main: Node,
        car_accord_main: Node,
    ) -> None:
        """A branch inherits a delete it forked after, so writing the field there is an update to nothing."""
        await _delete_attribute_cleanly(
            db=db, node_uuid=car_accord_main.id, attr_name="name", at=Timestamp().to_string()
        )
        assert await collect_graph_violations(db=db, kinds=["TestCar"]) == []

        branch = await create_branch(db=db, branch_name="forked-after-delete")
        await _write_value_edge_on_branch(
            db=db, node_uuid=car_accord_main.id, attr_name="name", branch=branch, at=Timestamp().to_string()
        )

        violations = await collect_graph_violations(db=db, kinds=["TestCar"])
        assert [violation.check for violation in violations] == [GraphCheck.ORPHANED_ACTIVE_EDGES]

    async def test_kind_update_before_a_delete_does_not_backdate_it(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        person_john_main: Node,
        car_accord_main: Node,
    ) -> None:
        """A kind update deletes one edge to the field and opens another, and the field lives on.

        The delete that matters is the last one, so an update written between the two is not a write to a
        deleted field.
        """
        kind_update_at = Timestamp()
        await _split_node_vertex_keeping_the_field(
            db=db, node_uuid=car_accord_main.id, attr_name="name", at=kind_update_at.to_string()
        )

        value_update_at = kind_update_at.add_delta(seconds=10)
        await _update_value_on_branch(
            db=db,
            node_uuid=car_accord_main.id,
            attr_name="name",
            branch=default_branch,
            value="renamed-accord",
            at=value_update_at.to_string(),
        )

        await _delete_attribute_cleanly(
            db=db,
            node_uuid=car_accord_main.id,
            attr_name="name",
            at=value_update_at.add_delta(seconds=10).to_string(),
        )

        assert await collect_graph_violations(db=db, kinds=["TestCar"]) == []

    async def test_a_delete_on_one_branch_is_not_inherited_by_another(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        person_john_main: Node,
        car_accord_main: Node,
    ) -> None:
        """Branches are cut from the default branch, so one branch never sees another's delete."""
        deleting_branch = await create_branch(db=db, branch_name="deleting-branch")
        await _delete_attribute_on_branch(
            db=db,
            node_uuid=car_accord_main.id,
            attr_name="name",
            branch=deleting_branch,
            at=Timestamp().to_string(),
        )

        sibling_branch = await create_branch(db=db, branch_name="sibling-branch")
        await _write_value_edge_on_branch(
            db=db,
            node_uuid=car_accord_main.id,
            attr_name="name",
            branch=sibling_branch,
            at=Timestamp().to_string(),
        )

        assert await collect_graph_violations(db=db, kinds=["TestCar"]) == []

    async def test_every_check_runs_and_all_violations_are_reported(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        person_john_main: Node,
        car_accord_main: Node,
    ) -> None:
        await _duplicate_attribute_vertex(db, car_accord_main, person_john_main)
        await _remove_owner_side_relationship_edge(db, car_accord_main, person_john_main)

        with pytest.raises(GraphValidationError) as exc_info:
            await verify_graph(db=db)

        assert {violation.check for violation in exc_info.value.violations} == {
            GraphCheck.DUPLICATE_ATTRIBUTES,
            GraphCheck.RELATIONSHIP_EDGE_COUNTS,
        }
        raised_message = str(exc_info.value)
        assert GraphCheck.DUPLICATE_ATTRIBUTES.value in raised_message
        assert GraphCheck.RELATIONSHIP_EDGE_COUNTS.value in raised_message
        assert len(raised_message.splitlines()) == len(exc_info.value.violations)
