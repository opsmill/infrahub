from __future__ import annotations

from typing import TYPE_CHECKING, cast

from infrahub.core.constants import SYSTEM_USER_ID, NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.log import get_logger
from infrahub.pools.registration import get_branches_with_schema_number_pool

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

    from structlog.stdlib import BoundLogger

    from infrahub.core.schema import GenericSchema, NodeSchema
    from infrahub.core.schema.manager import SchemaManager
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter

default_log = get_logger()


class SchemaNumberPoolSynchronizer:
    """Synchronizes schema-defined number pools.

    This class handles the lifecycle of CoreNumberPool instances that are defined
    via NumberPool attributes in the schema. It ensures pools are created, updated,
    or deleted as the schema changes across branches.

    Args:
        db: Database connection.
        log: Logger instance.
        schema_manager: Schema manager for looking up schemas.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        schema_manager: SchemaManager,
        upserter: SchemaNumberPoolUpserter,
        log: Logger | LoggerAdapter | BoundLogger | None = None,
    ) -> None:
        self.db = db
        self.log = log or default_log
        self.schema_manager = schema_manager
        self.existing_pool_ids: set[str] = set()
        self.upserter = upserter

    async def run(self, user_id: str = SYSTEM_USER_ID) -> None:
        """Execute the full synchronization process."""
        await self._load_existing_pools()
        await self._sync_existing_pools_with_schema(user_id=user_id)
        await self._process_all_branches(user_id=user_id)

    async def _load_existing_pools(self) -> None:
        """Load all existing schema-type number pools."""
        async with self.db.start_session() as dbs:
            schema_number_pools = await NodeManager.query(
                db=dbs,
                schema=CoreNumberPool,
                filters={"pool_type__value": NumberPoolType.SCHEMA.value},
                branch_agnostic=True,
            )
        self.existing_pool_ids = {pool.id for pool in schema_number_pools}
        self._schema_number_pools = list(schema_number_pools)

    async def _sync_existing_pools_with_schema(self, user_id: str) -> None:
        """Update or delete existing pools based on current schema definitions."""
        schema_number_pools = await NodeManager.query(
            db=self.db,
            schema=CoreNumberPool,
            filters={"pool_type__value": NumberPoolType.SCHEMA.value},
            branch_agnostic=True,
        )
        for schema_number_pool in schema_number_pools:
            defined_on_branches = get_branches_with_schema_number_pool(
                kind=schema_number_pool.node.value, attribute_name=schema_number_pool.node_attribute.value
            )
            if registry.default_branch in defined_on_branches:
                await self._update_pool_from_schema(schema_number_pool, user_id=user_id)
            elif not defined_on_branches:
                self.log.info(
                    f"Deleting number pool (id={schema_number_pool.id}) as it is no longer defined in the schema"
                )
                await schema_number_pool.delete(db=self.db, user_id=user_id)

    async def _update_pool_from_schema(self, schema_number_pool: CoreNumberPool, user_id: str = SYSTEM_USER_ID) -> None:
        """Update a pool's range parameters if they differ from the schema."""
        schema = self.schema_manager.get(
            name=schema_number_pool.node.value, branch=registry.default_branch, duplicate=False
        )
        attribute = schema.get_attribute(name=schema_number_pool.node_attribute.value)
        number_pool_updated = False

        if isinstance(attribute.parameters, NumberPoolParameters):
            if schema_number_pool.start_range.value != attribute.parameters.start_range:
                schema_number_pool.start_range.value = attribute.parameters.start_range
                number_pool_updated = True
            if schema_number_pool.end_range.value != attribute.parameters.end_range:
                schema_number_pool.end_range.value = attribute.parameters.end_range
                number_pool_updated = True

        if number_pool_updated:
            self.log.info(
                f"Updating NumberPool={schema_number_pool.id} based on changes in the schema on {registry.default_branch}"
            )
            await schema_number_pool.save(db=self.db, user_id=user_id)

    async def _process_all_branches(self, user_id: str) -> None:
        """Process all branches to create any missing number pools."""
        for branch_name in self.schema_manager.get_branches():
            schemas_to_update: list[str] = []
            schema_branch = self.schema_manager.get_schema_branch(name=branch_name)

            # Process generics first so their pool IDs are available for inheriting nodes
            for generic_name in schema_branch.generic_names:
                generic_schema = schema_branch.get_generic(name=generic_name, duplicate=False)
                updated_schema = await self._process_schema_node(
                    schema_node=generic_schema,
                    branch_name=branch_name,
                    schema_branch=schema_branch,
                    user_id=user_id,
                )
                if updated_schema:
                    schema_branch.set(name=generic_schema.kind, schema=updated_schema)
                    schemas_to_update.append(generic_schema.kind)

            # Process nodes after generics - inherited attributes will look up pool IDs from generics
            for node_name in schema_branch.node_names:
                node_schema = schema_branch.get_node(name=node_name, duplicate=False)
                updated_schema = await self._process_schema_node(
                    schema_node=node_schema,
                    branch_name=branch_name,
                    schema_branch=schema_branch,
                    user_id=user_id,
                )
                if updated_schema:
                    schema_branch.set(name=node_schema.kind, schema=updated_schema)
                    schemas_to_update.append(node_schema.kind)

            if schemas_to_update:
                self.log.info(f"Persisting schema changes to the database on {branch_name}")
                await self.schema_manager.update_schema_branch(
                    db=self.db, branch=branch_name, schema=schema_branch, limit=schemas_to_update, update_db=True
                )

    async def _process_schema_node(
        self,
        schema_node: NodeSchema | GenericSchema,
        branch_name: str,
        schema_branch: SchemaBranch,
        user_id: str,
    ) -> NodeSchema | GenericSchema | None:
        """Process NumberPool attributes for a schema node, creating pools as needed.

        Args:
            schema_node: The schema node to process.
            branch_name: The branch name for schema lookups.
            schema_branch: The SchemaBranch for schema lookups.
            user_id: The user ID for any save operations.

        Returns a NodeSchema or GenericSchema if the schema was updated.
        """
        updated_schema: NodeSchema | GenericSchema | None = None

        for attribute_name in schema_node.attribute_names:
            attribute = schema_node.get_attribute(name=attribute_name)
            if not isinstance(attribute.parameters, NumberPoolParameters):
                continue

            if attribute.parameters.number_pool_id:
                # Pool ID already exists, so the pool exists, move on
                continue

            # Try to get existing pool ID
            new_pool_id = await self.upserter.get_existing_number_pool_id(
                schema_node=schema_node,
                attribute=attribute,
                branch_name=branch_name,
                schema_branch=schema_branch,
            )

            # If no pool ID, create one
            if not new_pool_id:
                new_pool = await self.upserter.upsert_number_pool(
                    schema_node=schema_node,
                    attribute=attribute,
                    branch_name=branch_name,
                    schema_branch=schema_branch,
                    user_id=user_id,
                )
                new_pool_id = new_pool.id

            self.log.info(f"Setting {schema_node.kind}.{attribute_name} number_pool_id to {new_pool_id}")
            if not updated_schema:
                updated_schema = schema_node.duplicate()
            updated_attribute = updated_schema.get_attribute(name=attribute_name)
            attribute_parameters = cast("NumberPoolParameters", updated_attribute.parameters)
            attribute_parameters.number_pool_id = new_pool_id

        return updated_schema
