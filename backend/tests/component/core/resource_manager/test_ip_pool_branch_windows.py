"""An IP pool keeps a prefix or an address taken while any live branch holds it and its namespace, and frees it after."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from tests.component.core.resource_manager.conftest import mark_branches_deleting
from tests.helpers.ip_pool import (
    IP_POOL_CASES,
    IPPoolCase,
    create_namespace,
    create_pool,
    create_prefix,
    delete_on,
    pool_on,
    set_value_on,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def _pool_with_one_resource(db: InfrahubDatabase, case: IPPoolCase) -> tuple[Node, Node]:
    """The pool's namespace and the pool, allocating from the case's resource."""
    namespace = await create_namespace(db=db)
    resource = await create_prefix(db=db, namespace=namespace, value=case.resource)
    pool = await create_pool(db=db, case=case, namespace=namespace, resources=[resource])
    return namespace, pool


@pytest.mark.parametrize("case", IP_POOL_CASES, ids=lambda case: case.name)
@pytest.mark.usefixtures("default_ipnamespace", "register_ipam_schema", "init_nodes_registry")
class TestIPPoolAllocationAcrossBranches:
    async def test_value_deleted_on_main_after_branch_is_not_reallocated_on_branch(
        self, db: InfrahubDatabase, default_branch: Branch, case: IPPoolCase
    ) -> None:
        """The branch still holds the value, so the branch must not receive it again."""
        first_value, second_value = case.values(count=2)
        _, pool = await _pool_with_one_resource(db=db, case=case)
        first = await case.allocate(db=db, pool=pool, branch=default_branch)
        assert case.value_of(first) == first_value

        branch = await create_branch(db=db, branch_name="delete-on-main")
        await first.delete(db=db)

        second = await case.allocate(db=db, pool=await pool_on(db=db, pool=pool, branch=branch), branch=branch)

        assert case.value_of(second) == second_value
        assert await case.allocated_values_on(db=db, branch=branch) == sorted([first_value, second_value])

    async def test_namespace_deleted_on_branch_does_not_free_values_on_main(
        self, db: InfrahubDatabase, default_branch: Branch, case: IPPoolCase
    ) -> None:
        """Main still holds the namespace and its values, so main must not receive an allocated value again."""
        first_value, second_value = case.values(count=2)
        namespace, pool = await _pool_with_one_resource(db=db, case=case)
        first = await case.allocate(db=db, pool=pool, branch=default_branch)
        assert case.value_of(first) == first_value

        branch = await create_branch(db=db, branch_name="namespace-delete-on-branch")
        namespace_on_branch = await NodeManager.get_one(db=db, id=namespace.id, branch=branch, raise_on_error=True)
        await NodeManager.delete(
            db=db, branch=branch, nodes=[await pool_on(db=db, pool=pool, branch=branch), namespace_on_branch]
        )

        second = await case.allocate(db=db, pool=pool, branch=default_branch)

        assert case.value_of(second) == second_value
        assert await case.allocated_values_on(db=db, branch=default_branch) == sorted([first_value, second_value])


@pytest.mark.parametrize("case", IP_POOL_CASES, ids=lambda case: case.name)
@pytest.mark.usefixtures("default_ipnamespace", "register_ipam_schema", "init_nodes_registry")
class TestIPPoolReleaseAcrossBranches:
    async def test_value_deleted_on_main_and_on_branch_is_free_again(
        self, db: InfrahubDatabase, default_branch: Branch, case: IPPoolCase
    ) -> None:
        """Once no live branch holds the value, main and the branch can both receive it again."""
        (first_value,) = case.values(count=1)
        _, pool = await _pool_with_one_resource(db=db, case=case)
        first = await case.allocate(db=db, pool=pool, branch=default_branch)
        assert case.value_of(first) == first_value

        branch = await create_branch(db=db, branch_name="delete-everywhere")
        await first.delete(db=db)
        await delete_on(db=db, node=first, branch=branch)

        assert await case.next_value(db=db, pool=pool, branch=default_branch) == first_value
        second = await case.allocate(db=db, pool=await pool_on(db=db, pool=pool, branch=branch), branch=branch)
        assert case.value_of(second) == first_value

    async def test_value_held_only_by_a_branch_being_deleted_is_free_on_main(
        self, db: InfrahubDatabase, default_branch: Branch, case: IPPoolCase
    ) -> None:
        """A branch being deleted holds nothing, so main can receive the value it still holds."""
        (first_value,) = case.values(count=1)
        _, pool = await _pool_with_one_resource(db=db, case=case)
        first = await case.allocate(db=db, pool=pool, branch=default_branch)
        assert case.value_of(first) == first_value

        branch = await create_branch(db=db, branch_name="holder-being-deleted")
        await first.delete(db=db)
        await mark_branches_deleting(db=db, branches=[branch])

        second = await case.allocate(db=db, pool=pool, branch=default_branch)
        assert case.value_of(second) == first_value

    async def test_value_deleted_on_branch_only_is_not_reallocated_on_branch(
        self, db: InfrahubDatabase, default_branch: Branch, case: IPPoolCase
    ) -> None:
        """Main still holds the value, so the branch that deleted it must not receive it again."""
        first_value, second_value = case.values(count=2)
        _, pool = await _pool_with_one_resource(db=db, case=case)
        first = await case.allocate(db=db, pool=pool, branch=default_branch)
        assert case.value_of(first) == first_value

        branch = await create_branch(db=db, branch_name="delete-on-branch")
        await delete_on(db=db, node=first, branch=branch)

        second = await case.allocate(db=db, pool=await pool_on(db=db, pool=pool, branch=branch), branch=branch)
        assert case.value_of(second) == second_value


@pytest.mark.parametrize("case", IP_POOL_CASES, ids=lambda case: case.name)
@pytest.mark.usefixtures("default_ipnamespace", "register_ipam_schema", "init_nodes_registry")
class TestIPPoolValueChangedOnBranch:
    async def test_value_changed_on_branch_keeps_both_values_taken(
        self, db: InfrahubDatabase, default_branch: Branch, case: IPPoolCase
    ) -> None:
        """Main still holds the original value and the branch holds the new one, so main receives neither."""
        original, changed, expected = case.values(count=3)
        _, pool = await _pool_with_one_resource(db=db, case=case)
        first = await case.allocate(db=db, pool=pool, branch=default_branch)
        assert case.value_of(first) == original

        branch = await create_branch(db=db, branch_name="change-on-branch")
        await set_value_on(db=db, node=first, branch=branch, attribute_name=case.attribute_name, value=changed)

        assert await case.next_value(db=db, pool=pool, branch=default_branch) == expected

    async def test_value_changed_on_branch_then_deleted_on_main_frees_only_the_original(
        self, db: InfrahubDatabase, default_branch: Branch, case: IPPoolCase
    ) -> None:
        """The branch replaced the original value and main deleted the node, so only the branch's value stays taken."""
        original, changed, after_changed = case.values(count=3)
        _, pool = await _pool_with_one_resource(db=db, case=case)
        first = await case.allocate(db=db, pool=pool, branch=default_branch)
        assert case.value_of(first) == original

        branch = await create_branch(db=db, branch_name="change-on-branch-delete-on-main")
        await set_value_on(db=db, node=first, branch=branch, attribute_name=case.attribute_name, value=changed)
        await first.delete(db=db)

        second = await case.allocate(db=db, pool=pool, branch=default_branch)
        assert case.value_of(second) == original
        assert await case.next_value(db=db, pool=pool, branch=default_branch) == after_changed

    async def test_value_replaced_on_main_after_branch_creation_is_free_again(
        self, db: InfrahubDatabase, default_branch: Branch, case: IPPoolCase
    ) -> None:
        """The branch was created before the value, so once main replaces the value no live branch holds it."""
        original, replacement = case.values(count=2)
        _, pool = await _pool_with_one_resource(db=db, case=case)
        await create_branch(db=db, branch_name="replace-on-main")
        first = await case.allocate(db=db, pool=pool, branch=default_branch)
        assert case.value_of(first) == original

        await set_value_on(
            db=db, node=first, branch=default_branch, attribute_name=case.attribute_name, value=replacement
        )

        assert await case.next_value(db=db, pool=pool, branch=default_branch) == original

    async def test_value_changed_on_branch_then_moved_on_main_into_pool_namespace_is_free(
        self, db: InfrahubDatabase, default_branch: Branch, case: IPPoolCase
    ) -> None:
        """Main sees the node in the pool's namespace only with its main value, and the branch sees it in another namespace."""
        changed, original, after_original = case.values(count=3)
        namespace, pool = await _pool_with_one_resource(db=db, case=case)
        other_namespace = await create_namespace(db=db, name="other-ns")
        moved = await case.create_held_node(db=db, namespace=other_namespace, value=original)

        branch = await create_branch(db=db, branch_name="change-on-branch-move-on-main")
        await set_value_on(db=db, node=moved, branch=branch, attribute_name=case.attribute_name, value=changed)
        await moved.get_relationship("ip_namespace").update(db=db, data=namespace)
        await moved.save(db=db)

        first = await case.allocate(db=db, pool=pool, branch=default_branch)
        assert case.value_of(first) == changed
        assert await case.next_value(db=db, pool=pool, branch=default_branch) == after_original
