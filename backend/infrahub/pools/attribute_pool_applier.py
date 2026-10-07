from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, assert_never

from infrahub.core.attribute import PayloadPresence
from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
from infrahub.core.query.resource_manager import PoolRecordProvenance
from infrahub.core.schema import TemplateSchema
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.exceptions import InitializationError, NodeNotFoundError, PoolExhaustedError, ValidationError
from infrahub.pools.intent import FromPoolIntent, FromPoolIntentResolver, FromPoolRequest, Sent

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNumberPool
    from infrahub.core.schema import NonGenericSchemaTypes


class NumberPoolFinder(Protocol):
    async def find(self, pool_ref: str) -> CoreNumberPool:
        """Return the number pool whose id or name is `pool_ref`.

        Raises:
            NodeNotFoundError: When no number pool has that id or name.

        """
        ...

    async def get_tracking_pool_id(self, attribute_id: str) -> str | None:
        """Return the id of the number pool currently tracking the attribute, or None when none does."""
        ...


class AttributeNumberAllocator(Protocol):
    async def allocate(self, pool: CoreNumberPool, node: Node, attribute: BaseAttribute, user_id: str) -> int:
        """Return the number the pool gives the attribute.

        Raises:
            PoolExhaustedError: When the pool has no number left to give.

        """
        ...

    async def attach(self, pool: CoreNumberPool, node: Node, attribute: BaseAttribute, user_id: str) -> None:
        """Have the pool track the number the saved attribute already holds."""
        ...

    async def release(self, attribute: BaseAttribute, user_id: str) -> None:
        """Have every pool stop tracking the saved attribute, which keeps the number it holds."""
        ...


class AttributePoolApplierInterface(Protocol):
    async def apply(
        self,
        node: Node,
        attribute: BaseAttribute,
        allocate: bool,
        user_id: str,
    ) -> None:
        """Apply what a write naming a number pool on the attribute asks for.

        Raises:
            ValidationError: When the attribute cannot draw from or be tracked by the pool it names.

        """
        ...


class LoadedNodePoolApplier:
    """Stands in for the applier on a node loaded from the database, which never draws from a pool."""

    async def apply(
        self,
        node: Node,
        attribute: BaseAttribute,
        allocate: bool,  # noqa: ARG002
        user_id: str,  # noqa: ARG002
    ) -> None:
        """Refuse, since reaching this means a loaded node was asked to draw a number.

        Raises:
            InitializationError: Always.

        """
        raise InitializationError(f"The loaded node {node.get_id()} cannot draw '{attribute.name}' from a pool")


class AttributePoolApplier:
    """Apply what a write naming a number pool on an attribute asks for.

    A NumberPool attribute always draws from the pool its schema declares. On any other Number attribute,
    what `from_pool` means depends on the `value` sent with it and on the pool already tracking the attribute.
    """

    def __init__(
        self,
        pool_finder: NumberPoolFinder,
        number_allocator: AttributeNumberAllocator,
        intent_resolver: FromPoolIntentResolver,
    ) -> None:
        self.pool_finder = pool_finder
        self.number_allocator = number_allocator
        self.intent_resolver = intent_resolver

    async def apply(
        self,
        node: Node,
        attribute: BaseAttribute,
        allocate: bool,
        user_id: str,
    ) -> None:
        """Apply what a write naming a number pool on the attribute asks for.

        Without `allocate` only the pool is resolved, so the lock names can be computed.

        Raises:
            ValidationError: When `from_pool` is used on a template, when no pool ID is provided, when the
                pool is not provisioned or cannot be found, when the pool cannot be used for the attribute,
                when the pool is exhausted, or when `from_pool` alone names a pool over a non-default
                number the attribute holds and that pool does not already track it.

        """
        schema = node.get_schema()
        if isinstance(schema, TemplateSchema) and attribute.from_pool:
            pool_rel_name = f"{attribute.name}{RESOURCE_POOL_REL_SUFFIX}"
            raise ValidationError(
                {
                    f"{attribute.name}.from_pool": (
                        f"'from_pool' is not supported on template attributes. Set the '{pool_rel_name}' relationship on this template instead."
                    )
                }
            )

        if attribute.schema.kind == "NumberPool" and isinstance(attribute.schema.parameters, NumberPoolParameters):
            await self._apply_schema_number_pool(
                node=node,
                attribute=attribute,
                pool_id=attribute.schema.parameters.number_pool_id,
                allocate=allocate,
                user_id=user_id,
            )
            return

        pool: CoreNumberPool | None = None
        if attribute.from_pool:
            pool_ref = attribute.from_pool.get("id")
            if not pool_ref:
                raise ValidationError({f"{attribute.name}.from_pool": "No pool ID specified in from_pool."})
            pool = await self._find_pool(attribute=attribute, pool_ref=pool_ref)
            # Get the pool's ID in case it was referenced by name.
            attribute.from_pool = {"id": pool.get_id()}

        if not allocate or attribute.from_pool_presence is PayloadPresence.ABSENT:
            return

        if pool is not None:
            self._check_pool_targets_attribute(schema=schema, pool=pool, attribute=attribute)

        tracking_pool_id: str | None = None
        if attribute.id is not None:
            tracking_pool_id = await self.pool_finder.get_tracking_pool_id(attribute_id=attribute.id)

        number = self._get_number(attribute=attribute)
        intent = self.intent_resolver.resolve(
            request=FromPoolRequest(
                value=None if attribute.value_presence is PayloadPresence.ABSENT else Sent(value=number),
                from_pool=Sent(value=pool.get_id() if pool is not None else None),
                held_value_is_default=attribute.is_default is True,
                tracking_pool_id=tracking_pool_id,
                held_value=number,
            )
        )

        match intent:
            case FromPoolIntent.REFUSE:
                raise ValidationError(
                    {
                        f"{attribute.name}.from_pool": (
                            f"'{attribute.name}' already holds {attribute.value}, so 'from_pool' alone is ambiguous. "
                            "Send the value together with 'from_pool' to have the pool track it, "
                            "or send 'value: null' with 'from_pool' to discard it and allocate a new number."
                        )
                    }
                )
            case FromPoolIntent.NO_OP:
                return
            case FromPoolIntent.DETACH:
                await self.number_allocator.release(attribute=attribute, user_id=user_id)
            case FromPoolIntent.ATTACH:
                await self._attach(
                    node=node, pool=self._require_pool(pool=pool, intent=intent), attribute=attribute, user_id=user_id
                )
            case FromPoolIntent.ALLOCATE:
                await self._allocate(
                    node=node, pool=self._require_pool(pool=pool, intent=intent), attribute=attribute, user_id=user_id
                )
            case _:
                assert_never(intent)

    async def _apply_schema_number_pool(
        self, node: Node, attribute: BaseAttribute, pool_id: str | None, allocate: bool, user_id: str
    ) -> None:
        """Allocate from the pool a NumberPool attribute is declared with, whatever the payload holds.

        Raises:
            ValidationError: When the pool is not provisioned, cannot be found or used for the attribute,
                or is exhausted.

        """
        if not pool_id:
            raise ValidationError({f"{attribute.name}": f"The pool for {attribute.name} has not been provisioned yet."})
        attribute.from_pool = {"id": pool_id}
        if not allocate:
            return

        pool = await self._find_pool(attribute=attribute, pool_ref=pool_id)
        attribute.from_pool = {"id": pool.get_id()}
        self._check_pool_targets_attribute(schema=node.get_schema(), pool=pool, attribute=attribute)
        await self._allocate(node=node, pool=pool, attribute=attribute, user_id=user_id)

    async def _attach(self, node: Node, pool: CoreNumberPool, attribute: BaseAttribute, user_id: str) -> None:
        attribute.pool_provenance = PoolRecordProvenance.PROVIDED
        # An attribute not saved yet is attached to the pool when the node is created.
        if attribute.id is not None:
            await self.number_allocator.attach(pool=pool, node=node, attribute=attribute, user_id=user_id)

    async def _allocate(self, node: Node, pool: CoreNumberPool, attribute: BaseAttribute, user_id: str) -> None:
        """Set the attribute's value from the pool.

        Raises:
            ValidationError: When the pool is exhausted.

        """
        attribute.pool_provenance = PoolRecordProvenance.ALLOCATED
        try:
            attribute.value = await self.number_allocator.allocate(
                pool=pool, node=node, attribute=attribute, user_id=user_id
            )
        except PoolExhaustedError as exc:
            raise ValidationError({f"{attribute.name}.from_pool": exc.message}) from exc
        attribute.is_default = False

    async def _find_pool(self, attribute: BaseAttribute, pool_ref: str) -> CoreNumberPool:
        """Return the pool `pool_ref` names.

        Raises:
            ValidationError: When no number pool has that id or name.

        """
        try:
            return await self.pool_finder.find(pool_ref=pool_ref)
        except NodeNotFoundError as exc:
            raise ValidationError(
                {f"{attribute.name}.from_pool": f"The pool requested {attribute.from_pool} was not found."}
            ) from exc

    @staticmethod
    def _check_pool_targets_attribute(
        schema: NonGenericSchemaTypes, pool: CoreNumberPool, attribute: BaseAttribute
    ) -> None:
        """Ensure the pool was created for this attribute of this kind, or of a generic it inherits from.

        Raises:
            ValidationError: When the pool targets another kind or attribute.

        """
        if pool.node.value in [schema.kind, *schema.inherit_from] and pool.node_attribute.value == attribute.name:
            return
        raise ValidationError(
            {f"{attribute.name}.from_pool": f"The {pool.name.value} pool can't be used for '{attribute.name}'."}
        )

    @staticmethod
    def _get_number(attribute: BaseAttribute) -> int | None:
        """Return the number the attribute holds, or None when it holds none.

        Raises:
            InitializationError: When the attribute holds something other than a number.

        """
        if attribute.value is None or isinstance(attribute.value, int):
            return attribute.value
        raise InitializationError(f"'{attribute.name}' holds {attribute.value!r}, which a number pool cannot track")

    @staticmethod
    def _require_pool(pool: CoreNumberPool | None, intent: FromPoolIntent) -> CoreNumberPool:
        """Return the pool an intent acts on.

        Raises:
            InitializationError: When the intent was resolved without a pool.

        """
        if pool is None:
            raise InitializationError(f"A from_pool intent of {intent.value} needs a number pool")
        return pool
