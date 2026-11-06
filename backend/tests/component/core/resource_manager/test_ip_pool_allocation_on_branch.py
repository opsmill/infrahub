"""An IP pool allocating on a branch uses only the namespace and the resources that exist on that branch."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.initialization import create_branch
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import PoolExhaustedError, ResourceNotFoundError
from tests.helpers.agnostic_edges import TEST_ACTOR_ID
from tests.helpers.ip_pool import (
    ADDRESS_POOL_IPV4,
    NAMESPACE_NAME,
    POOL_NAME,
    PREFIX_POOL_IPV4,
    IPPoolCase,
    create_namespace,
    create_pool,
    create_prefix,
    pool_on,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def _merge(db: InfrahubDatabase, default_branch: Branch, branch: Branch) -> None:
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    await diff_merger.merge_graph(at=Timestamp(), user_id=TEST_ACTOR_ID)


def _namespace_missing_message(branch: Branch) -> str:
    return (
        f"Pool '{POOL_NAME}' cannot allocate on branch '{branch.name}': "
        f"its namespace '{NAMESPACE_NAME}' does not exist on this branch."
    )


def _resources_missing_message(branch: Branch) -> str:
    return f"Pool '{POOL_NAME}' cannot allocate on branch '{branch.name}': none of its resources exist on this branch."


@pytest.mark.parametrize("case", [PREFIX_POOL_IPV4, ADDRESS_POOL_IPV4], ids=lambda case: case.name)
@pytest.mark.usefixtures("default_ipnamespace", "register_ipam_schema", "init_nodes_registry")
class TestIPPoolAllocationOnBranch:
    async def test_namespace_missing_on_the_allocating_branch_is_refused(
        self, db: InfrahubDatabase, default_branch: Branch, case: IPPoolCase
    ) -> None:
        """The allocated value would point at a namespace the branch does not hold."""
        branch = await create_branch(db=db, branch_name="holds-the-namespace")
        namespace = await create_namespace(db=db, branch=branch)
        resource = await create_prefix(db=db, branch=branch, namespace=namespace, value=case.resource)
        pool = await create_pool(db=db, branch=branch, case=case, namespace=namespace, resources=[resource])

        pool_on_main = await pool_on(db=db, pool=pool, branch=default_branch)
        with pytest.raises(ResourceNotFoundError, match=rf"^{re.escape(_namespace_missing_message(default_branch))}$"):
            await case.allocate(db=db, pool=pool_on_main, branch=default_branch)

    async def test_namespace_deleted_with_its_branch_is_refused(
        self, db: InfrahubDatabase, default_branch: Branch, case: IPPoolCase
    ) -> None:
        """Deleting the branch that held the namespace also removes the pool's link to it, so there is no name to give."""
        branch = await create_branch(db=db, branch_name="held-the-namespace")
        namespace = await create_namespace(db=db, branch=branch)
        resource = await create_prefix(db=db, branch=branch, namespace=namespace, value=case.resource)
        pool = await create_pool(db=db, branch=branch, case=case, namespace=namespace, resources=[resource])
        await BranchDataDeleter(db=db, batch_size=100).delete(branch=branch)

        pool_on_main = await pool_on(db=db, pool=pool, branch=default_branch)
        expected = (
            f"Pool '{POOL_NAME}' cannot allocate on branch '{default_branch.name}': "
            "its namespace does not exist on this branch."
        )
        with pytest.raises(ResourceNotFoundError, match=rf"^{re.escape(expected)}$"):
            await case.allocate(db=db, pool=pool_on_main, branch=default_branch)

    async def test_no_resource_on_the_allocating_branch_exhausts_the_pool(
        self, db: InfrahubDatabase, default_branch: Branch, default_ipnamespace: Node, case: IPPoolCase
    ) -> None:
        """The pool's only resource exists on another branch, so the default branch has nothing to allocate from."""
        branch = await create_branch(db=db, branch_name="holds-the-resource")
        resource = await create_prefix(db=db, branch=branch, namespace=default_ipnamespace, value=case.resource)
        pool = await create_pool(
            db=db, branch=default_branch, case=case, namespace=default_ipnamespace, resources=[resource]
        )

        pool_on_main = await pool_on(db=db, pool=pool, branch=default_branch)
        with pytest.raises(PoolExhaustedError, match=rf"^{re.escape(_resources_missing_message(default_branch))}$"):
            await case.allocate(db=db, pool=pool_on_main, branch=default_branch)

    async def test_only_resources_on_the_allocating_branch_are_used(
        self, db: InfrahubDatabase, default_branch: Branch, default_ipnamespace: Node, case: IPPoolCase
    ) -> None:
        """The heavier resource exists only on another branch, so the default branch allocates from the lighter one."""
        on_main = await create_prefix(
            db=db, branch=default_branch, namespace=default_ipnamespace, value=case.resource, allocation_weight=1
        )
        branch = await create_branch(db=db, branch_name="holds-the-heavier-resource")
        on_branch = await create_prefix(
            db=db, branch=branch, namespace=default_ipnamespace, value=case.other_resource, allocation_weight=100
        )
        pool = await create_pool(
            db=db, branch=default_branch, case=case, namespace=default_ipnamespace, resources=[on_main, on_branch]
        )

        allocated = await case.allocate(
            db=db, pool=await pool_on(db=db, pool=pool, branch=default_branch), branch=default_branch
        )

        assert case.value_of(allocated) == case.values(count=1)[0]

    async def test_pool_created_on_a_branch_allocates_there_and_after_the_merge(
        self, db: InfrahubDatabase, default_branch: Branch, case: IPPoolCase
    ) -> None:
        """The namespace, the resource and the pool are created together on the branch, then merged."""
        first_value, second_value = case.values(count=2)
        branch = await create_branch(db=db, branch_name="creates-the-pool")
        namespace = await create_namespace(db=db, branch=branch)
        resource = await create_prefix(db=db, branch=branch, namespace=namespace, value=case.resource)
        pool = await create_pool(db=db, branch=branch, case=case, namespace=namespace, resources=[resource])

        on_branch = await case.allocate(db=db, pool=await pool_on(db=db, pool=pool, branch=branch), branch=branch)
        assert case.value_of(on_branch) == first_value

        await _merge(db=db, default_branch=default_branch, branch=branch)

        on_main = await case.allocate(
            db=db, pool=await pool_on(db=db, pool=pool, branch=default_branch), branch=default_branch
        )
        assert case.value_of(on_main) == second_value
