from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rich.console import Console

from infrahub.constants.database import IndexType
from infrahub.core.attribute import MAX_STRING_LENGTH
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.database.index import IndexItem
from infrahub.database.neo4j import IndexManagerNeo4j
from infrahub.log import get_logger

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


AV_INDEXED_INDEX = IndexItem(
    name="attr_value_indexed", label="AttributeValueIndexed", properties=["value"], type=IndexType.RANGE
)


@dataclass
class SchemaAttributeTimeframe:
    kind: str
    attr_name: str
    branch: str
    branch_level: int
    branched_from: str
    from_time: str
    is_default_branch: bool
    is_large_type: bool


class GetLargeAttributeTypesQuery(Query):
    """For every active attribute on every branch, return a SchemaAttributeTimeframe object"""

    name = "get_large_attribute_types_query"
    type = QueryType.READ
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (branch:Branch)
// --------------
// find all SchemaAttributes with a LARGE_ATTRIBUTE_TYPE kind for each branch
// --------------
MATCH (schema_attr:SchemaAttribute)-[r1:HAS_ATTRIBUTE]->(attr_kind:Attribute {name: "kind"})-[r2:HAS_VALUE]->(attr_kind_value)
WHERE r1.status = "active" and r1.to IS NULL AND r2.status = "active" and r2.to IS NULL
WITH DISTINCT branch, schema_attr, attr_kind
CALL (schema_attr, attr_kind, branch) {
    MATCH (schema_attr)-[has_attr:HAS_ATTRIBUTE]->(attr_kind)-[has_value:HAS_VALUE]->(attr_kind_value)
    WHERE has_attr.status = "active"
    AND has_value.status = "active"
    AND has_attr.to IS NULL
    AND has_value.to IS NULL
    AND (
        has_attr.branch = branch.name
        OR (has_attr.branch_level < branch.hierarchy_level AND has_attr.from <= branch.branched_from)
    )
    AND (
        has_value.branch = branch.name
        OR (has_value.branch_level < branch.hierarchy_level AND has_value.from <= branch.branched_from)
    )
    WITH has_value.from AS from_time, attr_kind_value.value AS attr_type
    ORDER BY has_value.branch_level DESC, has_value.from DESC
    LIMIT 1
    WITH from_time, attr_type
    RETURN from_time, attr_type IN ["JSON", "List", "TextArea"] AS is_large_type
}
CALL (schema_attr, branch) {
    // --------------
    // get the attribute name
    // --------------
    MATCH (schema_attr)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[r2:HAS_VALUE]->(name_value)
    WHERE r1.status = "active"
    AND r1.to IS NULL
    AND (
        r1.branch = branch.name
        OR (r1.branch_level < branch.hierarchy_level AND r1.from <= branch.branched_from)
    )
    AND r2.status = "active"
    AND r2.to IS NULL
    AND (
        r2.branch = branch.name
        OR (r2.branch_level < branch.hierarchy_level AND r2.from <= branch.branched_from)
    )
    WITH name_value.value AS attr_name
    ORDER BY r2.branch_level DESC, r1.branch_level DESC, r2.from DESC, r1.from DESC
    LIMIT 1

    // --------------
    // get the the schema node/generic
    // --------------
    MATCH (schema_attr)-[r1:IS_RELATED]-(:Relationship {name: "schema__node__attributes"})-[r2:IS_RELATED]-(schema_node:SchemaNode|SchemaGeneric)
    WHERE r1.status = "active"
    AND r1.to IS NULL
    AND (
        r1.branch = branch.name
        OR (r1.branch_level < branch.hierarchy_level AND r1.from <= branch.branched_from)
    )
    AND r2.status = "active"
    AND r2.to IS NULL
    AND (
        r2.branch = branch.name
        OR (r2.branch_level < branch.hierarchy_level AND r2.from <= branch.branched_from)
    )
    WITH attr_name, schema_node
    ORDER BY r2.branch_level DESC, r1.branch_level DESC, r2.from DESC, r1.from DESC
    LIMIT 1

    // --------------
    // find the namespace for this SchemaNode/SchemaGeneric
    // --------------
    MATCH (schema_node)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[r2:HAS_VALUE]->(kind_namespace_value)
    WHERE r1.status = "active"
    AND r1.to IS NULL
    AND (
        r1.branch = branch.name
        OR (r1.branch_level < branch.hierarchy_level AND r1.from <= branch.branched_from)
    )
    AND r2.status = "active"
    AND r2.to IS NULL
    AND (
        r2.branch = branch.name
        OR (r2.branch_level < branch.hierarchy_level AND r2.from <= branch.branched_from)
    )
    WITH attr_name, schema_node, kind_namespace_value.value AS kind_namespace
    ORDER BY r2.branch_level DESC, r1.branch_level DESC, r2.from DESC, r1.from DESC
    LIMIT 1

    // --------------
    // find the name for this SchemaNode/SchemaGeneric
    // --------------
    MATCH (schema_node)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[r2:HAS_VALUE]->(kind_name_value)
    WHERE r1.status = "active"
    AND r1.to IS NULL
    AND (
        r1.branch = branch.name
        OR (r1.branch_level < branch.hierarchy_level AND r1.from <= branch.branched_from)
    )
    AND r2.status = "active"
    AND r2.to IS NULL
    AND (
        r2.branch = branch.name
        OR (r2.branch_level < branch.hierarchy_level AND r2.from <= branch.branched_from)
    )
    WITH attr_name, kind_namespace, kind_name_value.value AS kind_name
    ORDER BY r2.branch_level DESC, r1.branch_level DESC, r2.from DESC, r1.from DESC
    LIMIT 1
    RETURN attr_name, kind_namespace, kind_name
}
RETURN
    kind_namespace,
    kind_name,
    attr_name,
    branch.name AS branch,
    branch.hierarchy_level AS branch_level,
    branch.branched_from AS branched_from,
    branch.is_default AS is_default_branch,
    from_time,
    is_large_type
"""
        self.add_to_query(query)
        self.return_labels = [
            "kind_namespace",
            "kind_name",
            "attr_name",
            "branch",
            "branch_level",
            "branched_from",
            "is_default_branch",
            "from_time",
            "is_large_type",
        ]

    def get_large_attribute_type_timeframes(self) -> list[SchemaAttributeTimeframe]:
        schema_attribute_timeframes: list[SchemaAttributeTimeframe] = []
        for result in self.get_results():
            kind_namespace = result.get_as_type("kind_namespace", return_type=str)
            kind_name = result.get_as_type("kind_name", return_type=str)
            attr_name = result.get_as_type("attr_name", return_type=str)
            branch = result.get_as_type("branch", return_type=str)
            branch_level = result.get_as_type("branch_level", return_type=int)
            branched_from = result.get_as_type("branched_from", return_type=str)
            is_default_branch = result.get_as_type("is_default_branch", return_type=bool)
            is_large_type = result.get_as_type("is_large_type", return_type=bool)
            from_time = result.get_as_type("from_time", return_type=str)
            kind = f"{kind_namespace}{kind_name}"
            schema_attribute_timeframes.append(
                SchemaAttributeTimeframe(
                    kind=kind,
                    attr_name=attr_name,
                    branch=branch,
                    branch_level=branch_level,
                    branched_from=branched_from,
                    from_time=from_time,
                    is_default_branch=is_default_branch,
                    is_large_type=is_large_type,
                )
            )
        return schema_attribute_timeframes


class DeIndexLargeAttributeValuesQuery(Query):
    name = "de_index_large_attribute_values_query"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, max_value_size: int, **kwargs: Any) -> None:
        self.max_value_size = max_value_size
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["max_value_size"] = self.max_value_size
        query = """
MATCH (av:AttributeValueIndexed)
WHERE size(toString(av.value)) > $max_value_size
REMOVE av:AttributeValueIndexed
        """
        self.add_to_query(query)


class CreateNonIndexedAttributeValueQuery(Query):
    name = "create_non_indexed_attribute_value_query"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        schema_attribute_timeframe: SchemaAttributeTimeframe,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.schema_attribute_timeframe = schema_attribute_timeframe

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params.update(
            {
                "attribute_name": self.schema_attribute_timeframe.attr_name,
                "branch": self.schema_attribute_timeframe.branch,
                "branch_level": self.schema_attribute_timeframe.branch_level,
                "branched_from": self.schema_attribute_timeframe.branched_from,
                "from_time": self.schema_attribute_timeframe.from_time,
            }
        )
        query = """
MATCH (node:Node:%(schema_kind)s)
CALL (node) {
    MATCH (node)-[has_attr_e:HAS_ATTRIBUTE]->(attr:Attribute)
    WHERE attr.name = $attribute_name
    AND (
        has_attr_e.branch = $branch
        OR (has_attr_e.branch_level < $branch_level AND has_attr_e.from <= $branched_from)
    )
    AND has_attr_e.status = "active"
    AND has_attr_e.to IS NULL
    WITH attr
    ORDER BY has_attr_e.branch_level DESC, has_attr_e.from DESC
    LIMIT 1

    // --------------
    // identify the active HAS_VALUE edges that we need to consider
    // --------------
    MATCH (attr)-[has_val_e:HAS_VALUE]->(av)
    WHERE (
        has_val_e.branch = $branch
        OR (has_val_e.branch_level < $branch_level AND has_val_e.from <= $branched_from)
    )
    AND has_val_e.status = "active"
    AND has_val_e.to IS NULL
    RETURN attr, has_val_e, av
    ORDER BY has_val_e.branch_level DESC, has_val_e.from DESC
    LIMIT 1
}
// --------------------
// determine the timestamp to de-index the AttributeValue
// --------------------
WITH attr, has_val_e, av,
CASE
    WHEN $from_time <= has_val_e.from THEN has_val_e.from
    ELSE $from_time
END AS non_indexed_from

// --------------------
// create the new edge to the AttributeValueNonIndexed vertex, if necessary
// --------------------
WITH attr, has_val_e, av, non_indexed_from
CALL (attr, has_val_e, av, non_indexed_from) {
    WITH has_val_e
    WHERE NOT "AttributeValueNonIndexed" IN labels(av)

    MERGE (av_no_index:AttributeValueNonIndexed {value: av.value, is_default: av.is_default})
    LIMIT 1

    CREATE (attr)-[add_no_index_on_branch:HAS_VALUE]->(av_no_index)
    SET add_no_index_on_branch = properties(has_val_e)
    SET
        add_no_index_on_branch.branch = $branch,
        add_no_index_on_branch.branch_level = $branch_level,
        add_no_index_on_branch.from = non_indexed_from,
        add_no_index_on_branch.status = "active",
        add_no_index_on_branch.to = NULL

    // --------------------
    // delete existing active edge if it is on this branch and we created a new edge
    // --------------------
    WITH has_val_e
    WHERE has_val_e.branch = $branch
    DELETE has_val_e

}
        """ % {"schema_kind": self.schema_attribute_timeframe.kind}
        self.add_to_query(query)


class RevertNonIndexOnBranchQuery(Query):
    name = "revert_non_index_on_branch_query"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        schema_attribute_timeframe: SchemaAttributeTimeframe,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.schema_attribute_timeframe = schema_attribute_timeframe

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params.update(
            {
                "attribute_name": self.schema_attribute_timeframe.attr_name,
                "branch": self.schema_attribute_timeframe.branch,
                "branch_level": self.schema_attribute_timeframe.branch_level,
                "branched_from": self.schema_attribute_timeframe.branched_from,
                "from_time": self.schema_attribute_timeframe.from_time,
            }
        )
        query = """
MATCH (node:Node:%(schema_kind)s)
CALL (node) {
    MATCH (node)-[has_attr_e:HAS_ATTRIBUTE]->(attr:Attribute)
    WHERE attr.name = $attribute_name
    AND (
        has_attr_e.branch = $branch
        OR (has_attr_e.branch_level < $branch_level AND has_attr_e.from <= $branched_from)
    )
    AND has_attr_e.status = "active"
    AND has_attr_e.to IS NULL
    WITH attr
    ORDER BY has_attr_e.branch_level DESC, has_attr_e.from DESC
    LIMIT 1

    // --------------
    // identify the active HAS_VALUE edges that we need to consider
    // --------------
    MATCH (attr)-[has_val_e:HAS_VALUE]->(av)
    WHERE (
        has_val_e.branch = $branch
        OR (has_val_e.branch_level < $branch_level AND has_val_e.from <= $branched_from)
    )
    AND has_val_e.status = "active"
    AND has_val_e.to IS NULL
    RETURN attr, has_val_e, av
    ORDER BY has_val_e.branch_level DESC, has_val_e.from DESC
    LIMIT 1
}

// --------------------
// determine the timestamp to index the AttributeValue
// --------------------
WITH attr, has_val_e, av,
CASE
    WHEN $from_time <= has_val_e.from THEN has_val_e.from
    ELSE $from_time
END AS indexed_from

// --------------------
// create the new edge to the AttributeValue vertex
// --------------------
WITH attr, has_val_e, av, indexed_from
CALL (attr, has_val_e, av, indexed_from) {
    WITH has_val_e
    WHERE NOT "AttributeValue" IN labels(av)

    MERGE (av_index:AttributeValue {value: av.value, is_default: av.is_default})
    LIMIT 1

    CREATE (attr)-[add_index_on_branch:HAS_VALUE]->(av_index)
    SET add_index_on_branch = properties(has_val_e)
    SET
        add_index_on_branch.branch = $branch,
        add_index_on_branch.branch_level = $branch_level,
        add_index_on_branch.from = indexed_from,
        add_index_on_branch.status = "active",
        add_index_on_branch.to = NULL

    // --------------------
    // delete existing active edge if it is on this branch and we created a new edge
    // --------------------
    WITH has_val_e
    WHERE has_val_e.branch = $branch AND add_index_on_branch IS NOT NULL
    DELETE has_val_e
}
        """ % {"schema_kind": self.schema_attribute_timeframe.kind}
        self.add_to_query(query)


class SetAttributeValueIndexedQuery(Query):
    name = "set_attribute_value_indexed_query"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (av:AttributeValue)
SET av:AttributeValueIndexed
        """
        self.add_to_query(query)


class FinalizeAttributeValueNonIndexedQuery(Query):
    name = "finalize_attribute_value_non_indexed_query"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (av_no_index:AttributeValueNonIndexed)
SET av_no_index:AttributeValue
REMOVE av_no_index:AttributeValueNonIndexed
        """
        self.add_to_query(query)


class Migration037(ArbitraryMigration):
    """
    Update AttributeValue vertices to be AttributeValueIndexed, unless they include values for LARGE_ATTRIBUTE_TYPES

    0. Drop the index on the AttributeValueIndexed vertex, there are no AttributeValueIndexed vertices at this point anyway
    1. For all attributes of all schema on all branches, determine if the attribute is a LARGE_ATTRIBUTE_TYPE and when
        attribute's kind was last updated in the schema
    2. For all branches, starting with the default and global branches, update HAS_VALUE edges for LARGE_ATTRIBUTE_TYPE
        attributes to point to AttributeValueNonIndexed vertices
    3. For any LARGE_ATTRIBUTE_TYPE attributes on the default branch that were updated to non-large_type on other branches,
        revert the HAS_VALUE edges to point to AttributeValue vertices
    4. Add the AttributeValueIndexed label to all AttributeValue vertices
    5. Update all AttributeValueNonIndexed vertices to AttributeValue (no AttributeValueIndexed label)
    6. Any AttributeValueIndexed vertices with a value of size greater than MAX_STRING_LENGTH are changed to AttributeValueNonIndexed
    7. Add the index on AttributeValueIndexed again
    """

    name: str = "037_index_attr_vals"
    minimum_version: int = 36

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()

        return result

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: PLR0915
        console = Console()
        result = MigrationResult()

        # find the active schema attributes that have a LARGE_ATTRIBUTE_TYPE kind on all branches
        console.print(
            f"{Timestamp().to_string()} Determining schema attribute types and timestamps on all branches...", end=""
        )
        get_large_attribute_types_query = await GetLargeAttributeTypesQuery.init(db=db)
        await get_large_attribute_types_query.execute(db=db)
        schema_attribute_timeframes = get_large_attribute_types_query.get_large_attribute_type_timeframes()
        console.print("done")

        # find which schema attributes are large_types in the default branch, but updated to non-large_type on other branches
        # {(kind, attr_name): SchemaAttributeTimeframe}
        console.print(
            f"{Timestamp().to_string()} Determining which schema attributes have been updated to non-large_type on non-default branches...",
            end="",
        )
        main_schema_attribute_timeframes_map: dict[tuple[str, str], SchemaAttributeTimeframe] = {}
        for schema_attr_time in schema_attribute_timeframes:
            if schema_attr_time.is_default_branch:
                main_schema_attribute_timeframes_map[schema_attr_time.kind, schema_attr_time.attr_name] = (
                    schema_attr_time
                )
        large_type_reverts: list[SchemaAttributeTimeframe] = []
        for schema_attr_time in schema_attribute_timeframes:
            if schema_attr_time.is_default_branch or schema_attr_time.is_large_type:
                continue
            default_schema_attr_time = main_schema_attribute_timeframes_map.get(
                (schema_attr_time.kind, schema_attr_time.attr_name)
            )
            if not default_schema_attr_time:
                continue
            if (
                default_schema_attr_time.is_large_type
                and default_schema_attr_time.from_time < schema_attr_time.branched_from
            ):
                large_type_reverts.append(schema_attr_time)
        console.print("done")

        # drop the index on the AttributeValueNonIndexed vertex, there won't be any at this point anyway
        console.print(f"{Timestamp().to_string()} Dropping index on AttributeValueIndexed vertices...", end="")
        index_manager = IndexManagerNeo4j(db=db)
        index_manager.init(nodes=[AV_INDEXED_INDEX], rels=[])
        await index_manager.drop()
        console.print("done")

        # create the temporary non-indexed attribute value vertices for LARGE_ATTRIBUTE_TYPE attributes
        # start with default branch
        console.print(f"{Timestamp().to_string()} Update non-indexed attribute values with temporary label...", end="")
        large_schema_attribute_timeframes = [
            schema_attr_time for schema_attr_time in schema_attribute_timeframes if schema_attr_time.is_large_type
        ]
        for schema_attr_time in sorted(large_schema_attribute_timeframes, key=lambda x: x.branch_level):
            create_non_indexed_attribute_value_query = await CreateNonIndexedAttributeValueQuery.init(
                db=db, schema_attribute_timeframe=schema_attr_time
            )
            await create_non_indexed_attribute_value_query.execute(db=db)
        console.print("done")

        # re-index attribute values on branches where the type was updated to non-large_type
        console.print(
            f"{Timestamp().to_string()} Indexing attribute values on branches where the attribute schema was updated to a non-large_type...",
            end="",
        )
        for schema_attr_time in large_type_reverts:
            revert_non_index_on_branch_query = await RevertNonIndexOnBranchQuery.init(
                db=db, schema_attribute_timeframe=schema_attr_time
            )
            await revert_non_index_on_branch_query.execute(db=db)
        console.print("done")

        # set the AttributeValue vertices to be AttributeValueIndexed
        console.print(
            f"{Timestamp().to_string()} Update all AttributeValue vertices to add the AttributeValueIndexed label...",
            end="",
        )
        set_attribute_value_indexed_query = await SetAttributeValueIndexedQuery.init(db=db)
        await set_attribute_value_indexed_query.execute(db=db)
        console.print("done")

        # set AttributeValueNonIndexed vertices to just AttributeValue
        console.print(
            f"{Timestamp().to_string()} Update all AttributeValueNonIndexed vertices to be AttributeValue (no index)...",
            end="",
        )
        finalize_attribute_value_non_indexed_query = await FinalizeAttributeValueNonIndexedQuery.init(db=db)
        await finalize_attribute_value_non_indexed_query.execute(db=db)
        console.print("done")

        # de-index all attribute values too large to be indexed
        console.print(
            f"{Timestamp().to_string()} De-index any legacy attribute data that is too large to be indexed...", end=""
        )
        de_index_large_attribute_values_query = await DeIndexLargeAttributeValuesQuery.init(
            db=db, max_value_size=MAX_STRING_LENGTH
        )
        await de_index_large_attribute_values_query.execute(db=db)
        console.print("done")

        # add the index back to the AttributeValueNonIndexed vertex
        console.print(f"{Timestamp().to_string()} Add the index back to the AttributeValueIndexed label...", end="")
        index_manager = IndexManagerNeo4j(db=db)
        index_manager.init(nodes=[AV_INDEXED_INDEX], rels=[])
        await index_manager.add()
        console.print("done")

        return result
