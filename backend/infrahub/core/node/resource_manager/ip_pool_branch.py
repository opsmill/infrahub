"""Read an IP pool's namespace and resources as they exist on the branch that allocates from the pool.

The pool links to them through branch-agnostic relationships, so a link can point at a node that exists only on
another branch. Allocating on a branch uses only the nodes that exist on that branch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.manager import NodeManager
from infrahub.exceptions import NodeNotFoundError, PoolExhaustedError, ResourceNotFoundError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def get_namespace_on_branch(db: InfrahubDatabase, pool: Node, branch: Branch) -> Node:
    """Return the pool's namespace as it exists on `branch`.

    Raises:
        ResourceNotFoundError: When the namespace does not exist on `branch`.

    """
    relationship = pool.get_relationship("ip_namespace")
    namespace_id = await relationship.get_peer_id(db=db)
    if namespace_id:
        namespace = await NodeManager.get_one(db=db, id=namespace_id, branch=branch)
        if namespace is not None:
            return namespace

    namespace_name = ""
    if namespace_id:
        namespace_name = f" '{await _namespace_label(db=db, pool=pool, namespace_id=namespace_id)}'"
    raise ResourceNotFoundError(
        message=(
            f"Pool '{await pool.get_display_label(db=db)}' cannot allocate on branch '{branch.name}': "
            f"its namespace{namespace_name} does not exist on this branch."
        )
    )


async def _namespace_label(db: InfrahubDatabase, pool: Node, namespace_id: str) -> str:
    # The pool's link reads the namespace from a branch that holds it, when any branch still does.
    try:
        namespace = await pool.get_relationship("ip_namespace").get_peer(db=db)
    except NodeNotFoundError:
        return namespace_id
    if namespace is None:
        return namespace_id
    return await namespace.get_display_label(db=db)


async def get_resources_on_branch(db: InfrahubDatabase, pool: Node, branch: Branch) -> list[Node]:
    """Return the pool's resources that exist on `branch`, the highest allocation weight first.

    Raises:
        PoolExhaustedError: When none of the resources exists on `branch`.

    """
    relationships = await pool.get_relationship("resources").get_relationships(db=db)
    peer_ids = [relationship.peer_id for relationship in relationships if relationship.peer_id]
    resources = await NodeManager.get_many(db=db, ids=peer_ids, branch=branch)
    if not resources:
        raise PoolExhaustedError(
            message=(
                f"Pool '{await pool.get_display_label(db=db)}' cannot allocate on branch '{branch.name}': "
                "none of its resources exist on this branch."
            )
        )

    return sorted(resources.values(), key=_allocation_weight, reverse=True)


def _allocation_weight(resource: Node) -> int:
    try:
        weight = resource.get_attribute("allocation_weight").value
    except ValueError:
        return 0
    return weight if isinstance(weight, int) else 0
