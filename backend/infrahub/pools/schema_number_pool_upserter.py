from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub import lock
from infrahub.core.constants import SYSTEM_USER_ID, InfrahubKind, NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.pools.models import NumberPoolLockDefinition

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.attribute_schema import AttributeSchema
    from infrahub.core.schema.manager import SchemaManager
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


@dataclass
class InheritedPoolInfo:
    pool_id: str | None
    generic_kind: str


class SchemaNumberPoolUpserter:
    """Gets or creates CoreNumberPool instances for schema-defined number pools.

    This class provides two main public methods:
    - get_existing_number_pool_id: Returns the ID of an existing pool, or None
    - upsert_number_pool: Returns a CoreNumberPool, creating it if necessary

    It handles inherited attributes by looking up the pool from the generic
    that defines the attribute.

    Args:
        db: Database connection.
        schema_manager: Schema manager for looking up schemas.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        schema_manager: SchemaManager,
    ) -> None:
        self.db = db
        self.schema_manager = schema_manager
        self._cache: dict[str, CoreNumberPool] = {}

    async def get_existing_number_pool_id(
        self,
        schema_node: MainSchemaTypes,
        attribute: AttributeSchema,
        branch_name: str,
        schema_branch: SchemaBranch | None = None,
    ) -> str | None:
        """Get the ID of an existing CoreNumberPool for a NumberPool attribute.

        Handles inheritance by checking the generic that defines the attribute.

        Args:
            schema_node: The schema containing the NumberPool attribute.
            attribute: The NumberPool attribute schema.
            branch_name: Branch name for schema lookups.
            schema_branch: Optional SchemaBranch to use for lookups (avoids re-fetching).

        Returns:
            The pool ID if found, None otherwise.
        """
        # If pool_id is already set on the attribute, return it
        if isinstance(attribute.parameters, NumberPoolParameters) and attribute.parameters.number_pool_id:
            return attribute.parameters.number_pool_id

        # For inherited attributes on nodes, check the generic first
        if attribute.inherited and isinstance(schema_node, NodeSchema):
            inherited_info = self.get_inherited_pool_info(
                node_schema=schema_node,
                attribute_name=attribute.name,
                branch_name=branch_name,
                schema_branch=schema_branch,
            )
            if inherited_info and inherited_info.pool_id:
                return inherited_info.pool_id

        return None

    async def upsert_number_pool(
        self,
        schema_node: MainSchemaTypes,
        attribute: AttributeSchema,
        branch_name: str,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
        schema_branch: SchemaBranch | None = None,
    ) -> CoreNumberPool:
        """Get or create a CoreNumberPool for a NumberPool attribute.

        Check for an existing pool.
        If found, retrieves the pool using registry.manager.get_one().
        If not found, creates a new pool with appropriate node and node_attribute values.

        Args:
            schema_node: The schema containing the NumberPool attribute.
            attribute: The NumberPool attribute schema.
            branch_name: Branch name for schema lookups.
            at: Optional timestamp for pool creation (used for consistency in migrations).
            user_id: The user ID to use for save operations.
            schema_branch: Optional SchemaBranch to use for lookups (avoids re-fetching).

        Returns:
            The CoreNumberPool instance.

        Raises:
            ValueError: If the attribute is not a NumberPool type.
        """
        if not isinstance(attribute.parameters, NumberPoolParameters):
            raise ValueError(f"Attribute {attribute.name} on {schema_node.kind} is not a NumberPool type")

        # Check for existing pool
        pool_id = await self.get_existing_number_pool_id(
            schema_node=schema_node,
            attribute=attribute,
            branch_name=branch_name,
            schema_branch=schema_branch,
        )

        if pool_id:
            # Pool exists, retrieve it
            return await self._get_by_id(pool_id)

        # No existing pool, create one with distributed lock to prevent race conditions
        pool_kind = self._get_pool_kind(schema_node, attribute, branch_name, schema_branch=schema_branch)
        lock_definition = NumberPoolLockDefinition(schema_kind=pool_kind, attribute_name=attribute.name)

        async with lock.registry.get(
            name=lock_definition.lock_name, namespace=lock_definition.namespace_name, local=False
        ):
            # Double-check after acquiring lock (race condition protection)
            existing_pools = await NodeManager.query(
                db=self.db,
                schema=CoreNumberPool,
                filters={
                    "node__value": pool_kind,
                    "node_attribute__value": attribute.name,
                    "pool_type__value": NumberPoolType.SCHEMA.value,
                },
                branch_agnostic=True,
            )

            if existing_pools:
                pool = existing_pools[0]
                self._cache[pool.id] = pool
                return pool

            # Create new pool
            number_pool_id = str(uuid4())
            number_pool = await Node.init(db=self.db, schema=InfrahubKind.NUMBERPOOL)
            await number_pool.new(
                db=self.db,
                id=number_pool_id,
                name=f"{pool_kind}.{attribute.name} [{number_pool_id}]",
                node=pool_kind,
                node_attribute=attribute.name,
                start_range=attribute.parameters.start_range,
                end_range=attribute.parameters.end_range,
                pool_type=NumberPoolType.SCHEMA.value,
            )
            await number_pool.save(db=self.db, at=at, user_id=user_id)

            # Re-fetch using _get_by_id to get the proper CoreNumberPool instance with its methods
            return await self._get_by_id(number_pool_id)

    def get_inherited_pool_info(
        self,
        node_schema: MainSchemaTypes,
        attribute_name: str,
        branch_name: str,
        schema_branch: SchemaBranch | None = None,
    ) -> InheritedPoolInfo | None:
        """Look up pool info from the generic that defines this inherited attribute.

        Args:
            node_schema: The node schema with the inherited attribute.
            attribute_name: The name of the inherited attribute.
            branch_name: The branch name to look up generics from.
            schema_branch: Optional SchemaBranch to use for lookups (avoids re-fetching).

        Returns:
            InheritedPoolInfo if the generic is found, None otherwise.
            The pool_id may be None if the generic hasn't been assigned a pool yet.
        """
        if not isinstance(node_schema, NodeSchema):
            return None
        if schema_branch is None:
            schema_branch = self.schema_manager.get_schema_branch(name=branch_name)
        for generic_name in node_schema.inherit_from:
            generic_schema = schema_branch.get_generic(name=generic_name, duplicate=False)
            if attribute_name in generic_schema.attribute_names:
                generic_attr = generic_schema.get_attribute(name=attribute_name)
                if isinstance(generic_attr.parameters, NumberPoolParameters):
                    return InheritedPoolInfo(
                        pool_id=generic_attr.parameters.number_pool_id, generic_kind=generic_schema.kind
                    )

        return None

    def _get_pool_kind(
        self,
        schema_node: MainSchemaTypes,
        attribute: AttributeSchema,
        branch_name: str,
        schema_branch: SchemaBranch | None = None,
    ) -> str:
        """Determine the kind to use for pool creation/lookup.

        For inherited attributes on NodeSchema, returns the generic kind.
        Otherwise returns the schema_node's kind.
        """
        if attribute.inherited and isinstance(schema_node, NodeSchema):
            inherited_info = self.get_inherited_pool_info(
                node_schema=schema_node,
                attribute_name=attribute.name,
                branch_name=branch_name,
                schema_branch=schema_branch,
            )
            if inherited_info:
                return inherited_info.generic_kind
        return schema_node.kind

    async def _get_by_id(self, pool_id: str) -> CoreNumberPool:
        """Retrieve a CoreNumberPool by its ID.

        Args:
            pool_id: The ID of the CoreNumberPool to retrieve.

        Returns:
            The CoreNumberPool instance.

        Raises:
            NodeNotFoundError: If pool not found.
        """
        if pool_id in self._cache:
            return self._cache[pool_id]

        pool = await registry.manager.get_one(
            db=self.db,
            id=pool_id,
            kind=CoreNumberPool,
            branch_agnostic=True,
            raise_on_error=True,
        )

        self._cache[pool_id] = pool
        return pool
