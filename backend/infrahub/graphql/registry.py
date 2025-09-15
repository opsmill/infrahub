from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import InitializationError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.graphql.manager import GraphQLSchemaManager


@dataclass
class BranchDetails:
    schema_changed_at: Timestamp
    schema_hash: str
    gql_manager: GraphQLSchemaManager


@dataclass
class GraphQLSchemaRegistry:
    branch_details_by_hash: dict[str, BranchDetails] = field(default_factory=dict)
    branch_name_by_hash: dict[str, set[str]] = field(default_factory=dict)
    branch_hash_activation_by_branch_name: dict[str, dict[str, str]] = field(default_factory=dict)
    _manager_class: type[GraphQLSchemaManager] | None = None

    def _add_branch_hash(self, branch_name: str, schema_hash: str) -> None:
        if schema_hash not in self.branch_name_by_hash:
            self.branch_name_by_hash[schema_hash] = set()

        self.branch_name_by_hash[schema_hash].add(branch_name)

    def _register_manager(self, manager: type[GraphQLSchemaManager]) -> None:
        self._manager_class = manager

    @property
    def manager(self) -> type[GraphQLSchemaManager]:
        if self._manager_class:
            return self._manager_class
        raise InitializationError

    def clear_cache(self) -> None:
        """Clear internal cache stored within this registry."""
        self.branch_details_by_hash = {}
        self.branch_name_by_hash = {}
        self.branch_hash_activation_by_branch_name = {}

    def purge_inactive(self, active_branches: list[str]) -> set[str]:
        """Return inactive branches that were purged"""
        inactive_branches: set[str] = set()
        for schema_hash in list(self.branch_name_by_hash.keys()):
            branches = list(self.branch_name_by_hash[schema_hash])
            for branch in branches:
                if branch not in active_branches and branch in self.branch_name_by_hash[schema_hash]:
                    inactive_branches.add(branch)
                    self.branch_name_by_hash[schema_hash].discard(branch)

        for schema_hash in list(self.branch_name_by_hash.keys()):
            if not self.branch_name_by_hash[schema_hash]:
                # If no remaining branch is using the schema remove it completely
                del self.branch_name_by_hash[schema_hash]
                del self.branch_details_by_hash[schema_hash]

        return inactive_branches

    def cache_branch(self, branch: Branch, schema_branch: SchemaBranch, schema_hash: str) -> BranchDetails:
        branch_details = BranchDetails(
            schema_changed_at=Timestamp(branch.schema_changed_at) if branch.schema_changed_at else Timestamp(),
            schema_hash=schema_hash,
            gql_manager=self.manager(schema=schema_branch),
        )

        self.branch_details_by_hash[schema_hash] = branch_details

        return branch_details

    def get_manager_for_branch(self, branch: Branch, schema_branch: SchemaBranch) -> GraphQLSchemaManager:
        if branch.schema_hash:
            schema_hash = branch.schema_hash.main
        else:
            schema_hash = schema_branch.get_hash()

        if schema_hash in self.branch_details_by_hash:
            branch_details = self.branch_details_by_hash[schema_hash]
        else:
            branch_details = self.cache_branch(branch=branch, schema_branch=schema_branch, schema_hash=schema_hash)

        self._add_branch_hash(branch_name=branch.name, schema_hash=schema_hash)

        return branch_details.gql_manager


registry = GraphQLSchemaRegistry()
