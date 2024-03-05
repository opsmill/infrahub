import os

import pytest

from infrahub.core.graph.constraints import (
    ConstraintInfo,
    ConstraintManager,
    ConstraintNodeMemgraph,
    ConstraintNodeNeo4j,
    ConstraintRelNeo4j,
    GraphPropertyType,
)
from infrahub.core.graph.schema import GRAPH_SCHEMA
from infrahub.database import InfrahubDatabase


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


@pytest.mark.skipif(
    os.getenv("INFRAHUB_DB_TYPE") != "neo4j",
    reason="Must use Neo4j to run this test",
)
def test_constraint_manager_from_graph_schema_neo4j(db: InfrahubDatabase):
    gm = ConstraintManager.from_graph_schema(db=db, schema=GRAPH_SCHEMA)

    assert gm.nodes == [
        ConstraintNodeNeo4j(
            item_name="node",
            item_label="Node",
            property="branch_support",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
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
            property="branch_support",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintNodeNeo4j(
            item_name="relationship",
            item_label="Relationship",
            property="name",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintNodeNeo4j(
            item_name="relationship",
            item_label="Relationship",
            property="uuid",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintNodeNeo4j(
            item_name="attribute",
            item_label="Attribute",
            property="branch_support",
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

    assert gm.rels == [
        ConstraintRelNeo4j(
            item_name="has_value",
            item_label="HAS_VALUE",
            property="branch",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_value",
            item_label="HAS_VALUE",
            property="branch_level",
            type=GraphPropertyType.INTEGER,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_value",
            item_label="HAS_VALUE",
            property="from",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_value", item_label="HAS_VALUE", property="to", type=GraphPropertyType.STRING, mandatory=False
        ),
        ConstraintRelNeo4j(
            item_name="has_value",
            item_label="HAS_VALUE",
            property="status",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_value",
            item_label="HAS_VALUE",
            property="hierarchy",
            type=GraphPropertyType.STRING,
            mandatory=False,
        ),
        ConstraintRelNeo4j(
            item_name="has_attribute",
            item_label="HAS_ATTRIBUTE",
            property="branch",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_attribute",
            item_label="HAS_ATTRIBUTE",
            property="branch_level",
            type=GraphPropertyType.INTEGER,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_attribute",
            item_label="HAS_ATTRIBUTE",
            property="from",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_attribute",
            item_label="HAS_ATTRIBUTE",
            property="to",
            type=GraphPropertyType.STRING,
            mandatory=False,
        ),
        ConstraintRelNeo4j(
            item_name="has_attribute",
            item_label="HAS_ATTRIBUTE",
            property="status",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_attribute",
            item_label="HAS_ATTRIBUTE",
            property="hierarchy",
            type=GraphPropertyType.STRING,
            mandatory=False,
        ),
        ConstraintRelNeo4j(
            item_name="is_related",
            item_label="IS_RELATED",
            property="branch",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="is_related",
            item_label="IS_RELATED",
            property="branch_level",
            type=GraphPropertyType.INTEGER,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="is_related",
            item_label="IS_RELATED",
            property="from",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="is_related",
            item_label="IS_RELATED",
            property="to",
            type=GraphPropertyType.STRING,
            mandatory=False,
        ),
        ConstraintRelNeo4j(
            item_name="is_related",
            item_label="IS_RELATED",
            property="status",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="is_related",
            item_label="IS_RELATED",
            property="hierarchy",
            type=GraphPropertyType.STRING,
            mandatory=False,
        ),
        ConstraintRelNeo4j(
            item_name="has_source",
            item_label="HAS_SOURCE",
            property="branch",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_source",
            item_label="HAS_SOURCE",
            property="branch_level",
            type=GraphPropertyType.INTEGER,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_source",
            item_label="HAS_SOURCE",
            property="from",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_source",
            item_label="HAS_SOURCE",
            property="to",
            type=GraphPropertyType.STRING,
            mandatory=False,
        ),
        ConstraintRelNeo4j(
            item_name="has_source",
            item_label="HAS_SOURCE",
            property="status",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_source",
            item_label="HAS_SOURCE",
            property="hierarchy",
            type=GraphPropertyType.STRING,
            mandatory=False,
        ),
        ConstraintRelNeo4j(
            item_name="has_owner",
            item_label="HAS_OWNER",
            property="branch",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_owner",
            item_label="HAS_OWNER",
            property="branch_level",
            type=GraphPropertyType.INTEGER,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_owner",
            item_label="HAS_OWNER",
            property="from",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_owner", item_label="HAS_OWNER", property="to", type=GraphPropertyType.STRING, mandatory=False
        ),
        ConstraintRelNeo4j(
            item_name="has_owner",
            item_label="HAS_OWNER",
            property="status",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="has_owner",
            item_label="HAS_OWNER",
            property="hierarchy",
            type=GraphPropertyType.STRING,
            mandatory=False,
        ),
        ConstraintRelNeo4j(
            item_name="is_visible",
            item_label="IS_VISIBLE",
            property="branch",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="is_visible",
            item_label="IS_VISIBLE",
            property="branch_level",
            type=GraphPropertyType.INTEGER,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="is_visible",
            item_label="IS_VISIBLE",
            property="from",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="is_visible",
            item_label="IS_VISIBLE",
            property="to",
            type=GraphPropertyType.STRING,
            mandatory=False,
        ),
        ConstraintRelNeo4j(
            item_name="is_visible",
            item_label="IS_VISIBLE",
            property="status",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="is_visible",
            item_label="IS_VISIBLE",
            property="hierarchy",
            type=GraphPropertyType.STRING,
            mandatory=False,
        ),
        ConstraintRelNeo4j(
            item_name="is_protected",
            item_label="IS_PROTECTED",
            property="branch",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="is_protected",
            item_label="IS_PROTECTED",
            property="branch_level",
            type=GraphPropertyType.INTEGER,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="is_protected",
            item_label="IS_PROTECTED",
            property="from",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="is_protected",
            item_label="IS_PROTECTED",
            property="to",
            type=GraphPropertyType.STRING,
            mandatory=False,
        ),
        ConstraintRelNeo4j(
            item_name="is_protected",
            item_label="IS_PROTECTED",
            property="status",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintRelNeo4j(
            item_name="is_protected",
            item_label="IS_PROTECTED",
            property="hierarchy",
            type=GraphPropertyType.STRING,
            mandatory=False,
        ),
    ]


@pytest.mark.skipif(
    os.getenv("INFRAHUB_DB_TYPE") != "memgraph",
    reason="Must use Memgraph to run this test",
)
def test_constraint_manager_from_graph_schema_memgraph(db: InfrahubDatabase):
    gm = ConstraintManager.from_graph_schema(db=db, schema=GRAPH_SCHEMA)

    assert gm.nodes == [
        ConstraintNodeMemgraph(
            item_name="node",
            item_label="Node",
            property="branch_support",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
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
            property="branch_support",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintNodeMemgraph(
            item_name="relationship",
            item_label="Relationship",
            property="name",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintNodeMemgraph(
            item_name="relationship",
            item_label="Relationship",
            property="uuid",
            type=GraphPropertyType.STRING,
            mandatory=True,
        ),
        ConstraintNodeMemgraph(
            item_name="attribute",
            item_label="Attribute",
            property="branch_support",
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


@pytest.mark.skipif(
    os.getenv("INFRAHUB_DB_TYPE") != "neo4j",
    reason="Must use Neo4j to run this test",
)
async def test_constraint_manager_database_neo4j(db: InfrahubDatabase, default_branch):
    gm = ConstraintManager.from_graph_schema(db=db, schema=GRAPH_SCHEMA)

    previous_constraints = await gm.list()

    await gm.add()
    constraints = await gm.list()

    assert constraints == [
        ConstraintInfo(
            item_name="node_attribute_branch_support_exist", item_label="Attribute", property="branch_support"
        ),
        ConstraintInfo(
            item_name="node_attribute_branch_support_type", item_label="Attribute", property="branch_support"
        ),
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
        ConstraintInfo(item_name="node_node_branch_support_exist", item_label="Node", property="branch_support"),
        ConstraintInfo(item_name="node_node_branch_support_type", item_label="Node", property="branch_support"),
        ConstraintInfo(item_name="node_node_kind_exist", item_label="Node", property="kind"),
        ConstraintInfo(item_name="node_node_kind_type", item_label="Node", property="kind"),
        ConstraintInfo(item_name="node_node_namespace_exist", item_label="Node", property="namespace"),
        ConstraintInfo(item_name="node_node_namespace_type", item_label="Node", property="namespace"),
        ConstraintInfo(item_name="node_node_uuid_exist", item_label="Node", property="uuid"),
        ConstraintInfo(item_name="node_node_uuid_type", item_label="Node", property="uuid"),
        ConstraintInfo(
            item_name="node_relationship_branch_support_exist", item_label="Relationship", property="branch_support"
        ),
        ConstraintInfo(
            item_name="node_relationship_branch_support_type", item_label="Relationship", property="branch_support"
        ),
        ConstraintInfo(item_name="node_relationship_name_exist", item_label="Relationship", property="name"),
        ConstraintInfo(item_name="node_relationship_name_type", item_label="Relationship", property="name"),
        ConstraintInfo(item_name="node_relationship_uuid_exist", item_label="Relationship", property="uuid"),
        ConstraintInfo(item_name="node_relationship_uuid_type", item_label="Relationship", property="uuid"),
        ConstraintInfo(item_name="rel_has_attribute_branch_exist", item_label="HAS_ATTRIBUTE", property="branch"),
        ConstraintInfo(
            item_name="rel_has_attribute_branch_level_exist", item_label="HAS_ATTRIBUTE", property="branch_level"
        ),
        ConstraintInfo(
            item_name="rel_has_attribute_branch_level_type", item_label="HAS_ATTRIBUTE", property="branch_level"
        ),
        ConstraintInfo(item_name="rel_has_attribute_branch_type", item_label="HAS_ATTRIBUTE", property="branch"),
        ConstraintInfo(item_name="rel_has_attribute_from_exist", item_label="HAS_ATTRIBUTE", property="from"),
        ConstraintInfo(item_name="rel_has_attribute_from_type", item_label="HAS_ATTRIBUTE", property="from"),
        ConstraintInfo(item_name="rel_has_attribute_hierarchy_type", item_label="HAS_ATTRIBUTE", property="hierarchy"),
        ConstraintInfo(item_name="rel_has_attribute_status_exist", item_label="HAS_ATTRIBUTE", property="status"),
        ConstraintInfo(item_name="rel_has_attribute_status_type", item_label="HAS_ATTRIBUTE", property="status"),
        ConstraintInfo(item_name="rel_has_attribute_to_type", item_label="HAS_ATTRIBUTE", property="to"),
        ConstraintInfo(item_name="rel_has_owner_branch_exist", item_label="HAS_OWNER", property="branch"),
        ConstraintInfo(item_name="rel_has_owner_branch_level_exist", item_label="HAS_OWNER", property="branch_level"),
        ConstraintInfo(item_name="rel_has_owner_branch_level_type", item_label="HAS_OWNER", property="branch_level"),
        ConstraintInfo(item_name="rel_has_owner_branch_type", item_label="HAS_OWNER", property="branch"),
        ConstraintInfo(item_name="rel_has_owner_from_exist", item_label="HAS_OWNER", property="from"),
        ConstraintInfo(item_name="rel_has_owner_from_type", item_label="HAS_OWNER", property="from"),
        ConstraintInfo(item_name="rel_has_owner_hierarchy_type", item_label="HAS_OWNER", property="hierarchy"),
        ConstraintInfo(item_name="rel_has_owner_status_exist", item_label="HAS_OWNER", property="status"),
        ConstraintInfo(item_name="rel_has_owner_status_type", item_label="HAS_OWNER", property="status"),
        ConstraintInfo(item_name="rel_has_owner_to_type", item_label="HAS_OWNER", property="to"),
        ConstraintInfo(item_name="rel_has_source_branch_exist", item_label="HAS_SOURCE", property="branch"),
        ConstraintInfo(item_name="rel_has_source_branch_level_exist", item_label="HAS_SOURCE", property="branch_level"),
        ConstraintInfo(item_name="rel_has_source_branch_level_type", item_label="HAS_SOURCE", property="branch_level"),
        ConstraintInfo(item_name="rel_has_source_branch_type", item_label="HAS_SOURCE", property="branch"),
        ConstraintInfo(item_name="rel_has_source_from_exist", item_label="HAS_SOURCE", property="from"),
        ConstraintInfo(item_name="rel_has_source_from_type", item_label="HAS_SOURCE", property="from"),
        ConstraintInfo(item_name="rel_has_source_hierarchy_type", item_label="HAS_SOURCE", property="hierarchy"),
        ConstraintInfo(item_name="rel_has_source_status_exist", item_label="HAS_SOURCE", property="status"),
        ConstraintInfo(item_name="rel_has_source_status_type", item_label="HAS_SOURCE", property="status"),
        ConstraintInfo(item_name="rel_has_source_to_type", item_label="HAS_SOURCE", property="to"),
        ConstraintInfo(item_name="rel_has_value_branch_exist", item_label="HAS_VALUE", property="branch"),
        ConstraintInfo(item_name="rel_has_value_branch_level_exist", item_label="HAS_VALUE", property="branch_level"),
        ConstraintInfo(item_name="rel_has_value_branch_level_type", item_label="HAS_VALUE", property="branch_level"),
        ConstraintInfo(item_name="rel_has_value_branch_type", item_label="HAS_VALUE", property="branch"),
        ConstraintInfo(item_name="rel_has_value_from_exist", item_label="HAS_VALUE", property="from"),
        ConstraintInfo(item_name="rel_has_value_from_type", item_label="HAS_VALUE", property="from"),
        ConstraintInfo(item_name="rel_has_value_hierarchy_type", item_label="HAS_VALUE", property="hierarchy"),
        ConstraintInfo(item_name="rel_has_value_status_exist", item_label="HAS_VALUE", property="status"),
        ConstraintInfo(item_name="rel_has_value_status_type", item_label="HAS_VALUE", property="status"),
        ConstraintInfo(item_name="rel_has_value_to_type", item_label="HAS_VALUE", property="to"),
        ConstraintInfo(item_name="rel_is_part_of_from_type", item_label="IS_PART_OF", property="from"),
        ConstraintInfo(item_name="rel_is_part_of_to_type", item_label="IS_PART_OF", property="to"),
        ConstraintInfo(item_name="rel_is_protected_branch_exist", item_label="IS_PROTECTED", property="branch"),
        ConstraintInfo(
            item_name="rel_is_protected_branch_level_exist", item_label="IS_PROTECTED", property="branch_level"
        ),
        ConstraintInfo(
            item_name="rel_is_protected_branch_level_type", item_label="IS_PROTECTED", property="branch_level"
        ),
        ConstraintInfo(item_name="rel_is_protected_branch_type", item_label="IS_PROTECTED", property="branch"),
        ConstraintInfo(item_name="rel_is_protected_from_exist", item_label="IS_PROTECTED", property="from"),
        ConstraintInfo(item_name="rel_is_protected_from_type", item_label="IS_PROTECTED", property="from"),
        ConstraintInfo(item_name="rel_is_protected_hierarchy_type", item_label="IS_PROTECTED", property="hierarchy"),
        ConstraintInfo(item_name="rel_is_protected_status_exist", item_label="IS_PROTECTED", property="status"),
        ConstraintInfo(item_name="rel_is_protected_status_type", item_label="IS_PROTECTED", property="status"),
        ConstraintInfo(item_name="rel_is_protected_to_type", item_label="IS_PROTECTED", property="to"),
        ConstraintInfo(item_name="rel_is_related_branch_exist", item_label="IS_RELATED", property="branch"),
        ConstraintInfo(item_name="rel_is_related_branch_level_exist", item_label="IS_RELATED", property="branch_level"),
        ConstraintInfo(item_name="rel_is_related_branch_level_type", item_label="IS_RELATED", property="branch_level"),
        ConstraintInfo(item_name="rel_is_related_branch_type", item_label="IS_RELATED", property="branch"),
        ConstraintInfo(item_name="rel_is_related_from_exist", item_label="IS_RELATED", property="from"),
        ConstraintInfo(item_name="rel_is_related_from_type", item_label="IS_RELATED", property="from"),
        ConstraintInfo(item_name="rel_is_related_hierarchy_type", item_label="IS_RELATED", property="hierarchy"),
        ConstraintInfo(item_name="rel_is_related_status_exist", item_label="IS_RELATED", property="status"),
        ConstraintInfo(item_name="rel_is_related_status_type", item_label="IS_RELATED", property="status"),
        ConstraintInfo(item_name="rel_is_related_to_type", item_label="IS_RELATED", property="to"),
        ConstraintInfo(item_name="rel_is_visible_branch_exist", item_label="IS_VISIBLE", property="branch"),
        ConstraintInfo(item_name="rel_is_visible_branch_level_exist", item_label="IS_VISIBLE", property="branch_level"),
        ConstraintInfo(item_name="rel_is_visible_branch_level_type", item_label="IS_VISIBLE", property="branch_level"),
        ConstraintInfo(item_name="rel_is_visible_branch_type", item_label="IS_VISIBLE", property="branch"),
        ConstraintInfo(item_name="rel_is_visible_from_exist", item_label="IS_VISIBLE", property="from"),
        ConstraintInfo(item_name="rel_is_visible_from_type", item_label="IS_VISIBLE", property="from"),
        ConstraintInfo(item_name="rel_is_visible_hierarchy_type", item_label="IS_VISIBLE", property="hierarchy"),
        ConstraintInfo(item_name="rel_is_visible_status_exist", item_label="IS_VISIBLE", property="status"),
        ConstraintInfo(item_name="rel_is_visible_status_type", item_label="IS_VISIBLE", property="status"),
        ConstraintInfo(item_name="rel_is_visible_to_type", item_label="IS_VISIBLE", property="to"),
    ]

    await gm.drop()

    constraints = await gm.list()
    assert constraints == previous_constraints


@pytest.mark.skipif(
    os.getenv("INFRAHUB_DB_TYPE") != "memgraph",
    reason="Must use Memgraph to run this test",
)
async def test_constraint_manager_database_memgraph(db: InfrahubDatabase, default_branch):
    gm = ConstraintManager.from_graph_schema(db=db, schema=GRAPH_SCHEMA)

    previous_constraints = await gm.list()

    await gm.add()
    constraints = await gm.list()

    assert constraints == [
        ConstraintInfo(item_name="n_a", item_label="Node", property="branch_support"),
        ConstraintInfo(item_name="n_a", item_label="Node", property="kind"),
        ConstraintInfo(item_name="n_a", item_label="Node", property="namespace"),
        ConstraintInfo(item_name="n_a", item_label="Node", property="uuid"),
        ConstraintInfo(item_name="n_a", item_label="Relationship", property="branch_support"),
        ConstraintInfo(item_name="n_a", item_label="Relationship", property="name"),
        ConstraintInfo(item_name="n_a", item_label="Relationship", property="uuid"),
        ConstraintInfo(item_name="n_a", item_label="Attribute", property="branch_support"),
        ConstraintInfo(item_name="n_a", item_label="Attribute", property="name"),
        ConstraintInfo(item_name="n_a", item_label="Attribute", property="type"),
        ConstraintInfo(item_name="n_a", item_label="Attribute", property="uuid"),
        ConstraintInfo(item_name="n_a", item_label="AttributeValue", property="type"),
        ConstraintInfo(item_name="n_a", item_label="Boolean", property="value"),
    ]

    await gm.drop()

    constraints = await gm.list()
    assert constraints == previous_constraints
