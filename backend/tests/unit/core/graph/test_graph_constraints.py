from infrahub.core.graph.constraints import (
    ConstraintInfo,
    ConstraintManager,
    ConstraintNodeMemgraph,
    ConstraintNodeNeo4j,
    ConstraintRelNeo4j,
    GraphPropertyType,
)
from infrahub.core.graph.schema import GRAPH_SCHEMA
from infrahub.database import DatabaseType, InfrahubDatabase


def test_item_node_neo4j():
    item = ConstraintNodeNeo4j(item_name="node", item_label="CoreNode", property="uuid", type="STRING")
    assert item.name_main == "node_node_uuid_type"
    assert item.name_exist == "node_node_uuid_exist"
    assert (
        item.get_query_exist_add()
        == "CREATE CONSTRAINT node_node_uuid_exist IF NOT EXISTS FOR (n:CoreNode) REQUIRE n.uuid IS NOT NULL"
    )
    assert (
        item.get_query_main_add()
        == "CREATE CONSTRAINT node_node_uuid_type IF NOT EXISTS FOR (n:CoreNode) REQUIRE n.uuid IS :: STRING"
    )
    assert item.get_query_exist_drop() == "DROP CONSTRAINT node_node_uuid_exist IF EXISTS"
    assert item.get_query_main_drop() == "DROP CONSTRAINT node_node_uuid_type IF EXISTS"


def test_item_rel_neo4j():
    item = ConstraintRelNeo4j(item_name="attr_value", item_label="HAS_VALUE", property="from", type="STRING")
    assert item.name_main == "rel_attr_value_from_type"
    assert item.name_exist == "rel_attr_value_from_exist"
    assert (
        item.get_query_exist_add()
        == "CREATE CONSTRAINT rel_attr_value_from_exist IF NOT EXISTS FOR ()-[r:HAS_VALUE]-() REQUIRE r.from IS NOT NULL"
    )
    assert (
        item.get_query_main_add()
        == "CREATE CONSTRAINT rel_attr_value_from_type IF NOT EXISTS FOR ()-[r:HAS_VALUE]-() REQUIRE r.from IS :: STRING"
    )
    assert item.get_query_exist_drop() == "DROP CONSTRAINT rel_attr_value_from_exist IF EXISTS"
    assert item.get_query_main_drop() == "DROP CONSTRAINT rel_attr_value_from_type IF EXISTS"


def test_item_node_memgraph():
    item = ConstraintNodeMemgraph(item_name="node", item_label="CoreNode", property="uuid", type="STRING")
    assert item.get_query_exist_add() == "CREATE CONSTRAINT ON (n:CoreNode) ASSERT EXISTS (n.uuid)"
    assert item.get_query_exist_drop() == "DROP CONSTRAINT ON (n:CoreNode) ASSERT EXISTS (n.uuid)"


def test_constraint_manager_from_graph_schema(db: InfrahubDatabase):
    gm = ConstraintManager.from_graph_schema(db=db, schema=GRAPH_SCHEMA)

    if db.db_type == DatabaseType.NEO4J:
        assert gm.nodes == [
            ConstraintNodeNeo4j(
                item_name="node", item_label="Node", property="kind", type=GraphPropertyType.STRING, mandatory=True
            ),
            ConstraintNodeNeo4j(
                item_name="node", item_label="Node", property="namespace", type=GraphPropertyType.STRING, mandatory=True
            ),
            ConstraintNodeNeo4j(
                item_name="node", item_label="Node", property="uuid", type=GraphPropertyType.STRING, mandatory=True
            ),
            ConstraintNodeNeo4j(
                item_name="relationship",
                item_label="Relationship",
                property="branch",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeNeo4j(
                item_name="relationship",
                item_label="Relationship",
                property="branch_level",
                type=GraphPropertyType.INTEGER,
                mandatory=True,
            ),
            ConstraintNodeNeo4j(
                item_name="relationship",
                item_label="Relationship",
                property="from",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeNeo4j(
                item_name="relationship",
                item_label="Relationship",
                property="to",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeNeo4j(
                item_name="relationship",
                item_label="Relationship",
                property="hierarchy",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeNeo4j(
                item_name="attribute",
                item_label="Attribute",
                property="name",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeNeo4j(
                item_name="attribute",
                item_label="Attribute",
                property="type",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeNeo4j(
                item_name="attribute",
                item_label="Attribute",
                property="uuid",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeNeo4j(
                item_name="attributevalue",
                item_label="AttributeValue",
                property="type",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeNeo4j(
                item_name="boolean",
                item_label="Boolean",
                property="value",
                type=GraphPropertyType.BOOLEAN,
                mandatory=True,
            ),
        ]

    elif db.db_type == DatabaseType.MEMGRAPH:
        assert gm.nodes == [
            ConstraintNodeMemgraph(
                item_name="node", item_label="Node", property="kind", type=GraphPropertyType.STRING, mandatory=True
            ),
            ConstraintNodeMemgraph(
                item_name="node", item_label="Node", property="namespace", type=GraphPropertyType.STRING, mandatory=True
            ),
            ConstraintNodeMemgraph(
                item_name="node", item_label="Node", property="uuid", type=GraphPropertyType.STRING, mandatory=True
            ),
            ConstraintNodeMemgraph(
                item_name="relationship",
                item_label="Relationship",
                property="branch",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeMemgraph(
                item_name="relationship",
                item_label="Relationship",
                property="branch_level",
                type=GraphPropertyType.INTEGER,
                mandatory=True,
            ),
            ConstraintNodeMemgraph(
                item_name="relationship",
                item_label="Relationship",
                property="from",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeMemgraph(
                item_name="relationship",
                item_label="Relationship",
                property="to",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeMemgraph(
                item_name="relationship",
                item_label="Relationship",
                property="hierarchy",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeMemgraph(
                item_name="attribute",
                item_label="Attribute",
                property="name",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeMemgraph(
                item_name="attribute",
                item_label="Attribute",
                property="type",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeMemgraph(
                item_name="attribute",
                item_label="Attribute",
                property="uuid",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeMemgraph(
                item_name="attributevalue",
                item_label="AttributeValue",
                property="type",
                type=GraphPropertyType.STRING,
                mandatory=True,
            ),
            ConstraintNodeMemgraph(
                item_name="boolean",
                item_label="Boolean",
                property="value",
                type=GraphPropertyType.BOOLEAN,
                mandatory=True,
            ),
        ]


async def test_constraint_manager_database(db: InfrahubDatabase, default_branch):
    gm = ConstraintManager.from_graph_schema(db=db, schema=GRAPH_SCHEMA)
    await gm.add()
    constraints = await gm.list()

    if db.db_type == DatabaseType.NEO4J:
        assert constraints == [
            ConstraintInfo(item_name="node_attribute_name_exist", item_label="Attribute", property="name"),
            ConstraintInfo(item_name="node_attribute_name_type", item_label="Attribute", property="name"),
            ConstraintInfo(item_name="node_attribute_type_exist", item_label="Attribute", property="type"),
            ConstraintInfo(item_name="node_attribute_type_type", item_label="Attribute", property="type"),
            ConstraintInfo(item_name="node_attribute_uuid_exist", item_label="Attribute", property="uuid"),
            ConstraintInfo(item_name="node_attribute_uuid_type", item_label="Attribute", property="uuid"),
            ConstraintInfo(item_name="node_attributevalue_type_exist", item_label="AttributeValue", property="type"),
            ConstraintInfo(item_name="node_attributevalue_type_type", item_label="AttributeValue", property="type"),
            ConstraintInfo(item_name="node_boolean_value_exist", item_label="Boolean", property="value"),
            ConstraintInfo(item_name="node_boolean_value_type", item_label="Boolean", property="value"),
            ConstraintInfo(item_name="node_node_kind_exist", item_label="Node", property="kind"),
            ConstraintInfo(item_name="node_node_kind_type", item_label="Node", property="kind"),
            ConstraintInfo(item_name="node_node_namespace_exist", item_label="Node", property="namespace"),
            ConstraintInfo(item_name="node_node_namespace_type", item_label="Node", property="namespace"),
            ConstraintInfo(item_name="node_node_uuid_exist", item_label="Node", property="uuid"),
            ConstraintInfo(item_name="node_node_uuid_type", item_label="Node", property="uuid"),
            ConstraintInfo(item_name="node_relationship_branch_exist", item_label="Relationship", property="branch"),
            ConstraintInfo(
                item_name="node_relationship_branch_level_exist", item_label="Relationship", property="branch_level"
            ),
            ConstraintInfo(
                item_name="node_relationship_branch_level_type", item_label="Relationship", property="branch_level"
            ),
            ConstraintInfo(item_name="node_relationship_branch_type", item_label="Relationship", property="branch"),
            ConstraintInfo(item_name="node_relationship_from_exist", item_label="Relationship", property="from"),
            ConstraintInfo(item_name="node_relationship_from_type", item_label="Relationship", property="from"),
            ConstraintInfo(
                item_name="node_relationship_hierarchy_exist", item_label="Relationship", property="hierarchy"
            ),
            ConstraintInfo(
                item_name="node_relationship_hierarchy_type", item_label="Relationship", property="hierarchy"
            ),
            ConstraintInfo(item_name="node_relationship_to_exist", item_label="Relationship", property="to"),
            ConstraintInfo(item_name="node_relationship_to_type", item_label="Relationship", property="to"),
        ]

    elif db.db_type == DatabaseType.MEMGRAPH:
        assert constraints == [
            ConstraintInfo(item_name="n_a", item_label="Node", property="kind"),
            ConstraintInfo(item_name="n_a", item_label="Node", property="namespace"),
            ConstraintInfo(item_name="n_a", item_label="Node", property="uuid"),
            ConstraintInfo(item_name="n_a", item_label="Relationship", property="branch"),
            ConstraintInfo(item_name="n_a", item_label="Relationship", property="branch_level"),
            ConstraintInfo(item_name="n_a", item_label="Relationship", property="from"),
            ConstraintInfo(item_name="n_a", item_label="Relationship", property="to"),
            ConstraintInfo(item_name="n_a", item_label="Relationship", property="hierarchy"),
            ConstraintInfo(item_name="n_a", item_label="Attribute", property="name"),
            ConstraintInfo(item_name="n_a", item_label="Attribute", property="type"),
            ConstraintInfo(item_name="n_a", item_label="Attribute", property="uuid"),
            ConstraintInfo(item_name="n_a", item_label="AttributeValue", property="type"),
            ConstraintInfo(item_name="n_a", item_label="Boolean", property="value"),
        ]

    await gm.drop()

    constraints = await gm.list()
    assert constraints == []
