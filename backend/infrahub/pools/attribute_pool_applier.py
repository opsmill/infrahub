from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
from infrahub.core.schema import TemplateSchema
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.exceptions import InitializationError, NodeNotFoundError, PoolExhaustedError, ValidationError

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNumberPool


class NumberPoolFinder(Protocol):
    async def find(self, pool_ref: str) -> CoreNumberPool:
        """Return the number pool whose id or name is `pool_ref`.

        Raises:
            NodeNotFoundError: When no number pool has that id or name.

        """
        ...


class AttributeNumberAllocator(Protocol):
    async def allocate(self, pool: CoreNumberPool, node: Node, attribute: BaseAttribute) -> int:
        """Return the number the pool gives the attribute.

        Raises:
            PoolExhaustedError: When the pool has no number left to give.

        """
        ...


class AttributePoolApplierInterface(Protocol):
    async def apply(self, node: Node, attribute: BaseAttribute, allocate: bool) -> None:
        """Resolve the pool the attribute draws from and, when `allocate` is set, set its value from it.

        Raises:
            ValidationError: When the attribute cannot draw from the pool it names.

        """
        ...


class LoadedNodePoolApplier:
    """Stands in for the applier on a node loaded from the database, which never draws from a pool."""

    async def apply(self, node: Node, attribute: BaseAttribute, allocate: bool) -> None:  # noqa: ARG002
        """Refuse, since reaching this means a loaded node was asked to draw a number.

        Raises:
            InitializationError: Always.

        """
        raise InitializationError(f"The loaded node {node.get_id()} cannot draw '{attribute.name}' from a pool")


class AttributePoolApplier:
    """Give an attribute its number from the number pool it is set to draw from.

    A NumberPool attribute always draws from the pool its schema declares; any other Number attribute
    draws from the pool its `from_pool` names.
    """

    def __init__(self, pool_finder: NumberPoolFinder, number_allocator: AttributeNumberAllocator) -> None:
        self.pool_finder = pool_finder
        self.number_allocator = number_allocator

    async def apply(self, node: Node, attribute: BaseAttribute, allocate: bool) -> None:
        """Resolve the pool the attribute draws from and, when `allocate` is set, set its value from it.

        Without `allocate` only the pool is resolved, so the lock names can be computed.

        Raises:
            ValidationError: When `from_pool` is used on a template, when no pool ID is provided, when the
                pool is not provisioned or cannot be found, when the pool cannot be used for the attribute,
                or when the pool is exhausted.

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

        pool_ref = self._get_pool_ref(attribute=attribute)
        if not pool_ref:
            return

        try:
            pool = await self.pool_finder.find(pool_ref=pool_ref)
        except NodeNotFoundError as exc:
            raise ValidationError(
                {f"{attribute.name}.from_pool": f"The pool requested {attribute.from_pool} was not found."}
            ) from exc

        # A pool named rather than identified still has to be recorded by its id: the reservation is
        # written by matching the pool vertex on `uuid`.
        attribute.from_pool = {"id": pool.get_id()}

        if not allocate:
            return

        if pool.node.value not in [schema.kind, *schema.inherit_from] or pool.node_attribute.value != attribute.name:
            raise ValidationError(
                {f"{attribute.name}.from_pool": f"The {pool.name.value} pool can't be used for '{attribute.name}'."}
            )

        try:
            attribute.value = await self.number_allocator.allocate(pool=pool, node=node, attribute=attribute)
        except PoolExhaustedError as exc:
            raise ValidationError({f"{attribute.name}.from_pool": f"The pool {pool.node.value} is exhausted."}) from exc

    @staticmethod
    def _get_pool_ref(attribute: BaseAttribute) -> str | None:
        """Return the id or name of the pool the attribute draws from, or None when it draws from none.

        Raises:
            ValidationError: When a NumberPool attribute's pool is not provisioned, or `from_pool` names no pool.

        """
        if attribute.schema.kind == "NumberPool" and isinstance(attribute.schema.parameters, NumberPoolParameters):
            pool_id = attribute.schema.parameters.number_pool_id
            if not pool_id:
                raise ValidationError(
                    {f"{attribute.name}": f"The pool for {attribute.name} has not been provisioned yet."}
                )
            attribute.from_pool = {"id": pool_id}
            attribute.is_default = False
            return pool_id

        if not attribute.from_pool:
            return None
        pool_ref = attribute.from_pool.get("id")
        if not pool_ref:
            raise ValidationError({f"{attribute.name}.from_pool": "No pool ID specified in from_pool."})
        return pool_ref
