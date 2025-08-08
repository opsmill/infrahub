import pytest

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m036_index_attr_vals import Migration036
from infrahub.core.node import Node
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase

# TODO: test for attribute updates on branch for nodes created on main
# TODO: test for reverting large attribute type on branch where value is too large to be indexed


class TestMigration036:
    @pytest.fixture
    async def load_start_schema(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_internal_models_schema: SchemaBranch,
        all_attribute_types_schema: NodeSchema,
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.load_schema_to_db(db=db, branch=default_branch, schema=schema_branch)

    @pytest.fixture
    async def branch_0(self, db: InfrahubDatabase, default_branch: Branch, load_start_schema: None) -> Branch:
        branch_0 = await create_branch(db=db, branch_name="branch_0")
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        schema_branch.duplicate(name=branch_0.name)
        registry.schema.set_schema_branch(name=branch_0.name, schema=schema_branch)
        return branch_0

    @pytest.fixture
    async def branch_1(self, db: InfrahubDatabase, default_branch: Branch, load_start_schema: None) -> Branch:
        branch_1 = await create_branch(db=db, branch_name="branch_1")
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        schema_branch.duplicate(name=branch_1.name)
        registry.schema.set_schema_branch(name=branch_1.name, schema=schema_branch)
        return branch_1

    @pytest.fixture
    async def branch_2(self, db: InfrahubDatabase, default_branch: Branch, load_start_schema: None) -> Branch:
        branch_2 = await create_branch(db=db, branch_name="branch_2")
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        schema_branch.duplicate(name=branch_2.name)
        registry.schema.set_schema_branch(name=branch_2.name, schema=schema_branch)
        return branch_2

    @pytest.fixture
    async def load_branch_0_nodes(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        branch_0: Branch,
        load_start_schema: None,
        all_attribute_types_schema: NodeSchema,
    ) -> list[Node]:
        loaded_nodes = []

        all_attribute_types_schema = registry.schema.get_node_schema(name=all_attribute_types_schema.kind)

        # node on branch before main schema change
        branch_node_before = await Node.init(db=db, branch=branch_0, schema=all_attribute_types_schema)
        await branch_node_before.new(
            db=db, mystring="-abc", mytextarea="-abc", myjson={"-a": "b"}, mylist=["-a", "-b", "-c"], name="123"
        )
        await branch_node_before.save(db=db)
        loaded_nodes.append(branch_node_before)

        schema_branch = registry.schema.get_schema_branch(name=branch_0.name)
        schema_branch = schema_branch.duplicate(name=branch_0.name)
        node_schema = schema_branch.get_node(name=all_attribute_types_schema.kind)

        name_attr_schema = node_schema.get_attribute(name="name")
        name_attr_schema.kind = "TextArea"
        text_area_attr_schema = node_schema.get_attribute(name="mytextarea")
        text_area_attr_schema.kind = "Text"
        schema_branch.set(name=all_attribute_types_schema.kind, schema=node_schema)
        registry.schema.set_schema_branch(name=branch_0.name, schema=schema_branch)
        await registry.schema.load_schema_to_db(db=db, branch=branch_0, schema=schema_branch)

        # node on main after schema change
        branch_node_after = await Node.init(db=db, branch=branch_0, schema=all_attribute_types_schema.kind)
        await branch_node_after.new(
            db=db, mystring="-def", mytextarea="-d" * 100, myjson={"-d": "e"}, mylist=["-d", "-e", "-f"], name="456"
        )
        await branch_node_after.save(db=db)
        loaded_nodes.append(branch_node_after)

        return loaded_nodes

    @pytest.fixture
    async def load_main_nodes(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        load_start_schema: None,
        all_attribute_types_schema: NodeSchema,
    ) -> list[Node]:
        loaded_nodes = []

        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

        # node on main before schema change
        main_node_before = await Node.init(db=db, branch=default_branch, schema=all_attribute_types_schema.kind)
        await main_node_before.new(
            db=db, mystring="abc", mytextarea="a" * 10_000, myjson={"a": "b"}, mylist=["a", "b", "c"]
        )
        await main_node_before.save(db=db)
        loaded_nodes.append(main_node_before)

        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        node_schema = schema_branch.get_node(name=all_attribute_types_schema.kind)
        text_attr_schema = node_schema.get_attribute(name="mystring")
        text_attr_schema.kind = "TextArea"
        schema_branch.set(name=all_attribute_types_schema.kind, schema=node_schema)
        registry.schema.set_schema_branch(name=default_branch.name, schema=schema_branch)
        await registry.schema.load_schema_to_db(db=db, branch=default_branch, schema=schema_branch)

        # node on main after schema change
        main_node_after = await Node.init(db=db, branch=default_branch, schema=all_attribute_types_schema.kind)
        await main_node_after.new(
            db=db, mystring="def", mytextarea="d" * 100, myjson={"d": "e"}, mylist=["d", "e", "f"]
        )
        await main_node_after.save(db=db)
        loaded_nodes.append(main_node_after)

        return loaded_nodes

    @pytest.fixture
    async def load_branch_1_nodes(
        self, db: InfrahubDatabase, default_branch: Branch, branch_1: Branch, all_attribute_types_schema: NodeSchema
    ) -> list[Node]:
        loaded_nodes = []

        all_attribute_types_schema = registry.schema.get_node_schema(name=all_attribute_types_schema.kind)

        # node on branch before branch schema change
        branch_node_before = await Node.init(db=db, branch=branch_1, schema=all_attribute_types_schema)
        await branch_node_before.new(
            db=db, mystring="abc", mytextarea="g" * 10_000, myjson={"g": "h"}, mylist=["g", "h", "i"]
        )
        await branch_node_before.save(db=db)
        loaded_nodes.append(branch_node_before)

        return loaded_nodes

    @pytest.fixture
    async def load_branch_2_nodes(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        branch_2: Branch,
        all_attribute_types_schema: NodeSchema,
    ) -> list[Node]:
        loaded_nodes = []

        all_attribute_types_schema = registry.schema.get_node_schema(name=all_attribute_types_schema.kind)

        # node on branch after main schema change
        branch_node_before = await Node.init(db=db, branch=branch_2, schema=all_attribute_types_schema)
        await branch_node_before.new(
            db=db, mystring="jkl", mytextarea="j" * 10_000, myjson={"j": "k"}, mylist=["j", "k", "l"], name="789"
        )
        await branch_node_before.save(db=db)
        loaded_nodes.append(branch_node_before)

        schema_branch = registry.schema.get_schema_branch(name=branch_2.name)
        schema_branch = schema_branch.duplicate(name=branch_2.name)
        node_schema = schema_branch.get_node(name=all_attribute_types_schema.kind)

        name_attr_schema = node_schema.get_attribute(name="mylist")
        name_attr_schema.kind = "Text"
        text_area_attr_schema = node_schema.get_attribute(name="myjson")
        text_area_attr_schema.kind = "TextArea"
        schema_branch.set(name=all_attribute_types_schema.kind, schema=node_schema)
        registry.schema.set_schema_branch(name=branch_2.name, schema=schema_branch)
        await registry.schema.load_schema_to_db(db=db, branch=branch_2, schema=schema_branch)

        # node on main after schema change
        branch_node_after = await Node.init(db=db, branch=branch_2, schema=all_attribute_types_schema.kind)
        await branch_node_after.new(
            db=db, mystring="mno", mytextarea="m" * 100, myjson='{"m": "n"}', mylist='["m","n","o"]', name="101"
        )
        await branch_node_after.save(db=db)
        loaded_nodes.append(branch_node_after)

        return loaded_nodes

    async def verify_no_duplicate_has_value_edges(self, db: InfrahubDatabase) -> None:
        query = """
MATCH (attr:Attribute)-[e:HAS_VALUE {status: "active"}]->()
MATCH (attr)-[overlap:HAS_VALUE {status: "active", branch: e.branch}]->()
WHERE elementId(e) <> elementId(overlap)
AND overlap.from >= e.from
AND (e.to IS NULL OR overlap.from < e.to)
RETURN attr.uuid AS attr_uuid, e.branch AS branch, e.from AS from_time, overlap.from AS overlap_from_time
        """
        results = await db.execute_query(query=query)
        if not results:
            return
        error_messages = []
        for result in results:
            attr_uuid = result.get("attr_uuid")
            branch = result.get("branch")
            from_time = result.get("from_time")
            overlap_from_time = result.get("overlap_from_time")
            error_messages.append(
                f"Duplicate HAS_VALUE edge for attribute {attr_uuid} on branch {branch} from {from_time} to {overlap_from_time}"
            )
        assert len(error_messages) == 0, "\n".join(error_messages)

    async def verify_attributes_have_correct_indexing(
        self, db: InfrahubDatabase, branch: Branch, kind_attr_name_map: dict[str, list[str]]
    ) -> None:
        for node_kind, attr_names in kind_attr_name_map.items():
            params = {
                "branch": branch.name,
                "branch_level": branch.hierarchy_level,
                "branched_from": branch.get_branched_from(),
                "attr_names": attr_names,
            }

            query = """
MATCH (n:%(node_kind)s)-[r1:HAS_ATTRIBUTE]->(attr:Attribute)
WHERE r1.status = "active"
AND r1.to IS NULL
AND (
    r1.branch = $branch
    OR (r1.branch_level < $branch_level AND r1.from <= $branched_from)
)
WITH DISTINCT n, attr

CALL (attr) {
    MATCH (attr)-[r2:HAS_VALUE]->(av:AttributeValue)
    WHERE r2.status = "active"
    AND r2.to IS NULL
    AND (
        r2.branch = $branch
        OR (r2.branch_level < $branch_level AND r2.from <= $branched_from)
    )
    RETURN r2, av
    ORDER BY r2.branch_level DESC, r2.from DESC
    LIMIT 1
}
WITH
    n.uuid AS node_uuid,
    r2.branch AS branch,
    attr.name AS attr_name,
    elementId(av) AS av_id,
    attr.name IN $attr_names AS is_large_attr,
    "AttributeValueIndexed" IN labels(av) AS is_indexed
WITH *,
    is_large_attr AND is_indexed AS should_not_be_indexed,
    NOT is_large_attr AND NOT is_indexed AS should_be_indexed
WHERE should_not_be_indexed OR should_be_indexed
RETURN node_uuid, branch, attr_name, av_id, should_not_be_indexed, should_be_indexed
            """ % {"node_kind": node_kind}
            results = await db.execute_query(query=query, params=params)
            if not results:
                continue
            error_messages = []
            for result in results:
                node_uuid = result.get("node_uuid")
                branch = result.get("branch")
                attr_name = result.get("attr_name")
                av_id = result.get("av_id")
                should_be_indexed = result.get("should_be_indexed")
                should_not_be_indexed = result.get("should_not_be_indexed")
                if should_not_be_indexed:
                    error_messages.append(
                        f"The {attr_name} attribute on Node {node_kind} ({node_uuid}) on "
                        f"branch {branch} is indexed but should not be: database_id={av_id}"
                    )
                elif should_be_indexed:
                    error_messages.append(
                        f"The {attr_name} attribute on Node {node_kind} ({node_uuid}) on "
                        f"branch {branch} is not indexed but should be: database_id={av_id}"
                    )
            assert len(error_messages) == 0, "\n".join(error_messages)

    async def test_migration_036(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        load_branch_0_nodes: list[Node],
        load_main_nodes: list[Node],
        load_branch_1_nodes: list[Node],
        load_branch_2_nodes: list[Node],
        branch_0: Branch,
        branch_1: Branch,
        branch_2: Branch,
    ) -> None:
        remove_attribute_value_indexed_labels_query = """
MATCH (avi:AttributeValueIndexed)
REMOVE avi:AttributeValueIndexed
        """
        await db.execute_query(query=remove_attribute_value_indexed_labels_query)

        migration = Migration036()
        await migration.execute(db=db)

        for branch, nodes in [
            (default_branch, load_main_nodes),
            (branch_0, load_branch_0_nodes),
            (branch_1, load_branch_1_nodes),
            (branch_2, load_branch_2_nodes),
        ]:
            for node in nodes:
                schema = node.get_schema()
                retrieved_node = await NodeManager.get_one(db=db, branch=branch, id=node.id)
                for attr_name in schema.attribute_names:
                    original_attr_value = getattr(node, attr_name).value
                    retrieved_attr_value = getattr(retrieved_node, attr_name).value
                    # this one went from a list to a text attribute
                    if branch.name == "branch_2" and attr_name == "mylist":
                        assert str(original_attr_value).replace("'", '"').replace(" ", "") == retrieved_attr_value
                    else:
                        assert original_attr_value == retrieved_attr_value

        await self.verify_no_duplicate_has_value_edges(db=db)

        # branch_0 is before schema changes on main, so mystring remains a text attribute
        # name was updated to TextArea and mytextarea was updated to Text
        kind_attr_name_map = {
            "TestAllAttributeTypes": ["myjson", "mylist", "name"],
        }
        await self.verify_attributes_have_correct_indexing(
            db=db, branch=branch_0, kind_attr_name_map=kind_attr_name_map
        )

        kind_attr_name_map = {
            "TestAllAttributeTypes": ["mytextarea", "myjson", "mylist", "mystring"],
        }
        await self.verify_attributes_have_correct_indexing(
            db=db, branch=default_branch, kind_attr_name_map=kind_attr_name_map
        )
        await self.verify_attributes_have_correct_indexing(
            db=db, branch=branch_1, kind_attr_name_map=kind_attr_name_map
        )

        # branch_2 updates mylist to a Text attribute and myjson to a TextArea attribute
        kind_attr_name_map = {
            "TestAllAttributeTypes": ["mytextarea", "myjson", "mystring"],
        }
        await self.verify_attributes_have_correct_indexing(
            db=db, branch=branch_2, kind_attr_name_map=kind_attr_name_map
        )
