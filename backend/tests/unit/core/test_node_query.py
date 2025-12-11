from infrahub.core.branch import Branch
from infrahub.core.constants import (
    SYSTEM_USER_ID,
    InfrahubKind,
    MetadataOptions,
    RelationshipDirection,
    RelationshipHierarchyDirection,
)
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_attribute_remove import (
    NodeAttributeRemoveMigration,
    NodeAttributeRemoveMigrationQuery01,
)
from infrahub.core.migrations.schema.node_kind_update import (
    NodeKindUpdateMigration,
    NodeKindUpdateMigrationQuery01,
)
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath, SchemaPathType
from infrahub.core.query.node import (
    NodeCreateAllQuery,
    NodeDeleteQuery,
    NodeGetHierarchyQuery,
    NodeListGetAttributeQuery,
    NodeListGetInfoQuery,
    NodeListGetRelationshipsQuery,
)
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes, get_nodes
from infrahub.database import InfrahubDatabase


async def test_query_NodeCreateAllQuery(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, first_account
) -> None:
    obj = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await obj.new(db=db, name="John", height=180)
    await obj.save(db=db)

    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(
        db=db,
        _owner=first_account,
        name="camry",
        nbr_seats=5,
        is_electric=False,
        owner={"id": obj.id, "_relation__source": first_account},
    )

    query = await NodeCreateAllQuery.init(db=db, node=car, user_id="abcd")
    await query.execute(db=db)

    assert query.get_self_ids()


async def test_query_NodeCreateAllQuery_iphost(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema
) -> None:
    obj = await Node.init(db=db, schema="TestAllAttributeTypes", branch=default_branch)
    await obj.new(db=db, ipaddress="10.2.5.2/24")

    query = await NodeCreateAllQuery.init(db=db, node=obj, user_id="abcd")
    await query.execute(db=db)

    nodes = await get_nodes(db=db, label="AttributeIPHost")
    assert len(nodes) == 1
    attribute = nodes[0]

    assert attribute["value"] == "10.2.5.2/24"
    assert attribute["version"] == 4
    assert attribute["binary_address"] == "00001010000000100000010100000010"
    assert attribute["prefixlen"] == 24

    assert await count_nodes(db=db, label="AttributeIPNetwork") == 0


async def test_query_NodeCreateAllQuery_ipnetwork(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema
) -> None:
    obj = await Node.init(db=db, schema="TestAllAttributeTypes", branch=default_branch)
    await obj.new(db=db, prefix="10.2.5.0/24")

    query = await NodeCreateAllQuery.init(db=db, node=obj, user_id="abcd")
    await query.execute(db=db)

    nodes = await get_nodes(db=db, label="AttributeIPNetwork")
    assert len(nodes) == 1
    prefix = nodes[0]

    assert prefix["value"] == "10.2.5.0/24"
    assert prefix["version"] == 4
    assert prefix["binary_address"] == "00001010000000100000010100000000"
    assert prefix["prefixlen"] == 24
    # assert prefix["num_addresses"] == 256

    assert await count_nodes(db=db, label="AttributeIPHost") == 0


async def test_query_NodeListGetInfoQuery(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
) -> None:
    right_now = Timestamp()
    ids = [person_john_main.id, person_jim_main.id, person_albert_main.id]
    query = await NodeListGetInfoQuery.init(db=db, branch=branch, ids=ids)
    await query.execute(db=db)
    assert len(query.results) == 3
    assert {r.get("node_uuid") for r in query.results} == {
        person_john_main.id,
        person_jim_main.id,
        person_albert_main.id,
    }

    query_with_metadata = await NodeListGetInfoQuery.init(
        db=db, branch=branch, ids=ids, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    await query_with_metadata.execute(db=db)
    async for node in query_with_metadata.get_nodes(db=db, duplicate=False):
        assert node.node_uuid in ids
        assert node.created_at < right_now
        assert node.created_by == SYSTEM_USER_ID
        assert node.updated_at == node.created_at
        assert node.updated_by == SYSTEM_USER_ID

    query_with_metadata = await NodeListGetInfoQuery.init(
        db=db, branch=branch, branch_agnostic=True, ids=ids, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    await query_with_metadata.execute(db=db)
    async for node in query_with_metadata.get_nodes(db=db, duplicate=False):
        assert node.node_uuid in ids
        assert node.created_at < right_now
        assert node.created_by == SYSTEM_USER_ID
        assert node.updated_at == node.created_at
        assert node.updated_by == SYSTEM_USER_ID


async def test_query_NodeListGetInfoQuery_renamed(
    db: InfrahubDatabase, person_john_main, person_jim_main, person_albert_main, person_alfred_main, branch: Branch
) -> None:
    schema = registry.schema.get_schema_branch(name=branch.name)
    candidate_schema = schema.duplicate()
    person_schema = candidate_schema.get(name="TestPerson")
    candidate_schema.delete(name="TestPerson")
    person_schema.name = "NewPerson"
    person_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewPerson", schema=person_schema)
    assert person_schema.kind == "Test2NewPerson"

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestPerson"),
        new_node_schema=person_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewPerson", field_name="namespace"
        ),
    )
    query = await NodeKindUpdateMigrationQuery01.init(db=db, branch=branch, migration=migration)
    await query.execute(db=db)

    ids = [person_john_main.id, person_jim_main.id, person_albert_main.id]
    query = await NodeListGetInfoQuery.init(db=db, branch=branch, ids=ids)
    await query.execute(db=db)
    results = [node.labels async for node in query.get_nodes(db=db)]
    for result in results:
        assert sorted(result) == ["CoreNode", "Node", "Test2NewPerson"]


async def test_query_NodeListGetAttributeQuery_all_fields(db: InfrahubDatabase, base_dataset_02) -> None:
    default_branch = await registry.get_branch(db=db, branch="main")
    branch1 = await registry.get_branch(db=db, branch="branch1")

    # Query all the nodes in main but only c1 and c2 present
    # Expect 4 attributes per node(x2) = 8 attributes
    query = await NodeListGetAttributeQuery.init(db=db, ids=["c1", "c2", "c3"], branch=default_branch)
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2"]
    assert len(list(query.get_results())) == 8
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 4
    assert len(query.get_attributes_group_by_node()["c2"].attrs) == 4

    # Query all the nodes in branch1, only c1 and c3 present
    query = await NodeListGetAttributeQuery.init(db=db, ids=["c1", "c2", "c3"], branch=branch1)
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c3"]
    assert len(list(query.get_results())) == 8
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 4
    assert len(query.get_attributes_group_by_node()["c3"].attrs) == 4


async def test_query_NodeListGetAttributeQuery_with_source(
    db: InfrahubDatabase, default_branch, criticality_schema, first_account, second_account
) -> None:
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4, _source=first_account)
    await obj1.save(db=db)

    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(
        db=db,
        name="medium",
        level={"value": 3, "source": second_account.id},
        description="My desc",
        color="#333333",
        _source=first_account,
    )
    await obj2.save(db=db)

    default_branch = await registry.get_branch(db=db, branch="main")

    query = await NodeListGetAttributeQuery.init(
        db=db, ids=[obj1.id, obj2.id], branch=default_branch, include_metadata=MetadataOptions.SOURCE
    )
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == sorted([obj1.id, obj2.id])
    assert (
        query.get_attributes_group_by_node()[obj1.id].attrs["name"].node_properties["source"].uuid == first_account.id
    )
    assert (
        query.get_attributes_group_by_node()[obj2.id].attrs["level"].node_properties["source"].uuid == second_account.id
    )
    assert (
        query.get_attributes_group_by_node()[obj2.id].attrs["name"].node_properties["source"].uuid == first_account.id
    )


async def test_query_NodeListGetAttributeQuery(db: InfrahubDatabase, base_dataset_02) -> None:
    default_branch = await registry.get_branch(db=db, branch="main")
    branch1 = await registry.get_branch(db=db, branch="branch1")

    # Query all the nodes in main but only c1 and c2 present
    # Expect 2 attributes per node(x2) = 4 attributes
    query = await NodeListGetAttributeQuery.init(
        db=db, ids=["c1", "c2", "c3"], branch=default_branch, fields={"name": True, "is_electric": True}
    )
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2"]
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 2
    assert len(query.get_attributes_group_by_node()["c2"].attrs) == 2
    assert len(list(query.get_results())) == 4

    # Query all the nodes in branch1: c1 and c3 present
    query = await NodeListGetAttributeQuery.init(
        db=db, ids=["c1", "c2", "c3"], branch=branch1, fields={"nbr_seats": True}
    )
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c3"]
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 1
    assert len(query.get_attributes_group_by_node()["c3"].attrs) == 1
    assert len(list(query.get_results())) == 2

    # Query c1 in branch1
    query = await NodeListGetAttributeQuery.init(db=db, ids=["c1"], branch=branch1, fields={"nbr_seats": True})
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1"]
    assert len(list(query.get_results())) == 1

    # Query all the nodes in branch1, only c1 and c3 present
    query = await NodeListGetAttributeQuery.init(
        db=db, ids=["c1", "c2", "c3"], branch=branch1, fields={"nbr_seats": True}
    )
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c3"]
    assert len(list(query.get_results())) == 2


async def test_query_NodeListGetAttributeQuery_deleted(db: InfrahubDatabase, base_dataset_02) -> None:
    default_branch = await registry.get_branch(db=db, branch="main")
    branch1 = await registry.get_branch(db=db, branch="branch1")

    schema = registry.schema.get_schema_branch(name=branch1.name)
    car_schema = schema.get(name="TestCar")

    migration = NodeAttributeRemoveMigration(
        previous_node_schema=car_schema,
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="is_electric"),
    )
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=branch1, migration=migration)
    await query.execute(db=db)

    # Query all the nodes in main but only c1 and c2 present
    # Expect 2 attributes per node(x2) = 4 attributes
    query = await NodeListGetAttributeQuery.init(
        db=db,
        ids=["c1", "c2", "c3"],
        branch=default_branch,
    )
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c2"]

    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 4

    # Query all the nodes in branch1: c1 and c3 present
    # Expect 6 attributes because each node has 1 but c1at2 has its value and its protected flag defined both in Main and Branch1
    query = await NodeListGetAttributeQuery.init(db=db, ids=["c1", "c2", "c3"], branch=branch1)
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1", "c3"]
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 3
    assert len(query.get_attributes_group_by_node()["c3"].attrs) == 3

    # Query c1 in branch1
    # Expect 4 attributes because c1at2 has its value and its protected flag defined both in Main and Branch1
    query = await NodeListGetAttributeQuery.init(
        db=db, ids=["c1"], branch=branch1, fields={"nbr_seats": True, "is_electric": True}
    )
    await query.execute(db=db)
    assert sorted(query.get_attributes_group_by_node().keys()) == ["c1"]
    assert len(query.get_attributes_group_by_node()["c1"].attrs) == 1


async def test_query_NodeListGetRelationshipsQuery(
    db: InfrahubDatabase, default_branch: Branch, person_jack_tags_main, tag_blue_main, tag_red_main
) -> None:
    default_branch = await registry.get_branch(db=db, branch="main")
    query = await NodeListGetRelationshipsQuery.init(
        db=db,
        ids=[person_jack_tags_main.id],
        branch=default_branch,
    )
    await query.execute(db=db)
    grouped_peer_nodes = query.get_peers_group_by_node()
    assert grouped_peer_nodes.has_node(person_jack_tags_main.id)
    peer_ids = grouped_peer_nodes.get_peer_ids(
        node_id=person_jack_tags_main.id, rel_name="builtintag__testperson", direction=RelationshipDirection.INBOUND
    )
    assert peer_ids == {tag_blue_main.id, tag_red_main.id}


async def test_query_NodeListGetRelationshipsQuery_hierarchical(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data: dict[str, Node]
) -> None:
    node_ids = [value.id for value in hierarchical_location_data.values()]
    europe_id = hierarchical_location_data["europe"].id
    paris_id = hierarchical_location_data["paris"].id
    paris_r1_id = hierarchical_location_data["paris-r1"].id
    paris_r2_id = hierarchical_location_data["paris-r2"].id
    default_branch = await registry.get_branch(db=db, branch="main")
    query = await NodeListGetRelationshipsQuery.init(
        db=db,
        ids=node_ids,
        branch=default_branch,
    )
    await query.execute(db=db)
    grouped_peer_nodes = query.get_peers_group_by_node()
    assert grouped_peer_nodes.has_node(paris_id)
    child_peer_ids = grouped_peer_nodes.get_peer_ids(
        node_id=paris_id, rel_name="parent__child", direction=RelationshipDirection.INBOUND
    )
    assert child_peer_ids == {paris_r1_id, paris_r2_id}
    parent_peer_ids = grouped_peer_nodes.get_peer_ids(
        node_id=paris_id, rel_name="parent__child", direction=RelationshipDirection.OUTBOUND
    )
    assert parent_peer_ids == {europe_id}

    # check with inbound only filter
    query = await NodeListGetRelationshipsQuery.init(
        db=db,
        ids=node_ids,
        branch=default_branch,
        outbound_identifiers=[],
        inbound_identifiers=["parent__child"],
        bidirectional_identifiers=[],
    )
    await query.execute(db=db)
    grouped_peer_nodes = query.get_peers_group_by_node()
    assert grouped_peer_nodes.has_node(paris_id)
    child_peer_ids = grouped_peer_nodes.get_peer_ids(
        node_id=paris_id, rel_name="parent__child", direction=RelationshipDirection.INBOUND
    )
    assert child_peer_ids == {paris_r1_id, paris_r2_id}
    parent_peer_ids = grouped_peer_nodes.get_peer_ids(
        node_id=paris_id, rel_name="parent__child", direction=RelationshipDirection.OUTBOUND
    )
    assert not parent_peer_ids

    # check with outbound only filter
    query = await NodeListGetRelationshipsQuery.init(
        db=db,
        ids=node_ids,
        branch=default_branch,
        outbound_identifiers=["parent__child"],
        inbound_identifiers=[],
        bidirectional_identifiers=[],
    )
    await query.execute(db=db)
    grouped_peer_nodes = query.get_peers_group_by_node()
    assert grouped_peer_nodes.has_node(paris_id)
    child_peer_ids = grouped_peer_nodes.get_peer_ids(
        node_id=paris_id, rel_name="parent__child", direction=RelationshipDirection.INBOUND
    )
    assert not child_peer_ids
    parent_peer_ids = grouped_peer_nodes.get_peer_ids(
        node_id=paris_id, rel_name="parent__child", direction=RelationshipDirection.OUTBOUND
    )
    assert parent_peer_ids == {europe_id}


async def test_query_NodeListGetRelationshipsQuery_pagination_and_parallel_runtime(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema, query_limit_of_one, neo4j_runtime_parallel
):
    """
    Test all expected results are returned with pagination and parallel runtime
    """
    tags = []
    for i in range(10):
        tag = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
        await tag.new(db=db, name=f"Tag{i}", description=f"The Tag{i} tag")
        await tag.save(db=db)
        tags.append(tag)
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, firstname="Test", lastname="Person", tags=tags)
    await person.save(db=db)

    query = await NodeListGetRelationshipsQuery.init(
        db=db,
        ids=[person.id],
        branch=default_branch,
    )
    await query.execute(db=db)

    # Verify all relationships are returned
    grouped_peer_nodes = query.get_peers_group_by_node()
    assert grouped_peer_nodes.has_node(person.id)
    peer_ids = grouped_peer_nodes.get_peer_ids(
        node_id=person.id, rel_name="builtintag__testperson", direction=RelationshipDirection.INBOUND
    )
    # Verify all 10 tags are returned
    expected_tag_ids = {tag.id for tag in tags}
    assert peer_ids == expected_tag_ids
    assert len(peer_ids) == 10


async def test_query_NodeDeleteQuery(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_jack_tags_main: Node,
    tag_blue_main: Node,
) -> None:
    tags_before = await NodeManager.query(db=db, schema=InfrahubKind.TAG, branch=default_branch)

    query = await NodeDeleteQuery.init(db=db, node=tag_blue_main, branch=default_branch, user_id="abcd")
    await query.execute(db=db)

    tags_after = await NodeManager.query(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    assert len(tags_after) == len(tags_before) - 1


async def test_query_NodeGetHierarchyQuery_ancestors(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchical_location_data,
) -> None:
    node_schema = registry.schema.get(name="LocationRack", branch=default_branch)

    europe = hierarchical_location_data["europe"]
    paris = hierarchical_location_data["paris"]
    paris_r1 = hierarchical_location_data["paris-r1"]

    query = await NodeGetHierarchyQuery.init(
        db=db,
        direction=RelationshipHierarchyDirection.ANCESTORS,
        node_id=paris_r1.id,
        node_schema=node_schema,
        branch=default_branch,
    )
    await query.execute(db=db)
    assert sorted(query.get_peer_ids()) == sorted([paris.id, europe.id])


async def test_query_NodeGetHierarchyQuery_filters(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchical_location_data: dict[str, Node],
) -> None:
    node_schema = registry.schema.get(name="LocationRack", branch=default_branch)

    europe = hierarchical_location_data["europe"]

    ids_to_names = {value.id: value for _, value in hierarchical_location_data.items()}

    query = await NodeGetHierarchyQuery.init(
        db=db,
        direction=RelationshipHierarchyDirection.DESCENDANTS,
        node_id=europe.id,
        filters={"descendants__status__value": "online"},
        node_schema=node_schema,
        branch=default_branch,
    )

    await query.execute(db=db)
    descendants_ids = list(query.get_peer_ids())
    descendants_names = [ids_to_names[descendants_id].name.value for descendants_id in descendants_ids]

    assert sorted(descendants_names) == ["london", "london-r1", "paris", "paris-r1"]
