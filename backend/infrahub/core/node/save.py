from collections.abc import Sequence

from infrahub import lock
from infrahub.core.branch import Branch
from infrahub.core.constraint.node.runner import NodeConstraintRunner
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.lock import InfrahubMultiLock
from infrahub.lock_getter import get_lock_names_on_object_mutation


async def run_constraints_and_save(
    node: Node,
    node_constraint_runner: NodeConstraintRunner,
    fields_to_validate: list[str],
    fields_to_save: list[str],
    db: InfrahubDatabase,
    branch: Branch,
    skip_uniqueness_check: bool = False,
    lock_names: Sequence[str] | None = None,
    manage_lock: bool = True,
) -> None:
    """Validate a node and persist it, optionally reusing an existing lock context.

    Args:
        node: The node instance to validate and persist.
        node_constraint_runner: Runner executing node-level constraints.
        fields_to_validate: Field names that must be validated.
        fields_to_save: Field names that must be persisted.
        db: Database connection or transaction to use for persistence.
        branch: Branch associated with the mutation.
        skip_uniqueness_check: Whether to skip uniqueness constraints.
        lock_names: Precomputed lock identifiers to reuse when ``manage_lock`` is False.
        manage_lock: Whether this helper should acquire and release locks itself.
    """

    if not manage_lock and lock_names is None:
        raise ValueError("lock_names must be provided when manage_lock is False")

    schema_branch = db.schema.get_schema_branch(name=branch.name)
    locks = (
        list(lock_names)
        if lock_names is not None
        else get_lock_names_on_object_mutation(node=node, schema_branch=schema_branch)
    )

    async def _persist() -> None:
        await node_constraint_runner.check(
            node=node, field_filters=fields_to_validate, skip_uniqueness_check=skip_uniqueness_check
        )
        await node.save(db=db, fields=fields_to_save)

    if manage_lock:
        async with InfrahubMultiLock(lock_registry=lock.registry, locks=locks):
            await _persist()
    else:
        await _persist()
