from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

import ujson

from infrahub.core import registry
from infrahub.core.constants import SYSTEM_USER_ID, InfrahubKind
from infrahub.core.migrations.shared import (
    ArbitraryMigration,
    MigrationInput,
    MigrationResult,
    get_migration_console,
)
from infrahub.core.query import Query, QueryType
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.core.schema.definitions.core.resource_pool import core_ip_pool
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

console = get_migration_console()

OLD_IDENTIFIERS = ["prefixpool__resource", "ipaddresspool__resource"]
NEW_IDENTIFIER = "ippool__resource"

POOL_NODE_NAMES = ["IPPrefixPool", "IPAddressPool"]


# ------------------------------------------------------------
# Structured payload types for cypher query inputs and outputs
# ------------------------------------------------------------


@dataclass(frozen=True)
class SchemaAttributeRewrite:
    """One rewrite target for :class:`BulkRewriteSchemaAttributeQuery`.

    ``parent_name`` / ``parent_namespace`` always identify the parent SchemaNode
    or SchemaGeneric. When ``relationship_name`` is ``None`` the attribute being
    rewritten lives directly on the parent (``parent``-[:HAS_ATTRIBUTE]->(attr));
    when it is set, the rewrite target is the SchemaRelationship reached via
    ``parent``-[:IS_RELATED]-()-[:IS_RELATED]-(SchemaRelationship {name = relationship_name})``.
    """

    parent_name: str
    parent_namespace: str
    attribute_name: str
    new_value: str
    relationship_name: str | None = None


@dataclass(frozen=True)
class InheritFromRow:
    node_name: str
    current: list[str]


# ---------------------------------------------------------------------------
# Query classes — all Cypher run by this migration goes through these.
# ---------------------------------------------------------------------------


class RenameRelationshipVerticesQuery(Query):
    name = "m070_rename_relationship_vertices"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["old_names"] = OLD_IDENTIFIERS
        self.params["new_name"] = NEW_IDENTIFIER
        query = """
MATCH (pool:%(pool_kind_a)s|%(pool_kind_b)s)-[:IS_RELATED]-(r:Relationship)-[:IS_RELATED]-(:%(prefix_kind)s)
WHERE r.name IN $old_names
WITH DISTINCT r
SET r.name = $new_name
        """ % {
            "pool_kind_a": InfrahubKind.IPPREFIXPOOL,
            "pool_kind_b": InfrahubKind.IPADDRESSPOOL,
            "prefix_kind": InfrahubKind.IPPREFIX,
        }
        self.add_to_query(query)


class AddCoreIPPoolLabelQuery(Query):
    name = "m070_add_core_ip_pool_label"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
MATCH (n:%(pool_kind_a)s|%(pool_kind_b)s)
WHERE NOT n:%(ippool_kind)s
SET n:%(ippool_kind)s
        """ % {
            "pool_kind_a": InfrahubKind.IPPREFIXPOOL,
            "pool_kind_b": InfrahubKind.IPADDRESSPOOL,
            "ippool_kind": InfrahubKind.IPPOOL,
        }
        self.add_to_query(query)


class GetSchemaAnchorTimestampQuery(Query):
    """Return the earliest IS_PART_OF.from on the existing CoreResourcePool SchemaGeneric.

    Used as the backdated ``from`` time for the new CoreIPPool SchemaGeneric and
    for the rewritten HAS_VALUE edges in Steps 4 and 5.
    """

    name = "m070_get_schema_anchor"
    type: QueryType = QueryType.READ
    insert_return: bool = False
    insert_limit: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
// ---------------
// find the CoreResourcePool Generic schema
// ---------------
MATCH (g:SchemaGeneric)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(v_name)
WHERE v_name.value = "ResourcePool"
MATCH (g)-[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[:HAS_VALUE]->(v_ns)
WHERE v_ns.value = "Core"
// ---------------
// find the time that it was created
// ---------------
MATCH (g)-[r:IS_PART_OF]->(:Root)
RETURN r.from AS anchor
ORDER BY r.from ASC
LIMIT 1
        """
        self.add_to_query(query)
        self.return_labels = ["anchor"]

    def parsed_anchor(self) -> str | None:
        if not self.results:
            return None
        return self.results[0].get_as_optional_type("anchor", return_type=str)


class CountCoreIPPoolGenericQuery(Query):
    name = "m070_count_core_ip_pool_generic"
    type: QueryType = QueryType.READ
    insert_return: bool = False
    insert_limit: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
MATCH (g:SchemaGeneric)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(v)
WHERE v.value = "IPPool"
RETURN count(g) AS total
        """
        self.add_to_query(query)
        self.return_labels = ["total"]

    def parsed_count(self) -> int:
        if not self.results:
            return 0
        return self.results[0].get_as_type("total", return_type=int)


class ReadInheritFromValuesQuery(Query):
    """Read the current ``inherit_from`` value for the two pool SchemaNodes."""

    name = "m070_read_inherit_from_values"
    type: QueryType = QueryType.READ
    insert_return: bool = False
    insert_limit: bool = False

    def __init__(self, default_branch_name: str, **kwargs: Any) -> None:
        self.default_branch_name = default_branch_name
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["pool_node_names"] = POOL_NODE_NAMES
        self.params["default_branch"] = self.default_branch_name
        query = """
// ---------------
// find the CoreIPPrefixPool and CoreIPAddressPool schemas
// ---------------
MATCH (sn:SchemaNode)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(v_name)
WHERE v_name.value IN $pool_node_names
MATCH (sn)-[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[:HAS_VALUE]->(v_ns)
WHERE v_ns.value = "Core"
// ---------------
// get the latest inherit_from value for each
// ---------------
CALL (sn) {
    MATCH (sn)-[:HAS_ATTRIBUTE]->(:Attribute {name: "inherit_from"})
        -[r:HAS_VALUE]->(av:AttributeValue)
    WHERE r.branch IN [$default_branch] AND r.status = "active"
    RETURN av.value AS inherit_from_value
    ORDER BY r.branch_level DESC, r.from DESC
    LIMIT 1
}
RETURN v_name.value AS node_name, inherit_from_value
        """
        self.add_to_query(query)
        self.return_labels = ["node_name", "inherit_from_value"]

    def parsed_rows(self) -> list[InheritFromRow]:
        rows: list[InheritFromRow] = []
        for result in self.results:
            node_name = result.get_as_type("node_name", return_type=str)
            raw_value = result.get_as_optional_type("inherit_from_value", return_type=str) or ""
            try:
                current = ujson.loads(raw_value) if raw_value else []
            except ValueError:
                console.log(f"  Skipping {node_name}.inherit_from: existing value is not valid JSON.")
                continue
            if not isinstance(current, list):
                console.log(f"  Skipping {node_name}.inherit_from: existing value is not a list.")
                continue
            rows.append(InheritFromRow(node_name=node_name, current=current))
        return rows


class BulkRewriteSchemaAttributeQuery(Query):
    """Rewrite all ``HAS_VALUE`` edges linking an Attribute to an AttributeValue.

    Each ``rewrite`` row is a :class:`SchemaAttributeRewrite`. ``parent_name`` /
    ``parent_namespace`` identify the parent SchemaNode or SchemaGeneric. When
    ``relationship_name`` is ``None`` the rewrite target is an Attribute directly
    on the parent; when set, it's the matching attribute on the SchemaRelationship
    reached via ``parent`` → IS_RELATED → SchemaRelationship.

    Idempotent: if the target ``AttributeValue`` already has ``new_value`` the
    row is a no-op. Otherwise the new edge inherits the old edge's properties
    (preserving its ``from`` time so past-timestamp queries see the new value),
    the old edge is hard-deleted, and any orphaned old ``AttributeValue`` is
    detach-deleted.
    """

    name = "m070_bulk_rewrite_schema_attribute"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False

    def __init__(
        self,
        rewrites: list[SchemaAttributeRewrite],
        default_branch_name: str,
        **kwargs: Any,
    ) -> None:
        self.rewrites = rewrites
        self.default_branch_name = default_branch_name
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["rewrites"] = [asdict(rw) for rw in self.rewrites]
        self.params["default_branch"] = self.default_branch_name
        query = """
UNWIND $rewrites AS rw
// --------------------
// all possible parent vertexes
// --------------------
MATCH (parent:SchemaNode|SchemaGeneric)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(:AttributeValue {value: rw.parent_name})
WITH DISTINCT parent, rw
CALL (parent) {
    MATCH (parent)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})
        -[r:HAS_VALUE]->(av_name:AttributeValue)
    WHERE r.branch IN [$default_branch] AND r.status = "active"
    RETURN av_name.value AS name_value
    ORDER BY r.branch_level DESC, r.from DESC
    LIMIT 1
}
CALL (parent) {
    MATCH (parent)-[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})
        -[r:HAS_VALUE]->(av_ns:AttributeValue)
    WHERE r.branch IN [$default_branch] AND r.status = "active"
    RETURN av_ns.value AS namespace_value
    ORDER BY r.branch_level DESC, r.from DESC
    LIMIT 1
}
// --------------------
// filter to the correct parent vertexes
// --------------------
WITH parent, rw, name_value, namespace_value
WHERE name_value = rw.parent_name AND namespace_value = rw.parent_namespace
// --------------------
// pick the vertex whose attribute we'll rewrite: either the parent itself
// (relationship_name is null), or the active SchemaRelationship with the
// given name/identifier. If relationship_name is set but no active path is
// found, vertex_to_update resolves to NULL and the row is dropped.
// --------------------
OPTIONAL MATCH (parent)-[r1:IS_RELATED]-(:Relationship)
    -[r2:IS_RELATED]-(sr:SchemaRelationship)
    -[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})
    -[r3:HAS_VALUE]->(:AttributeValue {value: rw.relationship_name})
WHERE rw.relationship_name IS NOT NULL
  AND r1.branch IN [$default_branch] AND r1.status = "active" AND r1.to IS NULL
  AND r2.branch IN [$default_branch] AND r2.status = "active" AND r2.to IS NULL
  AND r3.branch IN [$default_branch] AND r3.status = "active" AND r3.to IS NULL
WITH parent, rw, head(collect(DISTINCT sr)) AS sr
WITH rw,
    CASE WHEN rw.relationship_name IS NULL THEN parent ELSE sr END AS vertex_to_update
WHERE vertex_to_update IS NOT NULL
// --------------------
// get the attribute of the vertex_to_update
// --------------------
CALL (vertex_to_update, rw) {
    MATCH (vertex_to_update)-[:HAS_ATTRIBUTE]->(attr:Attribute {name: rw.attribute_name})
        -[hv_old:HAS_VALUE]->(av_old:AttributeValue)
    RETURN attr, hv_old, av_old
}
// --------------------
// update all the HAS_VALUE edges from the identified Attribute vertex to the old value
// regardless of time, branch, or active-ness
// --------------------
WITH DISTINCT rw, attr, hv_old, av_old
MERGE (av_new:AttributeValue {value: rw.new_value})
WITH attr, hv_old, av_old, av_new
WHERE av_new <> av_old
CREATE (attr)-[hv_new:HAS_VALUE]->(av_new)
SET hv_new = properties(hv_old)
DELETE hv_old
// --------------------
// detach delete orphaned AttributeValue vertices
// --------------------
WITH DISTINCT av_old
CALL (av_old) {
    WITH av_old
    WHERE NOT exists((av_old)<-[]-())
    DETACH DELETE av_old
}
        """
        self.add_to_query(query)


class CountLeftoverPoolRelationshipsQuery(Query):
    """Count Relationship vertices between IP pools and IP prefixes still using the old names.

    Constrained by peer node kinds so user-defined schemas that happen to use the
    same identifier strings on unrelated relationships don't trip the validation.
    """

    name = "m070_count_leftover_pool_relationships"
    type: QueryType = QueryType.READ
    insert_return: bool = False
    insert_limit: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["old_names"] = OLD_IDENTIFIERS
        query = """
MATCH (pool:%(pool_kind_a)s|%(pool_kind_b)s)-[:IS_RELATED]-(r:Relationship)-[:IS_RELATED]-(:%(prefix_kind)s)
WHERE r.name IN $old_names
WITH DISTINCT r
RETURN count(r) AS leftover
        """ % {
            "pool_kind_a": InfrahubKind.IPPREFIXPOOL,
            "pool_kind_b": InfrahubKind.IPADDRESSPOOL,
            "prefix_kind": InfrahubKind.IPPREFIX,
        }
        self.add_to_query(query)
        self.return_labels = ["leftover"]

    def parsed_count(self) -> int:
        if not self.results:
            return 0
        return self.results[0].get_as_type("leftover", return_type=int)


class CountUnlabeledPoolsQuery(Query):
    name = "m070_count_unlabeled_pools"
    type: QueryType = QueryType.READ
    insert_return: bool = False
    insert_limit: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
MATCH (n:%(pool_kind_a)s|%(pool_kind_b)s)
WHERE NOT n:%(ippool_kind)s
RETURN count(n) AS unlabeled
        """ % {
            "pool_kind_a": InfrahubKind.IPPREFIXPOOL,
            "pool_kind_b": InfrahubKind.IPADDRESSPOOL,
            "ippool_kind": InfrahubKind.IPPOOL,
        }
        self.add_to_query(query)
        self.return_labels = ["unlabeled"]

    def parsed_count(self) -> int:
        if not self.results:
            return 0
        return self.results[0].get_as_type("unlabeled", return_type=int)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class Migration071(ArbitraryMigration):
    """Unify the IP pool resource relationship under a new ``CoreIPPool`` generic.

    Pre-existing ``CoreIPPrefixPool`` and ``CoreIPAddressPool`` data must be reachable
    through the ``BuiltinIPPrefix.resource_pool`` relationship after this migration runs,
    *and* at every queryable past timestamp. The migration rewrites:

    * 1) ``Relationship`` vertex ``name`` from the two old identifiers to
      ``ippool__resource``.
    * 2) adds ``:CoreIPPool`` to existing pool vertices (label; non-temporal).
    * 3) bootstraps a new ``CoreIPPool`` ``SchemaGeneric`` in the schema graph
      with edge timestamps backdated to the original ``CoreResourcePool`` schema.
    * 4) appends ``CoreIPPool`` to ``inherit_from`` on both pool ``SchemaNode``
      vertices, copying old edge properties onto the new ``HAS_VALUE`` edge and hard
      deleting the old edge / orphaned ``AttributeValue``.
    * 5) rewrites the ``identifier`` value on the three ``SchemaRelationship``
      vertices (and ``peer`` on ``BuiltinIPPrefix.resource_pool``) using the same
      copy-and-hard-delete pattern.
    """

    name: str = "070_unify_ip_pool_resource_identifier"
    minimum_version: int = 69

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        leftover_query = await CountLeftoverPoolRelationshipsQuery.init(db=db)
        await leftover_query.execute(db=db)
        leftover = leftover_query.parsed_count()
        if leftover:
            result.errors.append(f"{leftover} pool↔prefix Relationship vertices still use the old identifier names")

        unlabeled_query = await CountUnlabeledPoolsQuery.init(db=db)
        await unlabeled_query.execute(db=db)
        unlabeled = unlabeled_query.parsed_count()
        if unlabeled:
            result.errors.append(f"{unlabeled} pool vertices are missing the CoreIPPool label")

        generic_query = await CountCoreIPPoolGenericQuery.init(db=db)
        await generic_query.execute(db=db)
        if not generic_query.parsed_count():
            result.errors.append("CoreIPPool SchemaGeneric was not added to the schema graph")

        return result

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        user_id = migration_input.user_id or SYSTEM_USER_ID
        async with db.start_transaction() as dbt:
            try:
                rename_query = await RenameRelationshipVerticesQuery.init(db=dbt)
                await rename_query.execute(db=dbt)

                label_query = await AddCoreIPPoolLabelQuery.init(db=dbt)
                await label_query.execute(db=dbt)

                schema_root_at = await self._get_schema_anchor_timestamp(db=dbt)
                if schema_root_at is None:
                    return MigrationResult(
                        errors=["Unable to determine an anchor timestamp from the existing schema graph"]
                    )

                await self._bootstrap_core_ip_pool_generic(db=dbt, at=schema_root_at, user_id=user_id)
                await self._append_inherit_from_for_all_pools(db=dbt)
                await self._rewrite_resource_relationship_attributes(db=dbt)
            except Exception as exc:
                error_msg = str(exc) or f"{type(exc).__name__}: {exc!r}"
                return MigrationResult(errors=[error_msg])

        return MigrationResult()

    async def _get_schema_anchor_timestamp(self, db: InfrahubDatabase) -> str | None:
        anchor_query = await GetSchemaAnchorTimestampQuery.init(db=db)
        await anchor_query.execute(db=db)
        return anchor_query.parsed_anchor()

    async def _bootstrap_core_ip_pool_generic(self, db: InfrahubDatabase, at: str, user_id: str) -> None:
        existing_query = await CountCoreIPPoolGenericQuery.init(db=db)
        await existing_query.execute(db=db)
        if existing_query.parsed_count():
            console.log("  CoreIPPool SchemaGeneric already exists; skipping bootstrap.")
            return

        if not registry.schema_has_been_initialized():
            registry.schema = SchemaManager()
            registry.schema.register_schema(schema=SchemaRoot(**internal_schema))

        default_branch = await registry.get_branch(branch=registry.default_branch, db=db)
        await registry.schema.load_node_to_db(
            node=core_ip_pool.duplicate(),
            db=db,
            branch=default_branch,
            at=Timestamp(at),
            user_id=user_id,
        )
        console.log(f"  Bootstrapped CoreIPPool SchemaGeneric with from={at}.")

    async def _append_inherit_from_for_all_pools(self, db: InfrahubDatabase) -> None:
        """Read inherit_from for both pool SchemaNodes, then rewrite the ones whose
        value doesn't yet contain ``CoreIPPool`` in a single bulk write.

        The new HAS_VALUE edge inherits the original edge's properties (incl. ``from``)
        so past-timestamp queries see the new value as if it were always there.
        """
        default_branch_name = registry.default_branch
        read_query = await ReadInheritFromValuesQuery.init(db=db, default_branch_name=default_branch_name)
        await read_query.execute(db=db)

        rewrites: list[SchemaAttributeRewrite] = []
        for row in read_query.parsed_rows():
            if InfrahubKind.IPPOOL in row.current:
                console.log(f"  {row.node_name}.inherit_from already contains {InfrahubKind.IPPOOL}; skipping.")
                continue
            rewrites.append(
                SchemaAttributeRewrite(
                    parent_name=row.node_name,
                    parent_namespace="Core",
                    attribute_name="inherit_from",
                    new_value=ujson.dumps(list(row.current) + [InfrahubKind.IPPOOL]),
                )
            )

        if not rewrites:
            return

        bulk_query = await BulkRewriteSchemaAttributeQuery.init(
            db=db, rewrites=rewrites, default_branch_name=default_branch_name
        )
        await bulk_query.execute(db=db)
        for rw in rewrites:
            console.log(f"  Appended {InfrahubKind.IPPOOL} to {rw.parent_name}.{rw.attribute_name}.")

    async def _rewrite_resource_relationship_attributes(self, db: InfrahubDatabase) -> None:
        rewrites: list[SchemaAttributeRewrite] = [
            SchemaAttributeRewrite(
                parent_name="IPPrefixPool",
                parent_namespace="Core",
                relationship_name="resources",
                attribute_name="identifier",
                new_value=NEW_IDENTIFIER,
            ),
            SchemaAttributeRewrite(
                parent_name="IPAddressPool",
                parent_namespace="Core",
                relationship_name="resources",
                attribute_name="identifier",
                new_value=NEW_IDENTIFIER,
            ),
            SchemaAttributeRewrite(
                parent_name="IPPrefix",
                parent_namespace="Builtin",
                relationship_name="resource_pool",
                attribute_name="identifier",
                new_value=NEW_IDENTIFIER,
            ),
            SchemaAttributeRewrite(
                parent_name="IPPrefix",
                parent_namespace="Builtin",
                relationship_name="resource_pool",
                attribute_name="peer",
                new_value=InfrahubKind.IPPOOL,
            ),
        ]
        default_branch_name = registry.default_branch
        bulk_query = await BulkRewriteSchemaAttributeQuery.init(
            db=db, rewrites=rewrites, default_branch_name=default_branch_name
        )
        await bulk_query.execute(db=db)
        for rw in rewrites:
            console.log(
                f"  Rewrote {rw.parent_namespace}{rw.parent_name}.{rw.relationship_name}"
                f".{rw.attribute_name} → {rw.new_value}."
            )
