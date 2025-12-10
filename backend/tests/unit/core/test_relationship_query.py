from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    SYSTEM_USER_ID,
    MetadataOptions,
    RelationshipDirection,
    SchemaPathType,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.relationship import (
    RelationshipCountPerNodeQuery,
    RelationshipCreateQuery,
    RelationshipDeleteQuery,
    RelationshipGetByIdentifierQuery,
    RelationshipGetPeerQuery,
    RelationshipPeerData,
    RelationshipQuery,
    RelationshipUpdatePropertyQuery,
    RelData,
)
from infrahub.core.relationship import Relationship
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import get_paths_between_nodes
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import verify_no_duplicate_paths


class DummyRelationshipQuery(RelationshipQuery):
    async def query_init(self, db: InfrahubDatabase, *args, **kwargs) -> None:
        pass


@dataclass
class DatabaseRelationshipProperty:
    property_type: str
    branch: str
    status: str
    changed_at: Timestamp
    end_at: Timestamp | None
    value: Any
    property_is_end_node: bool

    def __hash__(self) -> int:
        return hash(
            "|".join((self.property_type, self.branch, self.status, self.changed_at.to_string(), str(self.value)))
        )

    def to_comparison_tuple(self) -> tuple[str, str, str, Any]:
        return (self.property_type, self.branch, self.status, self.value, self.property_is_end_node)


async def get_relationship_properties(
    db: InfrahubDatabase,
    source_uuid: str,
    destination_uuid: str,
) -> list[DatabaseRelationshipProperty]:
    query = """
    MATCH (s {uuid: $source_uuid})-[:IS_RELATED]-(r:Relationship)-[:IS_RELATED]-(d {uuid: $destination_uuid})
    WITH DISTINCT r
    MATCH (r)-[edge]-(p)
    WHERE type(edge) IN ["IS_VISIBLE", "IS_PROTECTED", "HAS_OWNER", "HAS_SOURCE"]
    RETURN r, edge, p
    """

    params = {"source_uuid": source_uuid, "destination_uuid": destination_uuid}

    records = await db.execute_query(query=query, params=params, name="get_relationship_properties")

    relationship_properties = []
    for record in records:
        neo4j_edge = record.get("edge")
        property_node = record.get("p")
        end_at_raw = neo4j_edge.get("to")
        if end_at_raw:
            end_at = Timestamp(end_at_raw)
        else:
            end_at = None
        relationship_properties.append(
            DatabaseRelationshipProperty(
                property_type=neo4j_edge.type,
                branch=neo4j_edge.get("branch"),
                status=neo4j_edge.get("status"),
                changed_at=Timestamp(neo4j_edge.get("from")),
                end_at=end_at,
                value=property_node.get("value"),
                property_is_end_node=neo4j_edge.end_node.element_id == property_node.element_id,
            )
        )
    return relationship_properties


async def test_RelationshipQuery_init(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    with pytest.raises(ValueError) as exc:
        rq = DummyRelationshipQuery()
    assert "Either source or source_id must be provided." in str(exc.value)

    with pytest.raises(ValueError) as exc:
        rq = DummyRelationshipQuery(source=person_jack_main)
    assert "rel or rel_id must be provided." in str(exc.value)

    with pytest.raises(ValueError) as exc:
        rq = DummyRelationshipQuery(source=person_jack_main, rel=Relationship)
    assert "Either an instance of Relationship or a valid schema must be provided." in str(exc.value)

    with pytest.raises(ValueError) as exc:
        rq = DummyRelationshipQuery(source=person_jack_main, rel=Relationship, schema=rel_schema)
    assert "Either an instance of Relationship or a valid branch must be provided." in str(exc.value)

    # Initialization with the Relationship class
    rq = DummyRelationshipQuery(source=person_jack_main, rel=Relationship, schema=rel_schema, branch=branch)
    assert rq.schema == rel_schema
    assert rq.branch == branch
    assert rq.source_id == person_jack_main.id
    assert rq.source == person_jack_main

    rq = DummyRelationshipQuery(source_id=person_jack_main.id, rel=Relationship, schema=rel_schema, branch=branch)
    assert rq.schema == rel_schema
    assert rq.branch == branch
    assert rq.source_id == person_jack_main.id
    assert rq.source is None

    # Initialization with an instance of Relationship
    rel = Relationship(schema=rel_schema, branch=branch, source_kind=person_jack_main.get_kind(), node=person_jack_main)
    rq = DummyRelationshipQuery(source=person_jack_main, rel=rel)
    assert rq.schema == rel_schema
    assert rq.branch == branch


async def test_query_RelationshipCreateQuery(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    query = await RelationshipCreateQuery.init(
        db=db,
        source=person_jack_main,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
        user_id="user1",
    )
    await query.execute(db=db)

    # We should have 1 path between t1 and p1
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == 1


async def test_query_RelationshipCreateQuery_updates_node_metadata(
    db: InfrahubDatabase, default_branch: Branch, tag_blue_main: Node, person_jack_main: Node
) -> None:
    """Test that RelationshipCreateQuery updates updated_at/updated_by on source and destination nodes."""
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    create_time = Timestamp()
    query = await RelationshipCreateQuery.init(
        db=db,
        source=person_jack_main,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=Relationship,
        branch=default_branch,
        at=create_time,
        user_id="test_user",
    )
    await query.execute(db=db)

    # Verify node metadata was updated using NodeManager
    nodes_by_id = await NodeManager.get_many(
        db=db,
        branch=default_branch,
        ids=[person_jack_main.id, tag_blue_main.id],
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
    )

    # Verify source node metadata was updated
    source_node = nodes_by_id[person_jack_main.id]
    assert source_node._get_created_by() == SYSTEM_USER_ID
    assert source_node._get_created_at() < create_time
    assert source_node._get_updated_by() == "test_user"
    assert source_node._get_updated_at() == create_time

    # Verify destination node metadata was updated
    dest_node = nodes_by_id[tag_blue_main.id]
    assert dest_node._get_created_by() == SYSTEM_USER_ID
    assert dest_node._get_created_at() < create_time
    assert dest_node._get_updated_by() == "test_user"
    assert dest_node._get_updated_at() == create_time


async def test_query_RelationshipCreateQuery_w_node_property(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_main: Node, first_account: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_main.db_id,
        relationships=["IS_RELATED"],
        max_length=2,
    )
    assert len(paths) == 0

    rel = Relationship(
        schema=rel_schema,
        branch=branch,
        source_kind=person_jack_main.get_kind(),
        node=person_jack_main,
        source=first_account,
        owner=first_account,
    )
    query = await RelationshipCreateQuery.init(
        db=db, branch=branch, source=person_jack_main, destination=tag_blue_main, rel=rel, user_id="user1"
    )
    await query.execute(db=db)

    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_main.db_id,
        relationships=["IS_RELATED"],
        max_length=2,
    )
    assert len(paths) == 1


async def test_query_RelationshipCreateQuery_for_node_with_migrated_kind(
    db: InfrahubDatabase,
    default_branch: Branch,
    tag_blue_main: Node,
    tag_red_main: Node,
    person_jack_main: Node,
    branch: Branch,
) -> None:
    schema = registry.schema.get_schema_branch(name=branch.name)
    person_schema = schema.get(name="TestPerson")
    person_schema.name = "GreatPerson"
    new_person_kind = "TestGreatPerson"
    assert person_schema.kind == new_person_kind
    registry.schema.set(name=new_person_kind, schema=person_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestPerson"),
        new_node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=new_person_kind, field_name="name"),
    )
    execution_result = await migration.execute(db=db, branch=branch)
    assert not execution_result.errors

    rel_schema = person_schema.get_relationship("tags")
    migrated_person_jack = await NodeManager.get_one(db=db, branch=branch, id=person_jack_main.id)
    query = await RelationshipCreateQuery.init(
        db=db,
        source=migrated_person_jack,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
        user_id="user1",
    )
    await query.execute(db=db)

    # We should have 1 path between tag_blue and migrated_person_jack
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=migrated_person_jack.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == 1

    # We should have 0 path between tag_blue and person_jack_main
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == 0
    query = await RelationshipCreateQuery.init(
        db=db,
        source=person_jack_main,
        destination=tag_red_main,
        schema=rel_schema,
        rel=Relationship,
        branch=default_branch,
        at=Timestamp(),
        user_id="user1",
    )
    await query.execute(db=db)
    # check paths between tag_red and person_jack_main
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_red_main.db_id,
        destination_id=person_jack_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == (0 if branch.name == default_branch.name else 1)

    # check paths between tag_red and migrated_person_jack
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_red_main.db_id,
        destination_id=migrated_person_jack.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == (1 if branch.name == default_branch.name else 0)

    await verify_no_duplicate_paths(db=db)


async def test_query_RelationshipDeleteQuery(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_tags_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    # We should have 2 paths between t1 and p1
    # First for the relationship, Second via the branch
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == 1

    rel_node = [node for node in paths[0][0]._nodes if "Relationship" in node.labels][0]

    rel_data = RelationshipPeerData(
        source_id=person_jack_tags_main.id,
        source_db_id=person_jack_tags_main.db_id,
        source_kind=person_jack_tags_main.get_kind(),
        branch=branch.name,
        peer_id=tag_blue_main.id,
        peer_db_id=tag_blue_main.db_id,
        peer_kind=tag_blue_main.get_kind(),
        rel_node_id=rel_node.get("uuid"),
        rel_node_db_id=rel_node.element_id,
        rels=[RelData.from_db(rel) for rel in paths[0][0]._relationships],
        properties={},
    )

    rel = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_tags_main.get_kind(), node=person_jack_tags_main
    )
    rel.load(db=db, data=rel_data)

    delete_time_1 = Timestamp()
    query = await RelationshipDeleteQuery.init(
        db=db,
        source=person_jack_tags_main,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=rel,
        branch=branch,
        source_branch=branch,
        destination_branch=branch,
        at=delete_time_1,
        user_id="user1",
    )
    await query.execute(db=db)

    # 1 path on the default branch that now has the "to" time set
    # "4" paths when deleting on branch b/c it includes all combinations of 2 real paths: 1 active on main and 1 deleted on the branch
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    if branch.is_default:
        assert len(paths) == 1
        path = paths[0]["p"]
        assert all(r.get("to") == delete_time_1.to_string() for r in path.relationships)
    else:
        assert len(paths) == 4
        for path in paths:
            for edge in path["p"].relationships:
                active_on_main = (
                    edge.get("to") is None and edge.get("status") == "active" and edge.get("branch") == "main"
                )
                deleted_on_branch = (
                    edge.get("from") == delete_time_1.to_string()
                    and edge.get("status") == "deleted"
                    and edge.get("branch") == branch.name
                )
                assert active_on_main or deleted_on_branch

    # ------------------------------------------------------------
    # Recreate the relationship to delete it again
    # ------------------------------------------------------------
    rel = Relationship(schema=rel_schema, branch=branch, source_kind=tag_blue_main.get_kind(), node=tag_blue_main)
    create_time_2 = Timestamp()
    query = await RelationshipCreateQuery.init(
        db=db,
        branch=branch,
        source=person_jack_tags_main,
        destination=tag_blue_main,
        rel=rel,
        user_id="user1",
        at=create_time_2,
    )
    await query.execute(db=db)

    # 2 paths on the default branch: deleted path from before and new created path
    # "5" paths on the branch:
    #  - 2 paths for original relationship: 1 active on main and 1 deleted on the branch, for 4 permutations
    #  - 1 path for new relationship on branch
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    if branch.is_default:
        assert len(paths) == 2
        for path in paths:
            is_deleted = all(r.get("to") == delete_time_1.to_string() for r in path["p"].relationships)
            is_active = all(
                r.get("to") is None and r.get("from") == create_time_2.to_string() for r in path["p"].relationships
            )
            assert is_deleted or is_active
    else:
        assert len(paths) == 5
        for path in paths:
            for edge in path["p"].relationships:
                active_on_main = (
                    edge.get("to") is None and edge.get("status") == "active" and edge.get("branch") == "main"
                )
                deleted_on_branch = (
                    edge.get("from") == delete_time_1.to_string()
                    and edge.get("status") == "deleted"
                    and edge.get("branch") == branch.name
                )
                active_on_branch = (
                    edge.get("from") == create_time_2.to_string()
                    and edge.get("to") is None
                    and edge.get("status") == "active"
                    and edge.get("branch") == branch.name
                )
                assert active_on_main or deleted_on_branch or active_on_branch

    def get_active_path_and_rel(all_paths, previous_rel: str):
        for path in all_paths:
            for node in path[0]._nodes:
                if "Relationship" in node.labels and node.get("uuid") != previous_rel:
                    return path, node

        pytest.fail(reason="Unable to find active path and relationship")

    active_path, latest_rel_node = get_active_path_and_rel(all_paths=paths, previous_rel=rel_node.get("uuid"))

    rel_data = RelationshipPeerData(
        source_id=person_jack_tags_main.id,
        source_db_id=person_jack_tags_main.db_id,
        source_kind=person_jack_tags_main.get_kind(),
        branch=branch.name,
        peer_id=tag_blue_main.id,
        peer_kind=tag_blue_main.get_kind(),
        peer_db_id=tag_blue_main.db_id,
        rel_node_id=latest_rel_node.get("uuid"),
        rel_node_db_id=latest_rel_node.element_id,
        rels=[RelData.from_db(rel) for rel in active_path[0]._relationships],
        properties={},
    )

    rel = Relationship(
        schema=rel_schema, branch=branch, source_kind=person_jack_tags_main.get_kind(), node=person_jack_tags_main
    )
    rel.load(db=db, data=rel_data)

    delete_time_2 = Timestamp()
    query = await RelationshipDeleteQuery.init(
        db=db,
        source=person_jack_tags_main,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=rel,
        branch=branch,
        source_branch=branch,
        destination_branch=branch,
        at=delete_time_2,
        user_id="user1",
    )
    await query.execute(db=db)

    # 2 paths on default branch: original deleted and the one we just deleted
    # "5" paths on the branch:
    #  - 2 paths for original relationship: 1 active on main and 1 deleted on the branch, for 4 permutations
    #  - 1 path for create and delete of new relationship on branch
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    if branch.is_default:
        assert len(paths) == 2
        for path in paths:
            is_deleted_1 = all(r.get("to") == delete_time_1.to_string() for r in path["p"].relationships)
            is_deleted_2 = all(
                r.get("from") == create_time_2.to_string() and r.get("to") == delete_time_2.to_string()
                for r in path["p"].relationships
            )
            assert is_deleted_1 or is_deleted_2
    else:
        assert len(paths) == 5
        for path in paths:
            for edge in path["p"].relationships:
                active_on_main = (
                    edge.get("to") is None and edge.get("status") == "active" and edge.get("branch") == "main"
                )
                deleted_on_branch = (
                    edge.get("from") == delete_time_1.to_string()
                    and edge.get("status") == "deleted"
                    and edge.get("branch") == branch.name
                )
                deleted_on_branch_2 = (
                    edge.get("from") == create_time_2.to_string()
                    and edge.get("to") == delete_time_2.to_string()
                    and edge.get("status") == "active"
                    and edge.get("branch") == branch.name
                )
                assert active_on_main or deleted_on_branch or deleted_on_branch_2


async def test_query_RelationshipDeleteQuery_updates_node_metadata(
    db: InfrahubDatabase, default_branch: Branch, tag_blue_main: Node, person_jack_tags_main: Node
) -> None:
    """Test that RelationshipDeleteQuery updates updated_at/updated_by on source and destination nodes."""
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    jack_main = await NodeManager.get_one(db=db, id=person_jack_tags_main.id)
    tags_rels = await jack_main.tags.get(db=db)
    blue_tag_rel = [t for t in tags_rels if t.peer_id == tag_blue_main.id][0]

    delete_time = Timestamp()
    query = await RelationshipDeleteQuery.init(
        db=db,
        source=person_jack_tags_main,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=blue_tag_rel,
        branch=default_branch,
        source_branch=default_branch,
        destination_branch=default_branch,
        at=delete_time,
        user_id="delete_user",
    )
    await query.execute(db=db)

    # Verify node metadata was updated using NodeManager
    nodes_by_id = await NodeManager.get_many(
        db=db,
        branch=default_branch,
        ids=[person_jack_tags_main.id, tag_blue_main.id],
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
    )

    # Verify source node metadata was updated
    source_node = nodes_by_id[person_jack_tags_main.id]
    assert source_node._get_created_by() == SYSTEM_USER_ID
    assert source_node._get_created_at() < delete_time
    assert source_node._get_updated_by() == "delete_user"
    assert source_node._get_updated_at() == delete_time

    # Verify destination node metadata was updated
    dest_node = nodes_by_id[tag_blue_main.id]
    assert dest_node._get_created_by() == SYSTEM_USER_ID
    assert dest_node._get_created_at() < delete_time
    assert dest_node._get_updated_by() == "delete_user"
    assert dest_node._get_updated_at() == delete_time


async def test_query_RelationshipDeleteQuery_on_migrated_kind_node(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_tags_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")
    paths = await get_paths_between_nodes(
        db=db,
        source_id=tag_blue_main.db_id,
        destination_id=person_jack_tags_main.db_id,
        max_length=2,
        relationships=["IS_RELATED"],
    )
    assert len(paths) == 1

    # migrate person kind
    person_schema.name = "NewPerson"
    person_schema.namespace = "Test2"
    assert person_schema.kind == "Test2NewPerson"
    registry.schema.set(name="Test2NewPerson", schema=person_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=registry.schema.get(name="TestPerson", branch=branch),
        new_node_schema=person_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewPerson", field_name="namespace"
        ),
    )
    execution_result = await migration.execute(db=db, branch=branch)
    assert not execution_result.errors

    migrated_jack = await NodeManager.get_one(db=db, branch=branch, id=person_jack_tags_main.id)
    tag_rels = await migrated_jack.tags.get_relationships(db=db)
    assert len(tag_rels) == 2
    blue_tag_rels = [tag_rel for tag_rel in tag_rels if tag_rel.peer_id == tag_blue_main.id]
    assert len(blue_tag_rels) == 1
    blue_tag_rel = blue_tag_rels[0]

    query = await RelationshipDeleteQuery.init(
        db=db,
        source=migrated_jack,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=blue_tag_rel,
        branch=branch,
        source_branch=branch,
        destination_branch=branch,
        at=Timestamp(),
        user_id="user1",
    )
    await query.execute(db=db)
    await verify_no_duplicate_paths(db=db)


async def test_query_RelationshipUpdatePropertyQuery_updates_node_metadata(
    db: InfrahubDatabase, default_branch: Branch, tag_blue_main: Node, person_jack_tags_main: Node
) -> None:
    """Test that RelationshipUpdatePropertyQuery updates updated_at/updated_by on peer nodes."""
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    jack_main = await NodeManager.get_one(db=db, id=person_jack_tags_main.id)
    tags_rels = await jack_main.tags.get(db=db)
    blue_tag_rel = [t for t in tags_rels if t.peer_id == tag_blue_main.id][0]

    update_time = Timestamp()
    query = await RelationshipUpdatePropertyQuery.init(
        db=db,
        branch=default_branch,
        source=person_jack_tags_main,
        destination=tag_blue_main,
        schema=rel_schema,
        rel=blue_tag_rel,
        at=update_time,
        user_id="update_user",
        flag_properties_to_update={"is_protected": True},
        node_properties_to_update={},
    )
    await query.execute(db=db)

    # Verify node metadata was updated using NodeManager
    nodes_by_id = await NodeManager.get_many(
        db=db,
        branch=default_branch,
        ids=[person_jack_tags_main.id, tag_blue_main.id],
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
    )

    # Verify source node metadata was updated
    source_node = nodes_by_id[person_jack_tags_main.id]
    assert source_node._get_created_by() == SYSTEM_USER_ID
    assert source_node._get_created_at() < update_time
    assert source_node._get_updated_by() == "update_user"
    assert source_node._get_updated_at() == update_time

    # Verify destination node metadata was updated
    dest_node = nodes_by_id[tag_blue_main.id]
    assert dest_node._get_created_by() == SYSTEM_USER_ID
    assert dest_node._get_created_at() < update_time
    assert dest_node._get_updated_by() == "update_user"
    assert dest_node._get_updated_at() == update_time


async def test_relationship_delete_peer(db: InfrahubDatabase, default_branch, tag_blue_main: Node) -> None:
    person = await Node.init(db=db, branch=default_branch, schema="TestPerson")
    await person.new(db=db, firstname="Kara", lastname="Thrace", tags=[tag_blue_main])
    create_before = Timestamp()
    await person.save(db=db)
    create_after = Timestamp()
    branch = await create_branch(db=db, branch_name="branch")
    person_branch = await NodeManager.get_one(db=db, branch=branch, id=person.id)
    await person_branch.tags.delete(db=db)
    update_after = Timestamp()

    database_relationships = await get_relationship_properties(
        db=db, source_uuid=person.get_id(), destination_uuid=tag_blue_main.get_id()
    )

    expected_relationships = {
        ("IS_VISIBLE", default_branch.name, "active", True, True),
        ("IS_VISIBLE", branch.name, "deleted", True, True),
        ("IS_PROTECTED", default_branch.name, "active", False, True),
        ("IS_PROTECTED", branch.name, "deleted", False, True),
    }
    assert len(database_relationships) == 4
    assert {dr.to_comparison_tuple() for dr in database_relationships} == expected_relationships
    for database_rel in database_relationships:
        if database_rel.status == "active":
            assert create_before < database_rel.changed_at < create_after
        elif database_rel.status == "deleted":
            assert create_after < database_rel.changed_at < update_after


async def test_branch_delete_with_updated_main_relationship(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_jack_primary_tag_main: Node,
    tag_blue_main: Node,
    tag_black_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch2")
    before_main_update = Timestamp()
    person_main = await NodeManager.get_one(db=db, id=person_jack_primary_tag_main.id)
    await person_main.primary_tag.update(db=db, data={"id": tag_black_main.id, "_relation__is_protected": True})
    await person_main.save(db=db)
    after_main_update = Timestamp()
    person_branch = await NodeManager.get_one(db=db, branch=branch, id=person_jack_primary_tag_main.id)
    await person_branch.delete(db=db)
    after_branch_delete = Timestamp()

    # test edges for tag blue relationship
    database_relationships_tag_blue = await get_relationship_properties(
        db=db, source_uuid=person_jack_primary_tag_main.get_id(), destination_uuid=tag_blue_main.get_id()
    )
    expected_relationships_tag_blue = {
        ("IS_VISIBLE", default_branch.name, "active", True, True),
        ("IS_VISIBLE", branch.name, "deleted", True, True),
        ("IS_PROTECTED", default_branch.name, "active", False, True),
        ("IS_PROTECTED", branch.name, "deleted", False, True),
    }
    assert len(database_relationships_tag_blue) == 4
    assert {dr.to_comparison_tuple() for dr in database_relationships_tag_blue} == expected_relationships_tag_blue
    for database_rel in database_relationships_tag_blue:
        if database_rel.status == "active":
            assert database_rel.changed_at < before_main_update < database_rel.end_at < after_main_update
        elif database_rel.status == "deleted":
            assert not database_rel.end_at
            assert after_main_update < database_rel.changed_at < after_branch_delete

    # test edges for tag black relationship
    database_relationships_tag_black = await get_relationship_properties(
        db=db, source_uuid=person_jack_primary_tag_main.get_id(), destination_uuid=tag_black_main.get_id()
    )
    expected_relationships_tag_black = {
        ("IS_VISIBLE", default_branch.name, "active", True, True),
        ("IS_PROTECTED", default_branch.name, "active", True, True),
    }
    assert len(database_relationships_tag_black) == 2
    assert {dr.to_comparison_tuple() for dr in database_relationships_tag_black} == expected_relationships_tag_black
    for database_rel in database_relationships_tag_black:
        assert not database_rel.end_at
        assert before_main_update < database_rel.changed_at < after_main_update


async def test_main_delete_with_updated_branch_relationship(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_jack_primary_tag_main: Node,
    tag_blue_main: Node,
    tag_black_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch2")
    before_branch_update = Timestamp()
    person_branch = await NodeManager.get_one(db=db, branch=branch, id=person_jack_primary_tag_main.id)
    await person_branch.primary_tag.update(db=db, data={"id": tag_black_main.id, "_relation__is_protected": True})
    await person_branch.save(db=db)
    after_branch_update = Timestamp()
    person_main = await NodeManager.get_one(db=db, id=person_jack_primary_tag_main.id)
    await person_main.delete(db=db)
    after_main_delete = Timestamp()

    # test edges for tag blue relationship
    database_relationships_tag_blue = await get_relationship_properties(
        db=db, source_uuid=person_jack_primary_tag_main.get_id(), destination_uuid=tag_blue_main.get_id()
    )
    expected_relationships_tag_blue = {
        ("IS_VISIBLE", default_branch.name, "active", True, True),
        ("IS_VISIBLE", default_branch.name, "deleted", True, True),
        ("IS_VISIBLE", branch.name, "deleted", True, True),
        ("IS_PROTECTED", default_branch.name, "active", False, True),
        ("IS_PROTECTED", default_branch.name, "deleted", False, True),
        ("IS_PROTECTED", branch.name, "deleted", False, True),
    }
    assert len(database_relationships_tag_blue) == 6
    assert {dr.to_comparison_tuple() for dr in database_relationships_tag_blue} == expected_relationships_tag_blue
    for database_rel in database_relationships_tag_blue:
        if database_rel.status == "active" and database_rel.branch == default_branch.name:
            assert (
                database_rel.changed_at
                < before_branch_update
                < after_branch_update
                < database_rel.end_at
                < after_main_delete
            )
        elif database_rel.status == "deleted" and database_rel.branch == default_branch.name:
            assert not database_rel.end_at
            assert after_branch_update < database_rel.changed_at < after_main_delete
        elif database_rel.status == "deleted" and database_rel.branch == branch.name:
            assert not database_rel.end_at
            assert before_branch_update < database_rel.changed_at < after_branch_update

    # test edges for tag black relationship
    database_relationships_tag_black = await get_relationship_properties(
        db=db, source_uuid=person_jack_primary_tag_main.get_id(), destination_uuid=tag_black_main.get_id()
    )
    expected_relationships_tag_black = {
        ("IS_VISIBLE", branch.name, "active", True, True),
        ("IS_PROTECTED", branch.name, "active", True, True),
    }
    assert len(database_relationships_tag_black) == 2
    assert {dr.to_comparison_tuple() for dr in database_relationships_tag_black} == expected_relationships_tag_black
    for database_rel in database_relationships_tag_black:
        assert not database_rel.end_at
        assert before_branch_update < database_rel.changed_at < after_branch_update


async def test_relationship_update_with_delete_peer(
    db: InfrahubDatabase, default_branch, tag_blue_main: Node, tag_red_main: Node
) -> None:
    person = await Node.init(db=db, branch=default_branch, schema="TestPerson")
    await person.new(db=db, firstname="Kara", lastname="Thrace", tags=[tag_blue_main])
    create_before = Timestamp()
    await person.save(db=db)
    create_after = Timestamp()
    branch = await create_branch(db=db, branch_name="branch")
    person_branch = await NodeManager.get_one(db=db, branch=branch, id=person.id)
    await person_branch.tags.update(db=db, data=[tag_red_main])
    update_before = Timestamp()
    await person_branch.save(db=db)
    update_after = Timestamp()

    database_relationships = await get_relationship_properties(
        db=db, source_uuid=person.get_id(), destination_uuid=tag_blue_main.get_id()
    )
    expected_relationships = {
        ("IS_VISIBLE", default_branch.name, "active", True, True),
        ("IS_VISIBLE", branch.name, "deleted", True, True),
        ("IS_PROTECTED", default_branch.name, "active", False, True),
        ("IS_PROTECTED", branch.name, "deleted", False, True),
    }
    assert len(database_relationships) == 4
    assert {dr.to_comparison_tuple() for dr in database_relationships} == expected_relationships
    for database_rel in database_relationships:
        if database_rel.status == "active":
            assert create_before < database_rel.changed_at < create_after
        elif database_rel.status == "deleted":
            assert update_before < database_rel.changed_at < update_after


async def test_query_RelationshipGetPeerQuery(
    db: InfrahubDatabase, tag_blue_main: Node, person_jack_tags_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("tags")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_jack_tags_main.id],
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
        include_metadata=MetadataOptions.IS_PROTECTED | MetadataOptions.IS_VISIBLE,
    )
    await query.execute(db=db)

    peers = list(query.get_peers())
    assert len(peers) == 2
    assert len(peers[0].rels) == 2
    assert isinstance(peers[0].rel_node_db_id, str)
    assert isinstance(peers[0].rel_node_id, str)
    assert set(peers[0].properties.keys()) == {"is_visible", "is_protected"}
    assert peers[0].properties["is_visible"].value is True
    assert peers[0].properties["is_protected"].value is False
    assert peers[0].properties["is_protected"].prop_db_id == peers[1].properties["is_protected"].prop_db_id
    assert isinstance(peers[0].properties["is_protected"].prop_db_id, str)
    assert isinstance(peers[0].properties["is_protected"].rel.db_id, str)
    assert isinstance(peers[0].properties["is_protected"].prop_db_id, str)


async def test_query_RelationshipGetPeerQuery_with_filter(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        filters={"cars__is_electric__value": True},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)

    assert query.get_peer_ids() == sorted([car_volt_main.id, car_prius_main.id])


async def test_query_RelationshipGetPeerQuery_with_id(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        filters={"cars__ids": [car_accord_main.id]},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)
    assert query.get_peer_ids() == sorted([car_accord_main.id])


async def test_query_RelationshipGetPeerQuery_with_ids(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        filters={"cars__ids": [car_accord_main.id, car_prius_main.id]},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)
    assert query.get_peer_ids() == sorted([car_prius_main.id, car_accord_main.id])


async def test_query_RelationshipGetPeerQuery_with_sort(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
) -> None:
    car_schema = registry.schema.get(name="TestCar", branch=branch)
    car_schema.order_by = ["name__value"]
    registry.schema.set(name="TestCar", branch=branch.name, schema=car_schema)

    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)

    assert query.get_peer_ids() == [car_accord_main.id, car_prius_main.id, car_volt_main.id]


async def test_query_RelationshipGetPeerQuery_deleted_node(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
) -> None:
    node = await NodeManager.get_one(id=car_volt_main.id, db=db, branch=branch)
    await node.delete(db=db)

    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)
    assert query.get_peer_ids() == sorted([car_accord_main.id, car_prius_main.id])


async def test_query_RelationshipGetPeerQuery_with_multiple_filter(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        filters={"cars__is_electric__value": True, "cars__nbr_seats__value": 4},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)

    assert query.get_peer_ids() == [car_volt_main.id]


async def test_query_RelationshipGetPeerQuery_with_migrated_kind(
    db: InfrahubDatabase,
    person_john_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
) -> None:
    person_schema = registry.schema.get_node_schema(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    # migrate person kind
    person_schema.name = "NewPerson"
    person_schema.namespace = "Test2"
    assert person_schema.kind == "Test2NewPerson"
    registry.schema.set(name="Test2NewPerson", schema=person_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=registry.schema.get_node_schema(name="TestPerson", branch=branch),
        new_node_schema=person_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewPerson", field_name="namespace"
        ),
    )
    execution_result = await migration.execute(db=db, branch=branch)
    assert not execution_result.errors

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[person_john_main.id],
        schema=rel_schema,
        filters={"cars__is_electric__value": True, "cars__nbr_seats__value": 4},
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
    )

    await query.execute(db=db)

    assert query.get_peer_ids() == [car_volt_main.id]


# TODO: update to work
async def test_query_RelationshipDeleteQuery_on_migrated_kind_node_2(
    db: InfrahubDatabase, tag_blue_main: Node, tag_red_main: Node, person_jack_tags_main: Node, branch: Branch
) -> None:
    person_schema = registry.schema.get(name="TestPerson", branch=branch)
    rel_schema = person_schema.get_relationship("tags")

    # migrate person kind
    person_schema.name = "NewPerson"
    person_schema.namespace = "Test2"
    assert person_schema.kind == "Test2NewPerson"
    registry.schema.set(name="Test2NewPerson", schema=person_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=registry.schema.get(name="TestPerson", branch=branch),
        new_node_schema=person_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewPerson", field_name="namespace"
        ),
    )
    execution_result = await migration.execute(db=db, branch=branch)
    assert not execution_result.errors

    migrated_jack = await NodeManager.get_one(db=db, branch=branch, id=person_jack_tags_main.id)
    # Query the existing relationship in RelationshipPeerData format
    query1 = await RelationshipGetPeerQuery.init(
        db=db,
        source=migrated_jack,
        schema=rel_schema,
        rel=Relationship(schema=rel_schema, branch=branch, source_kind=migrated_jack.get_kind(), node=migrated_jack),
    )
    await query1.execute(db=db)
    peers_database: dict[str, RelationshipPeerData] = {peer.peer_id: peer for peer in query1.get_peers()}

    # Delete the relationship
    query2 = await RelationshipDeleteQuery.init(
        db=db,
        branch=branch,
        source=migrated_jack,
        destination=tag_blue_main,
        schema=rel_schema,
        rel_id=peers_database[tag_blue_main.id].rel_node_id,
        source_branch=branch,
        destination_branch=branch,
        user_id="user1",
    )
    await query2.execute(db=db)
    await verify_no_duplicate_paths(db=db)

    # migrate tag kind
    tag_schema = registry.schema.get("BuiltinTag", branch=branch)
    tag_schema.name = "NewTag"
    tag_schema.namespace = "Builtin2"
    assert tag_schema.kind == "Builtin2NewTag"
    registry.schema.set(name="Builtin2NewTag", schema=tag_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=registry.schema.get(name="BuiltinTag", branch=branch),
        new_node_schema=tag_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind="Builtin2NewTag", field_name="namespace"
        ),
    )
    execution_result = await migration.execute(db=db, branch=branch)
    assert not execution_result.errors

    # delete other tag relationship
    rel_schema.peer = "Builtin2NewTag"
    migrated_jack = await NodeManager.get_one(db=db, branch=branch, id=person_jack_tags_main.id)
    # Query the existing relationship in RelationshipPeerData format
    query1 = await RelationshipGetPeerQuery.init(
        db=db,
        source=migrated_jack,
        schema=rel_schema,
        rel=Relationship(schema=rel_schema, branch=branch, source_kind=migrated_jack.get_kind(), node=migrated_jack),
    )
    await query1.execute(db=db)
    peers_database: dict[str, RelationshipPeerData] = {peer.peer_id: peer for peer in query1.get_peers()}

    # Delete the relationship
    query2 = await RelationshipDeleteQuery.init(
        db=db,
        branch=branch,
        source=migrated_jack,
        destination_id=tag_red_main.id,
        schema=rel_schema,
        rel_id=peers_database[tag_red_main.id].rel_node_id,
        source_branch=branch,
        destination_branch=branch,
        user_id="user1",
    )
    await query2.execute(db=db)
    await verify_no_duplicate_paths(db=db)


async def test_query_RelationshipCountPerNodeQuery(
    db: InfrahubDatabase,
    person_john_main,
    person_jane_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
) -> None:
    person_schema = registry.schema.get(name="TestPerson")
    rel_schema = person_schema.get_relationship("cars")

    albert = await Node.init(db=db, schema="TestPerson", branch=branch)
    await albert.new(db=db, name="Albert", height=120)
    await albert.save(db=db)

    peer_ids = [person_john_main.id, person_jane_main.id, albert.id]

    query = await RelationshipCountPerNodeQuery.init(
        db=db,
        node_ids=peer_ids,
        identifier=rel_schema.identifier,
        direction=RelationshipDirection.INBOUND,
        branch=branch,
        at=Timestamp(),
    )
    await query.execute(db=db)
    count_per_peer = await query.get_count_per_peer()
    assert count_per_peer == {
        person_john_main.id: 3,
        person_jane_main.id: 2,
        albert.id: 0,
    }

    # Revert the direction to ensure this is working as expected
    query = await RelationshipCountPerNodeQuery.init(
        db=db,
        node_ids=peer_ids,
        identifier=rel_schema.identifier,
        direction=RelationshipDirection.OUTBOUND,
        branch=branch,
        at=Timestamp(),
    )
    await query.execute(db=db)
    count_per_peer = await query.get_count_per_peer()
    assert count_per_peer == {
        person_john_main.id: 0,
        person_jane_main.id: 0,
        albert.id: 0,
    }


async def test_query_RelationshipGetByIdentifierQuery(
    db: InfrahubDatabase,
    person_john_main,
    person_jane_main,
    car_accord_main,
    car_camry_main,
    car_volt_main,
    car_prius_main,
    car_yaris_main,
    branch: Branch,
) -> None:
    with pytest.raises(ValueError) as exc:
        query = await RelationshipGetByIdentifierQuery.init(
            db=db, branch=branch, identifiers=[], excluded_namespaces=[]
        )
    assert "identifiers or full_identifiers is required" in str(exc.value)

    query = await RelationshipGetByIdentifierQuery.init(
        db=db, branch=branch, identifiers=["testcar__testperson"], excluded_namespaces=[]
    )
    await query.execute(db=db)
    assert await query.count(db=db) == 5

    # test owner update on branch
    branch_yaris = await NodeManager.get_one(db=db, branch=branch, id=car_yaris_main.id)
    await branch_yaris.owner.update(db=db, data=person_jane_main)
    await branch_yaris.save(db=db)
    query = await RelationshipGetByIdentifierQuery.init(
        db=db, branch=branch, identifiers=["testcar__testperson"], excluded_namespaces=[]
    )
    await query.execute(db=db)
    assert await query.count(db=db) == 5

    # test delete
    branch_prius = await NodeManager.get_one(db=db, branch=branch, id=car_prius_main.id)
    await branch_prius.delete(db=db)
    query = await RelationshipGetByIdentifierQuery.init(
        db=db, branch=branch, identifiers=["testcar__testperson"], excluded_namespaces=[]
    )
    await query.execute(db=db)
    assert await query.count(db=db) == 4


async def test_query_RelationshipGetPeerQuery_branch_agnostic(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
) -> None:
    """Test that RelationshipGetPeerQuery works correctly with branch_agnostic=True"""
    # Create a new branch
    branch = await create_branch(branch_name="test_agnostic_branch", db=db)

    branch_accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await branch_accord.owner.update(db=db, data=person_jane_main.id)
    before_branch_update = Timestamp()
    await branch_accord.save(db=db, user_id="user1")
    after_branch_update = Timestamp()

    person_schema = registry.schema.get(name="TestCar", branch=branch)
    rel_schema = person_schema.get_relationship("owner")

    # validate query on branch gets correct times
    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[car_accord_main.id],
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        at=Timestamp(),
        include_metadata=MetadataOptions.IS_PROTECTED | MetadataOptions.IS_VISIBLE | MetadataOptions.USER_TIMESTAMPS,
    )
    await query.execute(db=db)

    # validate the peer timestamp metadata
    peer_by_id_map = {peer.peer_id: peer for peer in query.get_peers()}
    assert set(peer_by_id_map.keys()) == {person_jane_main.id}
    jane_peer = peer_by_id_map[person_jane_main.id]
    assert before_branch_update < jane_peer.created_at < after_branch_update
    assert before_branch_update < jane_peer.updated_at < after_branch_update
    assert jane_peer.created_by == "user1"
    assert jane_peer.updated_by == "user1"

    # validate the query on the default branch
    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[car_accord_main.id],
        schema=rel_schema,
        rel=Relationship,
        branch=default_branch,
        at=Timestamp(),
        include_metadata=MetadataOptions.IS_PROTECTED | MetadataOptions.IS_VISIBLE | MetadataOptions.USER_TIMESTAMPS,
    )
    await query.execute(db=db)

    # validate the peer timestamp metadata
    peer_by_id_map = {peer.peer_id: peer for peer in query.get_peers()}
    assert set(peer_by_id_map.keys()) == {person_john_main.id}
    john_peer = peer_by_id_map[person_john_main.id]
    assert john_peer.created_at < before_branch_update
    assert john_peer.updated_at < before_branch_update
    assert john_peer.created_by == SYSTEM_USER_ID
    assert john_peer.updated_by == SYSTEM_USER_ID

    # validate query when branch-agnostic gets correct times
    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=[car_accord_main.id],
        schema=rel_schema,
        rel=Relationship,
        branch=branch,
        branch_agnostic=True,
        at=Timestamp(),
        include_metadata=MetadataOptions.IS_PROTECTED | MetadataOptions.IS_VISIBLE | MetadataOptions.USER_TIMESTAMPS,
    )
    await query.execute(db=db)

    # validate the peer timestamp metadata
    # john is not included because he is deleted on a branch
    peer_by_id_map = {peer.peer_id: peer for peer in query.get_peers()}
    assert set(peer_by_id_map.keys()) == {person_jane_main.id}
    jane_peer = peer_by_id_map[person_jane_main.id]
    assert before_branch_update < jane_peer.created_at < after_branch_update
    assert before_branch_update < jane_peer.updated_at < after_branch_update
    assert jane_peer.created_by == "user1"
    assert jane_peer.updated_by == "user1"
