from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub.core.migrations.shared import (
    ArbitraryMigration,
    MigrationInput,
    MigrationResult,
    get_migration_console,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

console = get_migration_console()


@dataclass
class DuplicatePoolGroup:
    node: str
    node_attribute: str
    survivor_uuid: str
    duplicate_uuids: list[str] = field(default_factory=list)


class Migration065(ArbitraryMigration):
    """Consolidate duplicate CoreNumberPool instances with pool_type='Schema'
    that share the same node + node_attribute combination.

    Keeps the earliest pool (by creation timestamp) and moves all
    IS_RESERVED and HAS_SOURCE relationships to it. Hard-deletes the duplicate pools
    Updates any NumberPoolParameters on SchemaAttributes that reference a deleted CoreNumberPool
    """

    name: str = "065_consolidate_duplicate_number_pools"
    minimum_version: int = 64

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        async with db.start_transaction() as dbt:
            try:
                duplicate_groups = await self._find_duplicate_groups(db=dbt)
                if not duplicate_groups:
                    console.log("No duplicate CoreNumberPool instances found.")
                    return MigrationResult()

                console.log(f"Found {len(duplicate_groups)} duplicate pool group(s) to consolidate.")

                pool_id_map: dict[str, str] = {}
                for group in duplicate_groups:
                    console.log(
                        f"Consolidating pools for node={group.node}, "
                        f"node_attribute={group.node_attribute}: "
                        f"keeping {group.survivor_uuid}, removing {group.duplicate_uuids}"
                    )

                    await self._reassign_is_reserved(
                        db=dbt, survivor_uuid=group.survivor_uuid, duplicate_uuids=group.duplicate_uuids
                    )
                    await self._reassign_has_source(
                        db=dbt, survivor_uuid=group.survivor_uuid, duplicate_uuids=group.duplicate_uuids
                    )
                    await self._delete_duplicate_pools(db=dbt, duplicate_uuids=group.duplicate_uuids)

                    for dup_uuid in group.duplicate_uuids:
                        pool_id_map[dup_uuid] = group.survivor_uuid

                await self._update_schema_parameters(db=dbt, pool_id_map=pool_id_map)

            except Exception as exc:
                error_msg = str(exc) or f"{type(exc).__name__}: {repr(exc)}"
                return MigrationResult(errors=[error_msg])

        return MigrationResult()

    async def _find_duplicate_groups(self, db: InfrahubDatabase) -> list[DuplicatePoolGroup]:
        """Find groups of duplicate Schema-type CoreNumberPools sharing the same node + node_attribute."""
        query = """
        MATCH (pool:CoreNumberPool)

        // -------------------------------------------
        // Get latest IS_PART_OF edge; skip pool if deleted
        // -------------------------------------------
        CALL (pool) {
            MATCH (pool)-[r_ipo:IS_PART_OF]->(root:Root)
            RETURN r_ipo
            ORDER BY r_ipo.from DESC
            LIMIT 1
        }
        WITH pool, r_ipo
        WHERE r_ipo.status = "active"

        // -------------------------------------------
        // Get latest pool_type; skip if deleted or not "Schema"
        // -------------------------------------------
        CALL (pool) {
            MATCH (pool)-[r1:HAS_ATTRIBUTE]->(attr_pt:Attribute {name: "pool_type"})-[r2:HAS_VALUE]->(av_pt)
            RETURN r1.status = "active" AND r2.status= "active" AS is_active, av_pt.value AS pool_type
            ORDER BY r1.from DESC, r1.status ASC, r2.from DESC, r2.status ASC
            LIMIT 1
        }
        WITH pool, r_ipo, is_active, pool_type
        WHERE is_active AND pool_type = "Schema"

        // -------------------------------------------
        // Get latest node and node_attribute values
        // almost no filtering is required
        // b/c the schema is branch-agnostic and the attribute is mandatory
        // -------------------------------------------
        CALL (pool) {
            MATCH (pool)-[r1:HAS_ATTRIBUTE]->(attr_n:Attribute {name: "node"})-[r2:HAS_VALUE]->(av_n)
            RETURN av_n.value AS node_value
            ORDER BY r1.from DESC, r2.from DESC
            LIMIT 1
        }
        CALL (pool) {
            MATCH (pool)-[r1:HAS_ATTRIBUTE]->(attr_n:Attribute {name: "node_attribute"})-[r2:HAS_VALUE]->(av_na)
            RETURN av_na.value AS node_attribute_value
            ORDER BY r1.from DESC, r2.from DESC
            LIMIT 1
        }

        WITH pool.uuid AS pool_uuid,
            r_ipo.from AS created_at,
            node_value,
            node_attribute_value
        ORDER BY node_value, node_attribute_value, created_at ASC

        WITH node_value,
            node_attribute_value,
            collect(pool_uuid) AS chronological_pool_ids
        WHERE size(chronological_pool_ids) > 1

        RETURN node_value,
               node_attribute_value,
               chronological_pool_ids[0] AS survivor_uuid,
               chronological_pool_ids[1..] AS duplicate_uuids
        """

        results = await db.execute_query(query=query, name="find_duplicate_number_pools")

        return [
            DuplicatePoolGroup(
                node=record["node_value"],
                node_attribute=record["node_attribute_value"],
                survivor_uuid=record["survivor_uuid"],
                duplicate_uuids=list(record["duplicate_uuids"]),
            )
            for record in results
        ]

    async def _reassign_is_reserved(self, db: InfrahubDatabase, survivor_uuid: str, duplicate_uuids: list[str]) -> None:
        """Move IS_RESERVED relationships from duplicate pools to the surviving pool."""
        query = """
        MATCH (survivor:CoreNumberPool {uuid: $survivor_uuid})
        MATCH (dup_pool:CoreNumberPool)-[old_res:IS_RESERVED]->(target)
        WHERE dup_pool.uuid IN $duplicate_uuids

        CREATE (survivor)-[new_res:IS_RESERVED]->(target)
        SET new_res = properties(old_res)
        DELETE old_res

        RETURN count(new_res) AS moved_count
        """

        results = await db.execute_query(
            query=query,
            params={"survivor_uuid": survivor_uuid, "duplicate_uuids": duplicate_uuids},
            name="reassign_is_reserved",
        )

        if results and results[0]["moved_count"]:
            console.log(f"  Moved {results[0]['moved_count']} IS_RESERVED relationship(s) to survivor pool.")

    async def _reassign_has_source(self, db: InfrahubDatabase, survivor_uuid: str, duplicate_uuids: list[str]) -> None:
        """Move HAS_SOURCE relationships from duplicate pools to the surviving pool."""
        query = """
        MATCH (survivor:CoreNumberPool {uuid: $survivor_uuid})
        MATCH (attr:Attribute)-[old_hs:HAS_SOURCE]->(dup_pool:CoreNumberPool)
        WHERE dup_pool.uuid IN $duplicate_uuids

        CREATE (attr)-[new_hs:HAS_SOURCE]->(survivor)
        SET new_hs = properties(old_hs)
        DELETE old_hs

        RETURN count(new_hs) AS moved_count
        """

        results = await db.execute_query(
            query=query,
            params={"survivor_uuid": survivor_uuid, "duplicate_uuids": duplicate_uuids},
            name="reassign_has_source",
        )

        if results and results[0]["moved_count"]:
            console.log(f"  Moved {results[0]['moved_count']} HAS_SOURCE relationship(s) to survivor pool.")

    async def _update_schema_parameters(self, db: InfrahubDatabase, pool_id_map: dict[str, str]) -> None:
        """Update SchemaAttribute parameters JSON where number_pool_id matches a deleted pool.

        Args:
            pool_id_map: Mapping of {duplicate_uuid: survivor_uuid} for all pools to replace.
        """
        query = """
        // -------------------------------------------
        // no edge filtering required b/c we can count on the CONTAINS UUID filter
        // -------------------------------------------
        UNWIND $replacements AS replacement
        WITH replacement.dup_uuid AS dup_uuid, replacement.survivor_uuid AS survivor_uuid

        CALL (dup_uuid, survivor_uuid) {
            MATCH (sa:SchemaAttribute)-[:HAS_ATTRIBUTE]->(kind_attr:Attribute {name: "kind"})
                -[:HAS_VALUE]->(kind_val:AttributeValue {value: "NumberPool"})
            MATCH (sa)-[:HAS_ATTRIBUTE]->(param_attr:Attribute {name: "parameters"})
                -[:HAS_VALUE]->(param_val:AttributeValue)
            WHERE param_val.value CONTAINS dup_uuid

            SET param_val.value = replace(param_val.value, dup_uuid, survivor_uuid)
            RETURN 1 AS _dummy
        }

        RETURN count(*) AS updated_count
        """

        replacements = [{"dup_uuid": dup, "survivor_uuid": surv} for dup, surv in pool_id_map.items()]

        results = await db.execute_query(
            query=query,
            params={"replacements": replacements},
            name="update_schema_params_pool_id",
        )

        if results and results[0]["updated_count"]:
            console.log(f"  Updated {results[0]['updated_count']} SchemaAttribute parameter(s).")

    async def _delete_duplicate_pools(self, db: InfrahubDatabase, duplicate_uuids: list[str]) -> None:
        """Hard-delete duplicate pool nodes and their attribute sub-graphs."""
        query = """
        // ---------------------
        // only Attribute deletes are necessary b/c CoreNumberPool has no Relatonships
        // ---------------------
        MATCH (pool:CoreNumberPool)
        WHERE pool.uuid IN $duplicate_uuids
        OPTIONAL MATCH (pool)-[:HAS_ATTRIBUTE]->(attr:Attribute)

        DETACH DELETE attr, pool
        """

        await db.execute_query(
            query=query,
            params={"duplicate_uuids": duplicate_uuids},
            name="delete_duplicate_pools",
        )

        console.log(f"  Hard-deleted {len(duplicate_uuids)} duplicate pool node(s).")
