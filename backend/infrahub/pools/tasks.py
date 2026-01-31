from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

from prefect import flow
from prefect.logging import get_run_logger

from infrahub import lock
from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core.constants import InfrahubKind, NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.exceptions import NodeNotFoundError
from infrahub.pools.models import NumberPoolLockDefinition
from infrahub.pools.registration import get_branches_with_schema_number_pool
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

    from structlog.stdlib import BoundLogger

    from infrahub.core.schema import GenericSchema, MainSchemaTypes, NodeSchema
    from infrahub.core.schema.attribute_schema import AttributeSchema
    from infrahub.core.schema.manager import SchemaManager
    from infrahub.database import InfrahubDatabase


class SchemaNumberPoolValidator:
    """Validates and manages schema-defined number pools.

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
        log: Logger | LoggerAdapter | BoundLogger,
        schema_manager: SchemaManager,
    ) -> None:
        self.db = db
        self.log = log
        self.schema_manager = schema_manager
        self.existing_pool_ids: set[str] = set()
        self._schema_number_pools: list[CoreNumberPool] = []

    async def run(self) -> None:
        """Execute the full validation process."""
        await self._load_existing_pools()
        await self._sync_existing_pools_with_schema()
        await self._process_all_branches()

    async def ensure_pool_for_attribute(
        self,
        schema_node: MainSchemaTypes,
        attribute: AttributeSchema,
    ) -> str:
        """Create or find a number pool for a specific schema attribute.

        Args:
            schema_node: The schema containing the NumberPool attribute.
            attribute: The NumberPool SchemaAttribute.

        Returns:
            The pool ID for the created/found pool.

        Raises:
            ValueError: If the attribute is not a NumberPool type.
        """
        if not isinstance(attribute.parameters, NumberPoolParameters):
            raise ValueError(f"Attribute {attribute.name} on {schema_node.kind} is not a NumberPool type")

        # Ensure existing pools are loaded
        if not self.existing_pool_ids and not self._schema_number_pools:
            await self._load_existing_pools()

        # Check if pool already exists with the expected ID
        if attribute.parameters.number_pool_id and attribute.parameters.number_pool_id in self.existing_pool_ids:
            return attribute.parameters.number_pool_id

        # Create or find the pool
        pool_id = await self._get_or_create_number_pool(
            number_pool_id=attribute.parameters.number_pool_id,
            pool_node=schema_node.kind,
            pool_attribute=attribute.name,
            start_range=attribute.parameters.start_range,
            end_range=attribute.parameters.end_range,
        )

        self.existing_pool_ids.add(pool_id)
        return pool_id

    async def _load_existing_pools(self) -> None:
        """Load all existing schema-type number pools."""
        async with self.db.start_session() as dbs:
            schema_number_pools = await NodeManager.query(
                db=dbs, schema=CoreNumberPool, filters={"pool_type__value": NumberPoolType.SCHEMA.value}
            )
        self.existing_pool_ids = {pool.id for pool in schema_number_pools}
        self._schema_number_pools = list(schema_number_pools)

    async def _sync_existing_pools_with_schema(self) -> None:
        """Update or delete existing pools based on current schema definitions."""
        for schema_number_pool in self._schema_number_pools:
            defined_on_branches = get_branches_with_schema_number_pool(
                kind=schema_number_pool.node.value, attribute_name=schema_number_pool.node_attribute.value
            )
            if registry.default_branch in defined_on_branches:
                await self._update_pool_from_schema(schema_number_pool)
            elif not defined_on_branches:
                self.log.info(
                    f"Deleting number pool (id={schema_number_pool.id}) as it is no longer defined in the schema"
                )
                await schema_number_pool.delete(db=self.db)

    async def _update_pool_from_schema(self, schema_number_pool: CoreNumberPool) -> None:
        """Update a pool's range parameters if they differ from the schema."""
        schema = self.schema_manager.get(name=schema_number_pool.node.value, branch=registry.default_branch)
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
            await schema_number_pool.save(db=self.db)

    async def _process_all_branches(self) -> None:
        """Process all branches to create any missing number pools."""
        for branch_name in self.schema_manager.get_branches():
            schemas_to_update: list[str] = []
            schema_branch = self.db.schema.get_schema_branch(name=branch_name)

            for generic_name in schema_branch.generic_names:
                generic_schema = schema_branch.get_generic(name=generic_name, duplicate=False)
                updated_schema = await self._process_schema_node(schema_node=generic_schema)
                if updated_schema:
                    schema_branch.set(name=generic_schema.kind, schema=updated_schema)
                    schemas_to_update.append(generic_schema.kind)

            for node_name in schema_branch.node_names:
                node_schema = schema_branch.get_node(name=node_name, duplicate=False)
                updated_schema = await self._process_schema_node(schema_node=node_schema)
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
    ) -> NodeSchema | GenericSchema | None:
        """Process NumberPool attributes for a schema node, creating pools as needed.

        Returns a NodeSchema or GenericSchema if the schema was updated.
        """
        updated_schema: NodeSchema | GenericSchema | None = None

        for attribute_name in schema_node.attribute_names:
            attribute = schema_node.get_attribute(name=attribute_name)
            if not isinstance(attribute.parameters, NumberPoolParameters):
                continue

            original_pool_id = attribute.parameters.number_pool_id
            actual_pool_id = await self.ensure_pool_for_attribute(
                schema_node=schema_node,
                attribute=attribute,
            )

            if actual_pool_id != original_pool_id:
                self.log.info(
                    f"Updating {schema_node.kind}.{attribute_name} number_pool_id "
                    f"from {original_pool_id} to {actual_pool_id}"
                )
                if not updated_schema:
                    updated_schema = schema_node.duplicate()
                updated_attribute = updated_schema.get_attribute(name=attribute_name)
                attribute_parameters = cast("NumberPoolParameters", updated_attribute.parameters)
                attribute_parameters.number_pool_id = actual_pool_id

        return updated_schema

    async def _get_or_create_number_pool(
        self,
        number_pool_id: str | None,
        pool_node: str,
        pool_attribute: str,
        start_range: int,
        end_range: int,
    ) -> str:
        """Create or find an existing number pool.

        Returns the actual pool ID, which may be different from number_pool_id if an existing pool was found.
        """
        lock_definition = NumberPoolLockDefinition(schema_kind=pool_node, attribute_name=pool_attribute)
        async with lock.registry.get(
            name=lock_definition.lock_name, namespace=lock_definition.namespace_name, local=False
        ):
            async with self.db.start_session() as dbs:
                if number_pool_id:
                    try:
                        await registry.manager.get_one_by_id_or_default_filter(
                            db=dbs, id=str(number_pool_id), kind=CoreNumberPool
                        )
                        return number_pool_id
                    except NodeNotFoundError:
                        pass

                else:
                    number_pool_id = str(uuid4())

                existing_pools = await NodeManager.query(
                    db=dbs,
                    schema=CoreNumberPool,
                    filters={
                        "node__value": pool_node,
                        "node_attribute__value": pool_attribute,
                        "pool_type__value": NumberPoolType.SCHEMA.value,
                    },
                    branch_agnostic=True,
                )
                if existing_pools:
                    return existing_pools[0].id

                number_pool = await Node.init(db=dbs, schema=InfrahubKind.NUMBERPOOL, branch=registry.default_branch)
                await number_pool.new(
                    db=dbs,
                    id=number_pool_id,
                    name=f"{pool_node}.{pool_attribute} [{number_pool_id}]",
                    node=pool_node,
                    node_attribute=pool_attribute,
                    start_range=start_range,
                    end_range=end_range,
                    pool_type=NumberPoolType.SCHEMA.value,
                )
                await number_pool.save(db=dbs)
                return number_pool_id


@flow(
    name="validate-schema-number-pools",
    flow_run_name="Validate schema number pools on {branch_name}",
)
async def validate_schema_number_pools(
    branch_name: str,  # noqa: ARG001
    context: InfrahubContext,  # noqa: ARG001
    service: InfrahubServices,
) -> None:
    log = get_run_logger()
    validator = SchemaNumberPoolValidator(
        db=service.database,
        log=log,
        schema_manager=registry.schema,
    )
    await validator.run()
