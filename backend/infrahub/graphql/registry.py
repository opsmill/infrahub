from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import InitializationError

if TYPE_CHECKING:
    import graphene

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.graphql.manager import GraphQLSchemaManager, InterfaceReference

    from .mutations.main import InfrahubMutation
    from .types import InfrahubObject


@dataclass
class BranchDetails:
    schema_changed_at: Timestamp
    schema_hash: str
    gql_manager: GraphQLSchemaManager


@dataclass
class GraphQLSchemaRegistry:
    _branch_details_by_hash: dict[str, BranchDetails] = field(default_factory=dict)
    _branch_name_by_hash: dict[str, set[str]] = field(default_factory=dict)
    _branch_hash_activation_by_branch_name: dict[str, dict[str, str]] = field(default_factory=dict)
    _registered_interface_types: dict[str, type[graphene.Interface]] = field(default_factory=dict)
    _reference_hash_schema_map: dict[str, set[str]] = field(default_factory=dict)
    _registered_edge_types: dict[str, type[InfrahubObject]] = field(default_factory=dict)
    _registered_paginated_types: dict[str, type[InfrahubObject]] = field(default_factory=dict)
    _registered_input_types: dict[str, type[graphene.InputObjectType]] = field(default_factory=dict)
    _registered_object_types: dict[str, type[InfrahubObject]] = field(default_factory=dict)
    _registered_mutation_types: dict[str, type[InfrahubMutation]] = field(default_factory=dict)

    _manager_class: type[GraphQLSchemaManager] | None = None

    def _add_branch_hash(self, branch_name: str, schema_hash: str) -> None:
        if schema_hash not in self._branch_name_by_hash:
            self._branch_name_by_hash[schema_hash] = set()

        self._branch_name_by_hash[schema_hash].add(branch_name)

    def _register_manager(self, manager: type[GraphQLSchemaManager]) -> None:
        self._manager_class = manager

    @property
    def manager(self) -> type[GraphQLSchemaManager]:
        if self._manager_class:
            return self._manager_class
        raise InitializationError

    def clear_cache(self) -> None:
        """Clear internal cache stored within this registry."""
        self._branch_details_by_hash = {}
        self._branch_name_by_hash = {}
        self._branch_hash_activation_by_branch_name = {}
        self._registered_interface_types = {}
        self._reference_hash_schema_map = {}
        self._registered_edge_types = {}
        self._registered_paginated_types = {}
        self._registered_input_types = {}
        self._registered_object_types = {}
        self._registered_mutation_types = {}

    def _add_schema_to_reference_hash(self, reference_hash: str, schema_hash: str) -> None:
        """Add the schema hash to a map containing the referenced object.

        The goal of this is to be able to see all schemas that use a given reference type,
        once no schemas use a specific type it's safe to remove the type from the registry.
        """
        if reference_hash not in self._reference_hash_schema_map:
            self._reference_hash_schema_map[reference_hash] = set()
        self._reference_hash_schema_map[reference_hash].add(schema_hash)

    def get_edge_type(self, reference_hash: str, schema_hash: str) -> type[InfrahubObject] | None:
        self._add_schema_to_reference_hash(reference_hash=reference_hash, schema_hash=schema_hash)
        return self._registered_edge_types.get(reference_hash)

    def set_edge_type(self, reference: type[InfrahubObject], reference_hash: str, schema_hash: str) -> None:
        self._add_schema_to_reference_hash(reference_hash=reference_hash, schema_hash=schema_hash)
        self._registered_edge_types[reference_hash] = reference

    def get_input_type(self, reference_hash: str, schema_hash: str) -> type[graphene.InputObjectType] | None:
        self._add_schema_to_reference_hash(reference_hash=reference_hash, schema_hash=schema_hash)
        return self._registered_input_types.get(reference_hash)

    def set_input_type(self, reference: type[graphene.InputObjectType], reference_hash: str, schema_hash: str) -> None:
        self._add_schema_to_reference_hash(reference_hash=reference_hash, schema_hash=schema_hash)
        self._registered_input_types[reference_hash] = reference

    def get_interface_type(self, reference_hash: str, schema_hash: str) -> type[graphene.Interface] | None:
        self._add_schema_to_reference_hash(reference_hash=reference_hash, schema_hash=schema_hash)
        return self._registered_interface_types.get(reference_hash)

    def set_interface_type(self, reference: InterfaceReference, schema_hash: str) -> None:
        self._add_schema_to_reference_hash(reference_hash=reference.reference_hash, schema_hash=schema_hash)
        self._registered_interface_types[reference.reference_hash] = reference.reference

    def get_mutation_type(self, reference_hash: str, schema_hash: str) -> type[InfrahubMutation] | None:
        self._add_schema_to_reference_hash(reference_hash=reference_hash, schema_hash=schema_hash)
        return self._registered_mutation_types.get(reference_hash)

    def set_mutation_type(self, reference: type[InfrahubMutation], reference_hash: str, schema_hash: str) -> None:
        self._add_schema_to_reference_hash(reference_hash=reference_hash, schema_hash=schema_hash)
        self._registered_mutation_types[reference_hash] = reference

    def get_object_type(self, reference_hash: str, schema_hash: str) -> type[InfrahubObject] | None:
        self._add_schema_to_reference_hash(reference_hash=reference_hash, schema_hash=schema_hash)
        return self._registered_object_types.get(reference_hash)

    def set_object_type(self, reference: type[InfrahubObject], reference_hash: str, schema_hash: str) -> None:
        self._add_schema_to_reference_hash(reference_hash=reference_hash, schema_hash=schema_hash)
        self._registered_object_types[reference_hash] = reference

    def get_paginated_type(self, reference_hash: str, schema_hash: str) -> type[InfrahubObject] | None:
        self._add_schema_to_reference_hash(reference_hash=reference_hash, schema_hash=schema_hash)
        return self._registered_paginated_types.get(reference_hash)

    def set_paginated_type(self, reference: type[InfrahubObject], reference_hash: str, schema_hash: str) -> None:
        self._add_schema_to_reference_hash(reference_hash=reference_hash, schema_hash=schema_hash)
        self._registered_paginated_types[reference_hash] = reference

    def purge_inactive(self, active_branches: list[str]) -> set[str]:
        """Return inactive branches that were purged"""
        inactive_branches: set[str] = set()
        for schema_hash in list(self._branch_name_by_hash.keys()):
            branches = list(self._branch_name_by_hash[schema_hash])
            for branch in branches:
                if branch not in active_branches and branch in self._branch_name_by_hash[schema_hash]:
                    inactive_branches.add(branch)
                    self._branch_name_by_hash[schema_hash].discard(branch)

        for schema_hash in list(self._branch_name_by_hash.keys()):
            if not self._branch_name_by_hash[schema_hash]:
                # If no remaining branch is using the schema remove it completely
                del self._branch_name_by_hash[schema_hash]
                del self._branch_details_by_hash[schema_hash]

        return inactive_branches

    def cache_branch(self, branch: Branch, schema_branch: SchemaBranch, schema_hash: str) -> BranchDetails:
        branch_details = BranchDetails(
            schema_changed_at=Timestamp(branch.schema_changed_at) if branch.schema_changed_at else Timestamp(),
            schema_hash=schema_hash,
            gql_manager=self.manager(schema=schema_branch),
        )

        self._branch_details_by_hash[schema_hash] = branch_details

        return branch_details

    def get_manager_for_branch(self, branch: Branch, schema_branch: SchemaBranch) -> GraphQLSchemaManager:
        if branch.schema_hash:
            schema_hash = branch.schema_hash.main
        else:
            schema_hash = schema_branch.get_hash()

        if schema_hash in self._branch_details_by_hash:
            branch_details = self._branch_details_by_hash[schema_hash]
        else:
            branch_details = self.cache_branch(branch=branch, schema_branch=schema_branch, schema_hash=schema_hash)

        self._add_branch_hash(branch_name=branch.name, schema_hash=schema_hash)

        return branch_details.gql_manager


registry = GraphQLSchemaRegistry()
