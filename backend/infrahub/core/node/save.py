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
) -> None:
    schema_branch = db.schema.get_schema_branch(name=branch.name)
    lock_names = get_lock_names_on_object_mutation(node=node, branch=branch, schema_branch=schema_branch)
    async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
        await node_constraint_runner.check(
            node=node, field_filters=fields_to_validate, skip_uniqueness_check=skip_uniqueness_check
        )
        await node.save(db=db, fields=fields_to_save)
