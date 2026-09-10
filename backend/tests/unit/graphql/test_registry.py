from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import graphene

from infrahub.core.branch import Branch
from infrahub.core.models import SchemaBranchHash
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graphql.mutations.main import InfrahubMutation
from infrahub.graphql.registry import GraphQLSchemaRegistry
from infrahub.graphql.types import InfrahubObject

if TYPE_CHECKING:
    from infrahub.graphql.manager import GraphQLSchemaManager


class ManagerStub:
    """Stands in for GraphQLSchemaManager: records how many managers the registry builds.

    `on_build` runs when the registry asks the manager for its schema, which is when the real
    manager claims the registered types it is made of (registry.get_*_type / set_*_type).
    """

    instances: list["ManagerStub"] = []
    on_build: Callable[["ManagerStub"], None] | None = None

    def __init__(self, schema: SchemaBranch) -> None:
        self.schema = schema
        self.built = False
        ManagerStub.instances.append(self)

    def get_graphql_schema(self) -> None:
        self.built = True
        if ManagerStub.on_build:
            ManagerStub.on_build(self)


def make_registry() -> GraphQLSchemaRegistry:
    ManagerStub.instances = []
    ManagerStub.on_build = None
    registry = GraphQLSchemaRegistry()
    registry._register_manager(manager=cast("type[GraphQLSchemaManager]", ManagerStub))
    return registry


def make_branch(name: str, schema_hash: str) -> Branch:
    return Branch(name=name, schema_hash=SchemaBranchHash(main=schema_hash))


def make_schema_branch(name: str) -> SchemaBranch:
    return SchemaBranch(cache={}, name=name)


def test_same_hash_reuses_cached_manager() -> None:
    registry = make_registry()
    schema_branch = make_schema_branch(name="main")

    first = registry.get_manager_for_branch(branch=make_branch("main", "hash-a"), schema_branch=schema_branch)
    second = registry.get_manager_for_branch(branch=make_branch("main", "hash-a"), schema_branch=schema_branch)

    assert first is second
    assert len(ManagerStub.instances) == 1
    assert ManagerStub.instances[0].built


def test_same_hash_reused_across_branches() -> None:
    registry = make_registry()

    main = registry.get_manager_for_branch(
        branch=make_branch("main", "hash-a"), schema_branch=make_schema_branch(name="main")
    )
    other = registry.get_manager_for_branch(
        branch=make_branch("branch2", "hash-a"), schema_branch=make_schema_branch(name="branch2")
    )

    assert main is other
    assert len(ManagerStub.instances) == 1


def test_branch_moving_to_new_hash_evicts_previous_hash() -> None:
    registry = make_registry()
    schema_branch = make_schema_branch(name="main")

    registry.get_manager_for_branch(branch=make_branch("main", "hash-a"), schema_branch=schema_branch)
    registry.get_manager_for_branch(branch=make_branch("main", "hash-b"), schema_branch=schema_branch)

    assert "hash-a" not in registry._branch_details_by_hash
    assert "hash-b" in registry._branch_details_by_hash

    # coming back to the evicted hash builds a fresh manager
    registry.get_manager_for_branch(branch=make_branch("main", "hash-a"), schema_branch=schema_branch)
    assert len(ManagerStub.instances) == 3


def test_no_eviction_while_another_branch_uses_previous_hash() -> None:
    registry = make_registry()

    registry.get_manager_for_branch(branch=make_branch("main", "hash-a"), schema_branch=make_schema_branch("main"))
    registry.get_manager_for_branch(
        branch=make_branch("branch2", "hash-a"), schema_branch=make_schema_branch("branch2")
    )

    registry.get_manager_for_branch(branch=make_branch("main", "hash-b"), schema_branch=make_schema_branch("main"))
    assert "hash-a" in registry._branch_details_by_hash

    registry.get_manager_for_branch(
        branch=make_branch("branch2", "hash-b"), schema_branch=make_schema_branch("branch2")
    )
    assert "hash-a" not in registry._branch_details_by_hash


def test_reactivating_same_hash_keeps_cache() -> None:
    registry = make_registry()
    schema_branch = make_schema_branch(name="main")

    first = registry.get_manager_for_branch(branch=make_branch("main", "hash-a"), schema_branch=schema_branch)
    second = registry.get_manager_for_branch(branch=make_branch("main", "hash-a"), schema_branch=schema_branch)

    assert first is second
    assert "hash-a" in registry._branch_details_by_hash


def test_previous_hash_is_retired_only_after_the_new_schema_claimed_its_types() -> None:
    registry = make_registry()
    schema_branch = make_schema_branch(name="main")

    registry.get_manager_for_branch(branch=make_branch("main", "hash-a"), schema_branch=schema_branch)
    registry.set_edge_type(reference=InfrahubObject, reference_hash="edge-shared", schema_hash="hash-a")
    registry.set_edge_type(reference=InfrahubObject, reference_hash="edge-only-a", schema_hash="hash-a")

    found_while_generating: list[type[InfrahubObject] | None] = []

    def generate_hash_b_schema(_: ManagerStub) -> None:
        found_while_generating.append(registry.get_edge_type(reference_hash="edge-shared", schema_hash="hash-b"))

    ManagerStub.on_build = generate_hash_b_schema
    registry.get_manager_for_branch(branch=make_branch("main", "hash-b"), schema_branch=schema_branch)

    assert found_while_generating == [InfrahubObject]
    assert registry.get_edge_type(reference_hash="edge-shared", schema_hash="hash-b") is InfrahubObject
    assert registry.get_edge_type(reference_hash="edge-only-a", schema_hash="hash-b") is None


def test_eviction_prunes_types_only_referenced_by_evicted_hash() -> None:
    registry = make_registry()
    schema_branch = make_schema_branch(name="main")

    registry.get_manager_for_branch(branch=make_branch("main", "hash-a"), schema_branch=schema_branch)
    registry.set_object_type(reference=InfrahubObject, reference_hash="obj-only-a", schema_hash="hash-a")
    registry.set_input_type(reference=graphene.InputObjectType, reference_hash="input-shared", schema_hash="hash-a")

    def generate_hash_b_schema(_: ManagerStub) -> None:
        registry.get_input_type(reference_hash="input-shared", schema_hash="hash-b")

    ManagerStub.on_build = generate_hash_b_schema
    registry.get_manager_for_branch(branch=make_branch("main", "hash-b"), schema_branch=schema_branch)

    assert registry.get_object_type(reference_hash="obj-only-a", schema_hash="hash-b") is None
    assert registry.get_input_type(reference_hash="input-shared", schema_hash="hash-b") is graphene.InputObjectType


def test_purge_inactive_prunes_types_and_activation() -> None:
    registry = make_registry()

    registry.get_manager_for_branch(branch=make_branch("main", "hash-a"), schema_branch=make_schema_branch("main"))
    registry.get_manager_for_branch(
        branch=make_branch("branch2", "hash-b"), schema_branch=make_schema_branch("branch2")
    )
    registry.set_mutation_type(reference=InfrahubMutation, reference_hash="mut-only-b", schema_hash="hash-b")

    purged = registry.purge_inactive(active_branches=["main"])

    assert purged == {"branch2"}
    assert "hash-b" not in registry._branch_details_by_hash
    assert "hash-a" in registry._branch_details_by_hash
    assert registry.get_mutation_type(reference_hash="mut-only-b", schema_hash="hash-a") is None
    assert "branch2" not in registry._branch_hash_activation_by_branch_name
